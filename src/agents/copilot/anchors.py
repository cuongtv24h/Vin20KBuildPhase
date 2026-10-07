"""Mỏ neo chứng cứ `[n]` — do **máy** chèn ở bước hậu xử lý (P2.1–P2.3).

Vì sao không để LLM tự viết mỏ neo: mô hình rất dễ đánh sai số thứ tự, gắn mỏ neo cho con số không
có nguồn, hoặc bỏ sót con số quan trọng. Ở đây ta làm ngược lại — LLM chỉ viết **nội dung**, còn việc
gắn mỏ neo là của lớp tất định:

1. Quét các con số có nghĩa tài chính (`6,1 tỷ`, `8%`) và mã văn bản (`CSBH-…`) trong câu trả lời.
2. Đối chiếu từng con số với **danh sách citation** của lượt (đã chuẩn hoá về giá trị số học, nên
   `6,1 tỷ` trong câu trả lời khớp `6.100.000.000 ₫` trong căn cứ).
3. Con số có nguồn → chèn `[n]` ngay sau nó, `n` đánh theo thứ tự xuất hiện, cùng một con số + cùng
   một nguồn thì dùng lại đúng số đó.
4. Con số **do Sale tự nêu trong câu hỏi** (ví dụ ngân sách 2 tỷ) → KHÔNG gắn mỏ neo, vì mỏ neo là
   con trỏ tới nguồn hệ thống; gắn vào đó sẽ khiến người đọc tưởng hệ thống đã xác thực con số ấy.
   Thay vào đó in đậm kèm nhãn: `**2 tỷ** (ngân sách anh/chị nhập)`.

Đầu ra kèm `anchors[]` để UI biến `[n]` thành nút bấm mở đúng căn cứ (Trust Engine cho Sale).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from src.agents.copilot import grounding, verifier

#: `[3]` — mỏ neo do LLM tự gõ (sẽ bị gỡ và đánh lại bằng máy).
_EXISTING_ANCHOR_RE = re.compile(r"\[\d{1,2}\]")
#: Ngữ cảnh ngân sách quanh con số của Sale, để chọn nhãn cho đúng.
_BUDGET_CONTEXT_RE = re.compile(
    r"(ngân sách|ngan sach|vốn tự có|von tu co|tài chính|tai chinh|budget|giá tối đa|gia toi da)",
    re.IGNORECASE,
)
_BUDGET_LOOKBEHIND_CHARS = 40
_BUDGET_LOOKAHEAD_CHARS = 12


@dataclass(frozen=True)
class Anchor:
    """Một mỏ neo đã chèn: `[index]` → citation thứ `citation_index` trong payload."""

    index: int
    value: str
    citation_index: int
    label: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "index": self.index,
            "value": self.value,
            "citation_index": self.citation_index,
            "label": self.label,
        }


@dataclass
class AnchoredReply:
    """Câu trả lời đã gắn mỏ neo + dữ liệu cho UI."""

    text: str
    anchors: list[Anchor] = field(default_factory=list)
    #: Con số được nhận là **của Sale** (có trong câu hỏi), đã in đậm kèm nhãn.
    labeled_inputs: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "text": self.text,
            "anchors": [a.as_dict() for a in self.anchors],
            "labeled_inputs": self.labeled_inputs,
        }


def _citation_blob(citation: dict[str, Any]) -> str:
    parts = [
        str(citation.get("policy_id") or ""),
        str(citation.get("section") or ""),
        str(citation.get("quote") or ""),
        str(citation.get("clause_id") or ""),
        str(citation.get("title") or ""),
    ]
    return " ".join(p for p in parts if p)


def _citation_numbers(citation: dict[str, Any]) -> set[float]:
    return set(verifier._money_values(_citation_blob(citation)))


def citation_label(citation: dict[str, Any], fallback_index: int) -> str:
    """Nhãn ngắn hiển thị ở tooltip/nút mở căn cứ."""
    policy_id = str(citation.get("policy_id") or "").strip()
    section = str(citation.get("section") or "").strip()
    if policy_id and section:
        return f"{policy_id} · {section}"
    if policy_id:
        return policy_id
    return f"Nguồn #{fallback_index + 1}"


def _matches(value: float, known: set[float]) -> bool:
    return verifier._claim_matches(value, known)


def _find_citation(
    value: float,
    citations: list[dict[str, Any]],
    citation_numbers: list[set[float]],
    text: str,
    start: int,
    end: int,
) -> int | None:
    """Tìm citation chứa giá trị này; nếu trùng nhiều nguồn thì ưu tiên nguồn gần con số nhất."""
    candidates = [idx for idx, numbers in enumerate(citation_numbers) if _matches(value, numbers)]
    if not candidates:
        return None
    if len(candidates) == 1:
        return candidates[0]
    # Nhiều nguồn cùng giá trị: chọn nguồn có nhãn xuất hiện gần con số trong câu trả lời.
    window = grounding.normalize(text[max(0, start - 120) : end + 120])
    for idx in candidates:
        label = grounding.normalize(citation_label(citations[idx], idx))
        if label and label in window:
            return idx
    return candidates[0]


def _budget_label(text: str, start: int, end: int) -> str:
    window = text[max(0, start - _BUDGET_LOOKBEHIND_CHARS) : end + _BUDGET_LOOKAHEAD_CHARS]
    if _BUDGET_CONTEXT_RE.search(window):
        return "ngân sách anh/chị nhập"
    return "số anh/chị nhập"


def _is_bold(text: str, start: int, end: int) -> bool:
    return text[max(0, start - 2) : start] == "**" and text[end : end + 2] == "**"


def annotate_reply(
    reply: str,
    citations: list[dict[str, Any]] | None = None,
    *,
    question: str = "",
) -> AnchoredReply:
    """Gắn mỏ neo `[n]` cho mọi con số có nguồn; nhãn riêng cho số do Sale nhập.

    Trả về câu trả lời đã sửa + danh sách mỏ neo. Hàm thuần, không phụ thuộc LLM.
    """
    text = str(reply or "")
    citations = list(citations or [])
    if not text.strip():
        return AnchoredReply(text=text)

    # Gỡ mỏ neo LLM tự gõ (có thể sai số thứ tự) rồi đánh lại bằng máy.
    text = _EXISTING_ANCHOR_RE.sub("", text)

    citation_numbers = [_citation_numbers(c) for c in citations]
    question_numbers = set(verifier._money_values(question or ""))

    # Thu thập mọi "claim" theo thứ tự xuất hiện: (start, end, raw, value)
    claims: list[tuple[int, int, str, float]] = []
    for match in verifier._MONEY_RE.finditer(text):
        raw, unit = match.group(1), match.group(2)
        value = verifier._to_float(raw)
        if value is None:
            continue
        unit_key = grounding.normalize(unit)
        if unit_key in ("ty", "ty."):
            value *= 1_000_000_000
        elif unit_key in ("trieu", "tr", "tr."):
            value *= 1_000_000
        claims.append((match.start(), match.end(), match.group(0).strip(), value))
    for match in verifier._PERCENT_RE.finditer(text):
        value = verifier._to_float(match.group(1))
        if value is None:
            continue
        claims.append((match.start(), match.end(), match.group(0).strip(), value))
    for match in verifier._POLICY_ID_RE.finditer(text):
        claims.append((match.start(), match.end(), match.group(0).strip(), float("nan")))
    claims.sort(key=lambda c: c[0])

    anchors: list[Anchor] = []
    labeled: list[str] = []
    #: (value, citation_index) → số mỏ neo, để cùng số + cùng nguồn dùng lại một nhãn.
    assigned: dict[tuple[float, int], int] = {}
    #: Số của Sale đã gắn nhãn chưa (chỉ gắn nhãn ở lần xuất hiện đầu).
    labeled_values: set[float] = set()
    out: list[str] = []
    cursor = 0

    for start, end, raw, value in claims:
        if start < cursor:  # chồng lấn (hiếm) — bỏ qua để không phá chuỗi
            continue
        piece = text[start:end]

        # 1) Số do Sale nêu trong câu hỏi → in đậm + nhãn, KHÔNG gắn mỏ neo.
        if not _is_number_nan(value) and question_numbers and _matches(value, question_numbers):
            # Nếu LLM đã bọc `**…**` quanh con số, nuốt luôn hai dấu đó để nhãn nằm NGOÀI phần in đậm
            # (tránh sinh `**2 tỷ (nhãn)**` hoặc `****`).
            if _is_bold(text, start, end):
                start, end = max(0, start - 2), end + 2
            rendered = f"**{piece}**"
            # Không chèn nhãn khi con số vốn đã nằm trong ngoặc sẵn (ví dụ dòng Observation viết
            # "tối đa 2.000.000.000 ₫ (giá niêm yết trước thuế)") — chèn thêm sẽ thành hai ngoặc
            # lồng nhau, đọc rất rối.
            window_before = text[max(0, start - 60) : start]
            in_parentheses = window_before.rfind("(") > window_before.rfind(")")
            # Cũng bỏ qua khi NGAY SAU số đã là một ngoặc sẵn (ví dụ "tối đa X (giá niêm yết trước thuế)"),
            # chèn thêm sẽ thành hai ngoặc lồng nhau.
            if text[end : end + 3].startswith(" ("):
                in_parentheses = True
            if value not in labeled_values and not in_parentheses:
                label = _budget_label(text, start, end)
                rendered += f" ({label})"
                labeled_values.add(value)
                labeled.append(piece)
            out.append(text[cursor:start])
            out.append(rendered)
            cursor = end
            continue

        # 2) Con số/mã có nguồn → gắn mỏ neo.
        citation_index: int | None = None
        if _is_number_nan(value):
            normalized = grounding.normalize(piece)
            for idx, citation in enumerate(citations):
                if normalized in grounding.normalize(_citation_blob(citation)):
                    citation_index = idx
                    break
        else:
            citation_index = _find_citation(value, citations, citation_numbers, text, start, end)

        if citation_index is None:
            continue  # không có nguồn → để tầng cảnh báo nội bộ xử lý

        key = (value, citation_index)
        if key not in assigned:
            assigned[key] = len(assigned) + 1
            anchors.append(
                Anchor(
                    index=assigned[key],
                    value=piece,
                    citation_index=citation_index,
                    label=citation_label(citations[citation_index], citation_index),
                )
            )
        out.append(text[cursor:start])
        out.append(f"{piece}[{assigned[key]}]")
        cursor = end

    out.append(text[cursor:])
    return AnchoredReply(text="".join(out), anchors=anchors, labeled_inputs=labeled)


def _is_number_nan(value: float) -> bool:
    return value != value  # noqa: PLR0124 — NaN check cố ý (không dùng math.isnan cho gọn)


__all__ = ["Anchor", "AnchoredReply", "annotate_reply", "citation_label"]
