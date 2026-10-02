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
    checked: int = 0
    reason: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "verified": self.verified,
            "unsupported_claims": self.unsupported[:5],
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


def verify_reply(reply: str, observations: list[dict[str, Any]]) -> VerificationResult:
    """Đối chiếu câu trả lời với Observation."""
    text = reply or ""
    if not text.strip():
        return VerificationResult(verified=False, reason="Câu trả lời rỗng.", checked=0)
    if not observations:
        # Không có observation nào thì không có gì để kiểm; lớp _finalize đã gắn cờ ungrounded.
        return VerificationResult(verified=True, reason="Không có observation để đối chiếu.", checked=0)

    known_numbers, blob_norm = _observation_numbers(observations)
    unsupported: list[str] = []
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
        if not _claim_matches(value, known_numbers):
            unsupported.append(f"{raw} {unit}".strip())

    for raw in _PERCENT_RE.findall(text):
        if raw in _IGNORED_PERCENT:
            continue
        value = _to_float(raw)
        if value is None or not known_numbers:
            continue
        checked += 1
        if not _claim_matches(value, known_numbers):
            unsupported.append(f"{raw}%")

    for policy_id in _POLICY_ID_RE.findall(text):
        checked += 1
        if grounding.normalize(policy_id) not in blob_norm:
            unsupported.append(policy_id)

    if not unsupported:
        return VerificationResult(verified=True, checked=checked, reason="Mọi số liệu đều có trong Observation.")

    return VerificationResult(
        verified=False,
        unsupported=sorted(set(unsupported)),
        checked=checked,
        reason="Có số liệu/mã văn bản không xuất hiện trong Observation của tool.",
    )


__all__ = ["VerificationResult", "verify_reply"]
