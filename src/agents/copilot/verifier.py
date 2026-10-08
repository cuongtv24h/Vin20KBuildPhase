"""Verifier — kiểm tra câu trả lời cuối có vượt quá Observation hay không.

Prompt chỉ là "luật chơi"; nó không đảm bảo LLM tuân thủ. Verifier bổ sung tầng kiểm tra bằng
máy: mọi **số liệu tiền tệ**, **tỷ lệ phần trăm** và **mã văn bản chính sách** xuất hiện trong
câu trả lời phải tồn tại trong Observation của tool. Nếu không → gắn cờ `verified=False` và
thêm cảnh báo cho Sale, KHÔNG âm thầm trả lời như thật.

Thiết kế cố tình "dễ tha, khó bỏ sót":
- So khớp số theo giá trị số học (8% ≈ 8.0%, 4.200.000.000 ≈ 4200000000) nên không bắt lỗi oan
  vì định dạng.
- Chỉ kiểm những con số mang đơn vị/có ý nghĩa tài chính; bỏ qua số thứ tự ("bước 2", "3 phương
  án") vì chúng không phải khẳng định về dữ liệu.
- **Số do chính người dùng nêu trong câu hỏi** ("khách có 2 tỷ") được coi là đã biết: câu trả lời
  nhắc lại con số đó không phải là bịa. Trước đây luật này thiếu nên mọi câu trả lời hợp lệ có nhắc
  lại ngân sách của Sale đều bị gắn cờ "có số liệu chưa đối chiếu được" — báo động giả, làm mất
  lòng tin vào cảnh báo thật.
- Ngoài số liệu, không phán xét văn phong.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from src.agents.copilot import grounding

# 4.200.000.000 ₫ · 4,2 tỷ · 72,5 m² · 8% · 95%
_MONEY_RE = re.compile(
    r"(\d{1,3}(?:[.,]\d{3})+|\d+(?:[.,]\d+)?)\s*(tỷ|ty|triệu|trieu|tr|VNĐ|VND|₫|đồng|dong)(?!\w)",
    re.IGNORECASE,
)
_PERCENT_RE = re.compile(r"(\d+(?:[.,]\d+)?)\s*%")
_POLICY_ID_RE = re.compile(r"\b(CSBH-[A-Z0-9.\-]+|FCS[\s-]?v?\d+(?:\.\d+)?)\b", re.IGNORECASE)

# Số không mang tính khẳng định dữ liệu (số bước, số phương án, m² đã có trong observation)
_IGNORED_PERCENT = {"0", "1", "2", "3", "100"}


@dataclass
class VerificationResult:
    """Kết quả kiểm chứng câu trả lời."""

    verified: bool = True
    unsupported: list[str] = field(default_factory=list)
    #: Số xuất hiện trong câu trả lời **và** trong câu hỏi của Sale (ngân sách, số phòng ngủ đã nêu…):
    #: không tính là số liệu bịa, nhưng vẫn ghi lại để đối chiếu khi cần.
    echoed: list[str] = field(default_factory=list)
    #: Số/mã lấy từ **bối cảnh canonical** (dải giá giỏ hàng, mã chính sách đang hiệu lực) — nguồn hệ thống.
    from_context: list[str] = field(default_factory=list)
    checked: int = 0
    reason: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "verified": self.verified,
            "unsupported_claims": self.unsupported[:5],
            "echoed_claims": self.echoed[:5],
            "context_claims": self.from_context[:5],
            "checked_claims": self.checked,
            "reason": self.reason,
        }


def _to_float(raw: str) -> float | None:
    """Chuẩn hóa số kiểu Việt Nam: '.' là phân cách nghìn, ',' là phân cách thập phân.

    Quy ước dữ liệu của hệ thống (vnđ/tỷ lệ) luôn format theo kiểu VN, nên:
    - "4.655.200.000" → 4655200000 (mọi nhóm sau dấu chấm đều đúng 3 chữ số)
    - "8.0" / "72,5"  → 8.0 / 72.5 (dấu chấm/comma đóng vai trò thập phân)
    """
    token = raw.replace(" ", "")
    if not token:
        return None
    if "," in token and "." in token:
        if token.rfind(",") > token.rfind("."):
            token = token.replace(".", "").replace(",", ".")
        else:
            token = token.replace(",", "")
    elif "," in token:
        token = token.replace(",", ".")
    elif "." in token:
        parts = token.split(".")
        if len(parts) > 1 and all(len(part) == 3 for part in parts[1:]):
            token = "".join(parts)
    try:
        return float(token)
    except ValueError:
        return None


def _money_values(text: str) -> list[float]:
    """Trích mọi giá trị tiền tệ trong một đoạn, đã quy đổi về VNĐ (4,2 tỷ → 4.2e9)."""
    values: list[float] = []
    for raw, unit in _MONEY_RE.findall(text or ""):
        value = _to_float(raw)
        if value is None:
            continue
        unit_key = grounding.normalize(unit)
        if unit_key in ("ty", "ty."):
            value *= 1_000_000_000
        elif unit_key in ("trieu", "tr", "tr."):
            value *= 1_000_000
        values.append(value)
    for raw in _PERCENT_RE.findall(text or ""):
        if (value := _to_float(raw)) is not None:
            values.append(value)
    # Số trần dạng nhóm nghìn (ví dụ "4.200.000.000" xuất hiện không kèm đơn vị)
    for raw in re.findall(r"\d{1,3}(?:\.\d{3}){2,}", text or ""):
        if (value := _to_float(raw)) is not None:
            values.append(value)
    return values


def _observation_numbers(observations: list[dict[str, Any]]) -> tuple[set[float], str]:
    """Trích tập giá trị số + toàn văn observation (đã chuẩn hóa) để đối chiếu.

    Dùng CHUNG `_money_values` với phía câu trả lời để "200 triệu" trong reply và
    "200.000.000 ₫" trong observation quy về cùng một giá trị.
    """
    blob_parts: list[str] = []
    for obs in observations:
        for key in ("summary", "draft_text", "recommended", "sanity_passed"):
            value = obs.get(key)
            if value:
                blob_parts.append(str(value))
        for citation in obs.get("citations") or []:
            blob_parts.append(str(citation.get("quote") or ""))
            blob_parts.append(str(citation.get("section") or ""))
            blob_parts.append(str(citation.get("policy_id") or ""))
    blob = " \n ".join(blob_parts)
    return set(_money_values(blob)), grounding.normalize(blob)


def _claim_matches(value: float, known: set[float]) -> bool:
    """Khớp theo giá trị tuyệt đối hoặc theo tỷ lệ (1.5% vs 0.015)."""
    for candidate in known:
        if abs(candidate - value) < 1e-6:
            return True
        if candidate and abs(candidate * 100 - value) < 1e-6:
            return True
        if abs(candidate - value * 100) < 1e-6:
            return True
    return False


def has_data_claims(text: str) -> bool:
    """Câu trả lời có khẳng định SỐ LIỆU không (tiền, %, mã chính sách)?

    Dùng cho trường hợp LLM trả lời trực tiếp mà KHÔNG gọi tool nào (câu hỏi kiểu định nghĩa/quy trình
    — xem `prompts.build_system_prompt`). Khi đó không có observation để `verify_reply` đối chiếu, nên
    cần cách nhẹ hơn để biết câu trả lời có đang nói về số liệu chính sách/giá hay không: nếu có thì
    vẫn phải nhắc Sale là chưa đối chiếu, còn văn xuôi thuần thì để yên.
    """
    if _MONEY_RE.search(text or "") or _POLICY_ID_RE.search(text or ""):
        return True
    return any(raw not in _IGNORED_PERCENT for raw in _PERCENT_RE.findall(text or ""))


def verify_reply(
    reply: str,
    observations: list[dict[str, Any]],
    question: str = "",
    context: str = "",
) -> VerificationResult:
    """Đối chiếu câu trả lời với Observation.

    Hai nguồn được miễn kiểm (vẫn ghi lại để đối chiếu, không tính là bịa):
    - `question`: câu hỏi gốc của Sale — số **người dùng tự nêu** (ngân sách 2 tỷ) được phép nhắc lại.
    - `context`: **dữ liệu canonical** đã nạp vào prompt (chính sách hiệu lực, dải giá giỏ hàng). Đây vẫn
      là số liệu thật của hệ thống; nếu không miễn, mọi câu trả lời dùng đúng dải giá canonical đều bị
      gắn cờ "chưa đối chiếu được" chỉ vì dữ liệu đó đến từ bối cảnh thay vì từ Observation của tool.
      Truyền vào **chỉ** phần canonical (`prompts.canonical_facts`), không truyền phần học từ phản hồi.
    """
    text = reply or ""
    if not text.strip():
        return VerificationResult(verified=False, reason="Câu trả lời rỗng.", checked=0)
    if not observations:
        # Không có observation nào thì không có gì để kiểm; lớp _finalize đã gắn cờ ungrounded.
        return VerificationResult(verified=True, reason="Không có observation để đối chiếu.", checked=0)

    known_numbers, blob_norm = _observation_numbers(observations)
    #: Số Sale tự nêu trong câu hỏi — được phép nhắc lại, không phải "bịa".
    question_numbers = set(_money_values(question or ""))
    #: Số liệu canonical nạp sẵn trong bối cảnh (dải giá giỏ hàng, chính sách hiệu lực) — cũng là dữ liệu thật.
    context_numbers = set(_money_values(context or ""))
    context_norm = grounding.normalize(context or "")
    unsupported: list[str] = []
    echoed: list[str] = []
    from_context: list[str] = []
    checked = 0

    for raw, unit in _MONEY_RE.findall(text):
        value = _to_float(raw)
        if value is None:
            continue
        # Quy đổi "4,2 tỷ" → 4.200.000.000 để so với observation
        unit_key = grounding.normalize(unit)
        if unit_key in ("ty", "ty."):
            value *= 1_000_000_000
        elif unit_key in ("trieu", "tr", "tr."):
            value *= 1_000_000
        checked += 1
        claim = f"{raw} {unit}".strip()
        if _claim_matches(value, question_numbers):
            echoed.append(claim)
        elif _claim_matches(value, context_numbers):
            from_context.append(claim)
        elif not _claim_matches(value, known_numbers):
            unsupported.append(claim)

    for raw in _PERCENT_RE.findall(text):
        if raw in _IGNORED_PERCENT:
            continue
        value = _to_float(raw)
        if value is None or not known_numbers:
            continue
        checked += 1
        if _claim_matches(value, question_numbers):
            echoed.append(f"{raw}%")
        elif _claim_matches(value, context_numbers):
            from_context.append(f"{raw}%")
        elif not _claim_matches(value, known_numbers):
            unsupported.append(f"{raw}%")

    for policy_id in _POLICY_ID_RE.findall(text):
        checked += 1
        normalized = grounding.normalize(policy_id)
        if normalized in blob_norm:
            continue
        if context_norm and normalized in context_norm:
            # Mã chính sách đang hiệu lực đã nạp ở bối cảnh — vẫn là nguồn hệ thống.
            from_context.append(policy_id)
            continue
        unsupported.append(policy_id)

    if not unsupported:
        reason = "Mọi số liệu đều có trong Observation."
        if echoed:
            reason += f" ({len(echoed)} số do người dùng nêu trong câu hỏi.)"
        if from_context:
            reason += f" ({len(from_context)} số/mã lấy từ bối cảnh hệ thống.)"
        return VerificationResult(
            verified=True,
            echoed=sorted(set(echoed)),
            from_context=sorted(set(from_context)),
            checked=checked,
            reason=reason,
        )

    return VerificationResult(
        verified=False,
        unsupported=sorted(set(unsupported)),
        echoed=sorted(set(echoed)),
        from_context=sorted(set(from_context)),
        checked=checked,
        reason="Có số liệu/mã văn bản không xuất hiện trong Observation của tool.",
    )


__all__ = ["VerificationResult", "verify_reply"]
