"""Bóc tách ý định + thực thể tiếng Việt cho Sales Copilot (lớp offline/fallback).

Vai trò:
1. Khi LLM không khả dụng (mất mạng, hết quota, demo offline) — vẫn hiểu lệnh Sale.
2. Khi LLM trả lời nhưng quên chèn Smart Card — sinh thẻ hành động từ luật tất định.

Đây KHÔNG phải bộ não chính: bộ não là ReAct loop (LLM + tools). Lớp này chỉ đảm bảo
hệ thống không bao giờ "chết lặng" trước một câu lệnh nghiệp vụ rõ ràng.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from src.agents.copilot import grounding

INTENT_CREATE_CUSTOMER = "smart_customer_create"
INTENT_CREATE_QUOTE = "smart_quote_create"
INTENT_COMPARE_SCENARIOS = "smart_scenario_compare"
INTENT_BROWSE_UNITS = "smart_units_browse"
#: Hỏi/đánh giá **vốn tự có** (đòn bẩy tài chính) — chốt P1.4: khác với "tính phương án"
#: (bảng dòng tiền chi tiết). Chỉ trả mốc tổng quan (P1.2).
INTENT_ASSESS_FUNDS = "assess_own_funds"
INTENT_COMPOSE_MESSAGE = "smart_compose_message"
INTENT_LOOKUP_POLICY = "lookup_policy"
INTENT_LOOKUP_CUSTOMER = "lookup_customer"
INTENT_CHECK_F8 = "check_f8_compliance"
INTENT_SMALL_TALK = "small_talk"

_UNIT_CODE_RE = re.compile(r"\b([A-Z]{2,4}-[A-Z0-9]{1,3}-\d{3,4}|[A-Z]{1,3}-\d{2}\.\d{2})\b", re.IGNORECASE)
_PHONE_RE = re.compile(r"0\d{9,10}")
_NAME_STRIP_PREFIX = re.compile(
    r"^(?:tạo|thêm|mở|nhập|lưu|đăng\s*ký)?\s*(?:khách(?:\s*hàng)?(?:\s*mới)?|lead|hồ\s*sơ)\s*",
    re.IGNORECASE,
)
_NAME_STRIP_FILLER = re.compile(r"^(?:mới\s+tên|mới\s+là|tên\s+là|tên|mới|anh|chị|ông|bà|khách\s*hàng)\s*", re.IGNORECASE)
_AMOUNT_RE = re.compile(r"(\d+(?:[.,]\d+)?)\s*(tỷ|ty|triệu|trieu|tr)\b", re.IGNORECASE)


@dataclass
class IntentResult:
    """Kết quả bóc tách tất định từ câu lệnh Sale."""

    intent: str
    confidence: float
    entities: dict[str, Any] = field(default_factory=dict)
    matched_keywords: list[str] = field(default_factory=list)


def _has(text: str, *keywords: str) -> list[str]:
    """So khớp từ khóa trên văn bản đã bỏ dấu (tự chuẩn hóa cả từ khóa)."""
    return [k for k in keywords if grounding.normalize(k) in text]


def extract_amount(text: str) -> int | None:
    match = _AMOUNT_RE.search(text)
    if not match:
        return None
    value = float(match.group(1).replace(",", "."))
    unit = match.group(2).lower()
    multiplier = 1_000_000_000 if unit in ("tỷ", "ty") else 1_000_000
    return int(value * multiplier)


def extract_name(text: str) -> str:
    """Bóc họ tên khách khỏi câu lệnh tự nhiên (loại bỏ từ đệm & SĐT)."""
    cleaned = _NAME_STRIP_PREFIX.sub("", text).strip()
    cleaned = _NAME_STRIP_FILLER.sub("", cleaned).strip()
    phone = _PHONE_RE.search(cleaned)
    if phone and phone.start() > 0:
        cleaned = cleaned[: phone.start()].strip()
    else:
        cleaned = cleaned.split(",")[0].split(";")[0].strip()
    cleaned = re.sub(r"[,;:\-]?\s*(?:sđt|sdt|phone|điện\s*thoại)\s*$", "", cleaned, flags=re.IGNORECASE).strip()
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" ,;:-")
    if len(cleaned) < 2 or grounding.normalize(cleaned) in {
        "moi",
        "khach",
        "khach hang",
        "khach moi",
        "anh",
        "chi",
        "lead",
        "ho so",
    }:
        return ""
    # Chỉ nhận tên có chữ cái (tránh nuốt cả câu dài)
    if len(cleaned.split()) > 6:
        return ""
    return cleaned


def extract_unit_code(text: str) -> str | None:
    match = _UNIT_CODE_RE.search(text)
    return match.group(1).upper() if match else None


def extract_bedrooms(text: str) -> int | None:
    match = re.search(r"(\d)\s*(?:pn|phòng\s*ngủ|phong\s*ngu|ngủ|ngu|br)\b", text, re.IGNORECASE)
    if match:
        return int(match.group(1))
    if "studio" in grounding.normalize(text):
        return 1
    return None


def extract_project_id(text: str) -> str | None:
    norm = grounding.normalize(text)
    if any(k in norm for k in ("zen park", "zenpark", "the zen park")):
        return "THE_ZEN_PARK"
    if any(k in norm for k in ("sapphire", "vland sapphire", "vlandfuture sapphire")):
        return "VLANDFUTURE_SAPPHIRE"
    if any(k in norm for k in ("riverside", "vland riverside", "vland future riverside")):
        return "PROJECT-VLF-001"
    unit = extract_unit_code(text)
    if unit:
        if unit.startswith("ZEN-"):
            return "THE_ZEN_PARK"
        if unit.startswith("SAP-"):
            return "VLANDFUTURE_SAPPHIRE"
        if unit.startswith(("R-", "G-", "SH-")):
            return "PROJECT-VLF-001"
    return None


def detect_intent(text: str) -> IntentResult:
    """Nhận diện ý định nghiệp vụ theo thứ tự ưu tiên (luật tất định, không gọi LLM)."""
    from src.agents.copilot import memory

    lower = grounding.normalize(text)
    slots = memory.extract_slots_from_text(text)
    entities: dict[str, Any] = {
        "unit_code": extract_unit_code(text),
        "bedrooms": extract_bedrooms(text),
        "amount_vnd": extract_amount(text),
        "project_id": extract_project_id(text),
        "transaction_date": slots.get("transaction_date"),
    }

    # Mã hồ sơ rõ ràng (DOS-000123 / LD-2026-001) — không thể nhầm với ý định khác.
    if re.search(r"\b(?:DOS|LD)-[A-Z0-9-]{3,}\b", text, re.IGNORECASE):
        entities["customer_name"] = ""
        return IntentResult(INTENT_LOOKUP_CUSTOMER, 0.95, entities, ["dossier_id"])

    kw = _has(lower, "tạo khách", "thêm khách", "khách mới", "nhập khách", "lưu khách", "đăng ký khách", "tạo lead")
    if kw:
        entities["customer_name"] = extract_name(text)
        phone = _PHONE_RE.search(text)
        entities["customer_phone"] = phone.group(0) if phone else ""
        return IntentResult(INTENT_CREATE_CUSTOMER, 0.9, entities, kw)

    kw = _has(
        lower,
        "vốn tự có",
        "von tu co",
        "vốn ban đầu",
        "von ban dau",
        "đòn bẩy",
        "don bay",
        "tỷ lệ vay",
        "mua được không",
        "mua duoc khong",
    )
    # Chốt bảo vệ: nếu Sale nói rõ muốn **bảng dòng tiền / tính phương án / báo giá** thì đó vẫn là
    # yêu cầu tính chi tiết — đừng kéo về đánh giá tổng quan vốn tự có (P1.2 chỉ áp cho câu hỏi khái quát).
    wants_detail = _has(
        lower,
        "dòng tiền",
        "tính phương án",
        "các phương án",
        "so sánh",
        "bảng tính vay",
        "bảng dòng tiền",
        "báo giá",
        "lịch thanh toán",
    )
    if kw and not wants_detail:
        return IntentResult(INTENT_ASSESS_FUNDS, 0.8, entities, kw)

    kw = _has(lower, "tạo báo giá", "lập báo giá", "ra báo giá", "tính giá", "báo giá")
    if kw:
        if any(w in lower for w in ("so sánh", "đối chiếu")):
            return IntentResult(INTENT_COMPARE_SCENARIOS, 0.85, entities, kw)
        return IntentResult(INTENT_CREATE_QUOTE, 0.85, entities, kw)

    kw = _has(
        lower,
        "so sánh",
        "các phương án",
        "phương án nào",
        "phương án thanh toán",
        "tính phương án",
        "dòng tiền",
        "tính dòng tiền",
        "lịch thanh toán",
        # Chip hành động nhanh (K4) — Sale bấm là gửi đúng câu này vào khung chat.
        "bảng tính vay",
        "phương án vay",
        "bảng dòng tiền",
        "xem bảng tính",
    )
    if kw:
        return IntentResult(INTENT_COMPARE_SCENARIOS, 0.8, entities, kw)

    kw = _has(lower, "soạn tin", "tin nhắn", "nhắn cho khách", "nhắn zalo", "viết tin")
    if kw:
        return IntentResult(INTENT_COMPOSE_MESSAGE, 0.8, entities, kw)

    kw = _has(
        lower,
        "tra cứu căn",
        "tìm căn",
        "giỏ hàng",
        "danh sách căn",
        "căn 2 ngủ",
        "căn 1 ngủ",
        "căn 3 ngủ",
        "căn hộ trống",
        "rổ hàng",
        "thông tin căn",
        "còn căn",
        "các căn",
        "đang mở bán",
        "liệt kê căn",
        "gửi danh sách",
        "mở rộng sang",
        "lọc sang",
    )
    if kw:
        return IntentResult(INTENT_BROWSE_UNITS, 0.8, entities, kw)

    kw = _has(lower, "tìm khách", "tra cứu khách", "hồ sơ khách", "số điện thoại", "mã hồ sơ")
    if kw:
        return IntentResult(INTENT_LOOKUP_CUSTOMER, 0.75, entities, kw)

    kw = _has(
        lower,
        "phát ngôn này",
        "có vi phạm",
        "vi phạm không",
        "gửi khách được chưa",
        "gửi được chưa",
        "có gửi được",
        "f8",
        "tuân thủ",
        "kiểm tra phát ngôn",
    )
    if kw:
        return IntentResult(INTENT_CHECK_F8, 0.8, entities, kw)

    kw = _has(lower, "chính sách", "chiết khấu", "quy định", "p09", "hiệu lực", "áp dụng")
    if kw:
        return IntentResult(INTENT_LOOKUP_POLICY, 0.7, entities, kw)

    return IntentResult(INTENT_SMALL_TALK, 0.3, entities, [])


def build_action_card(text: str, result: IntentResult, context: dict[str, Any] | None = None) -> dict[str, Any] | None:
    """Sinh Smart Card payload tương thích hợp đồng UI hiện tại (action_type/action_data)."""
    context = context or {}
    current_unit = context.get("current_unit")
    unit = result.entities.get("unit_code") or current_unit or "ZEN-A-1205"

    if result.intent == INTENT_CREATE_CUSTOMER:
        name = result.entities.get("customer_name") or ""
        own_funds = result.entities.get("amount_vnd") or 1_500_000_000
        return {
            "action_type": INTENT_CREATE_CUSTOMER,
            "action_data": {
                "customer_name": name,
                "customer_phone": result.entities.get("customer_phone") or "",
                "preferred_unit_code": unit,
                "own_funds_vnd": own_funds,
                "bedrooms": result.entities.get("bedrooms"),
                "needs_summary": f"Khách {name or 'mới'} quan tâm căn {unit}, vốn dự kiến {grounding.format_vnd(own_funds)}.",
            },
        }
    if result.intent == INTENT_CREATE_QUOTE:
        scenario = "PA-NHANH" if _has(grounding.normalize(text), "sớm", "nhanh", "chiết khấu") else (
            "PA-VAY" if _has(grounding.normalize(text), "vay", "lãi", "ngân hàng") else "PA-CHUDONG"
        )
        return {"action_type": INTENT_CREATE_QUOTE, "action_data": {"unit_code": unit, "scenario": scenario}}
    if result.intent == INTENT_COMPARE_SCENARIOS:
        return {"action_type": INTENT_COMPARE_SCENARIOS, "action_data": {"unit_code": unit}}
    if result.intent == INTENT_ASSESS_FUNDS:
        return {
            "action_type": INTENT_ASSESS_FUNDS,
            "action_data": {
                "unit_code": unit,
                "own_funds_vnd": result.entities.get("amount_vnd") or 0,
                "bedrooms": result.entities.get("bedrooms"),
            },
        }
    if result.intent == INTENT_BROWSE_UNITS:
        return {
            "action_type": INTENT_BROWSE_UNITS,
            "action_data": {"bedrooms": result.entities.get("bedrooms"), "max_price_vnd": result.entities.get("amount_vnd")},
        }
    if result.intent == INTENT_COMPOSE_MESSAGE:
        return None  # nội dung do tool soạn tin trả về
    return None
