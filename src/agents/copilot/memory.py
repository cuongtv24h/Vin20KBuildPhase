"""Bộ nhớ phiên cho Sales Copilot — slot ngữ cảnh + tóm tắt hội thoại.

Hai vấn đề được giải quyết:

1. **Sale nói thiếu ngữ cảnh.** Câu trước nói "căn ZEN-A-1205", câu sau nói "tính phương án đi
   em" — Copilot phải nhớ căn nào. `resolve_slots()` quét lịch sử hội thoại để điền các slot
   (`current_unit`, `lead_dossier_id`, `transaction_date`) mà lượt hiện tại không nêu lại.

2. **Hội thoại dài làm phình prompt.** `summarize_history()` nén phần cũ thành các dòng sự kiện
   ngắn (đã hỏi gì · đã tra được gì · slot nào đã chốt) và chỉ giữ vài lượt gần nhất nguyên văn.

Toàn bộ tất định, không gọi LLM — chạy được ở chế độ offline.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from src.agents.copilot import grounding

SLOT_KEYS = ("current_unit", "lead_dossier_id", "transaction_date")

_UNIT_RE = re.compile(r"\b([A-Z]{2,4}-[A-Z0-9]{1,3}-\d{3,4}|[A-Z]{1,3}-\d{2}\.\d{2})\b", re.IGNORECASE)
_DOSSIER_RE = re.compile(r"\b(DOS-\d{4,8}|LD-\d{4}-\d{3,6})\b", re.IGNORECASE)
_DATE_RE = re.compile(r"\b(20\d{2})-(\d{2})-(\d{2})\b")
_DATE_VN_RE = re.compile(r"\b(\d{1,2})/(\d{1,2})/(20\d{2})\b")

MAX_KEEP_VERBATIM = 6
MAX_HISTORY_SUMMARIZED = 40


@dataclass
class SessionSlots:
    """Ngữ cảnh đã chốt trong phiên làm việc."""

    current_unit: str | None = None
    lead_dossier_id: str | None = None
    transaction_date: str | None = None
    sources: dict[str, str] = field(default_factory=dict)

    def filled_from_history(self) -> list[str]:
        return [k for k, v in self.sources.items() if v == "history" and getattr(self, k)]

    def as_dict(self) -> dict[str, str | None]:
        return {k: getattr(self, k) for k in SLOT_KEYS}


def _valid_date(year: str, month: str, day: str) -> str | None:
    try:
        from datetime import date as _date

        return _date(int(year), int(month), int(day)).isoformat()
    except ValueError:
        return None


def extract_slots_from_text(text: str) -> dict[str, str]:
    """Bóc slot xuất hiện trong một đoạn văn bản (ưu tiên giá trị xuất hiện SAU = mới hơn)."""
    found: dict[str, str] = {}
    unit = _UNIT_RE.search(text or "")
    if unit:
        found["current_unit"] = unit.group(1).upper()
    dossier = _DOSSIER_RE.search(text or "")
    if dossier:
        found["lead_dossier_id"] = dossier.group(1).upper()
    iso = _DATE_RE.search(text or "")
    if iso and (valid := _valid_date(iso.group(1), iso.group(2), iso.group(3))):
        found["transaction_date"] = valid
    else:
        vn = _DATE_VN_RE.search(text or "")
        if vn and (valid := _valid_date(vn.group(3), vn.group(2), vn.group(1))):
            found["transaction_date"] = valid
    return found


def resolve_slots(
    *,
    current_unit: str | None = None,
    lead_dossier_id: str | None = None,
    transaction_date: str | None = None,
    message: str = "",
    history: list[dict[str, str]] | None = None,
) -> SessionSlots:
    """Gộp ngữ cảnh: tham số lượt hiện tại > lịch sử > câu lệnh hiện tại."""
    slots = SessionSlots()
    sources: dict[str, str] = {}

    explicit = {
        "current_unit": current_unit,
        "lead_dossier_id": lead_dossier_id,
        "transaction_date": transaction_date,
    }
    for key, value in explicit.items():
        if value:
            setattr(slots, key, str(value))
            sources[key] = "request"

    # Quét lịch sử từ cũ → mới để giá trị mới nhất thắng
    for item in (history or [])[:MAX_HISTORY_SUMMARIZED]:
        if str(item.get("role", "")).lower() not in ("user", "assistant", "agent"):
            continue
        for key, value in extract_slots_from_text(str(item.get("content", "") or "")).items():
            if not getattr(slots, key):
                setattr(slots, key, value)
                sources.setdefault(key, "history")

    # Câu lệnh hiện tại luôn mới nhất
    for key, value in extract_slots_from_text(message).items():
        setattr(slots, key, value)
        sources[key] = "message"

    slots.sources = sources
    return slots


def summarize_history(history: list[dict[str, str]] | None, *, keep_verbatim: int = MAX_KEEP_VERBATIM) -> str:
    """Nén phần hội thoại cũ thành khối sự kiện ngắn gọn cho prompt.

    Phần `keep_verbatim` lượt gần nhất KHÔNG nằm trong bản tóm tắt (được đưa nguyên văn vào
    messages), nên hàm này chỉ mô tả phần xa hơn.
    """
    items = [i for i in (history or []) if str(i.get("content", "")).strip()]
    older = items[:-keep_verbatim] if keep_verbatim and len(items) > keep_verbatim else []
    if not older:
        return ""

    lines: list[str] = []
    for item in older[-MAX_HISTORY_SUMMARIZED:]:
        role = "Sale" if str(item.get("role", "")).lower() == "user" else "Copilot"
        text = re.sub(r"\s+", " ", str(item.get("content", ""))).strip()
        if len(text) > 160:
            text = text[:157] + "…"
        lines.append(f"- {role}: {text}")

    slots = resolve_slots(history=older)
    slot_line = ", ".join(f"{k}={v}" for k, v in slots.as_dict().items() if v)
    summary = "TÓM TẮT HỘI THOẠI TRƯỚC ĐÓ:\n" + "\n".join(lines)
    if slot_line:
        summary += f"\nNGỮ CẢNH ĐÃ CHỐT: {slot_line}"
    return summary


def enrich_entity_with_slots(entity: dict, slots: SessionSlots) -> dict:
    """Điền slot vào entity của intent nếu câu lệnh hiện tại chưa nêu."""
    merged = dict(entity or {})
    if not merged.get("unit_code") and slots.current_unit:
        merged["unit_code"] = slots.current_unit
        merged["unit_code_from"] = "memory"
    if not merged.get("transaction_date") and slots.transaction_date:
        merged["transaction_date"] = slots.transaction_date
    if slots.lead_dossier_id:
        merged.setdefault("lead_dossier_id", slots.lead_dossier_id)

    # Bổ sung ràng buộc khách nếu đã biết (giúp tool tính phương án đúng ngữ cảnh)
    if slots.current_unit and not grounding.find_unit(str(merged.get("unit_code"))):
        merged["unit_code"] = slots.current_unit
    return merged


__all__ = [
    "MAX_KEEP_VERBATIM",
    "SLOT_KEYS",
    "SessionSlots",
    "enrich_entity_with_slots",
    "extract_slots_from_text",
    "resolve_slots",
    "summarize_history",
]
