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
#: Soạn HỒ SƠ ĐỀ XUẤT trình Quản lý (hồ sơ + checklist còn thiếu) — dùng tool `soan_ho_so_de_xuat`.
#: Khác INTENT_COMPOSE_MESSAGE (tin nhắn gửi khách): đây là bản đề xuất NỘI BỘ để trình duyệt.
INTENT_COMPOSE_PROPOSAL = "compose_proposal"
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

#: Khoảng giá Sale nêu: "từ 3 tỷ đến 5 tỷ", "3-5 tỷ", "khoảng 2 đến 3 tỷ". Dấu gạch chỉ tính là khoảng khi
#: mốc SAU nó là con số (tránh nhầm "3 tỷ - vốn tự có").
_RANGE_SEP = r"(?:đến|tới|->|–|—|-|~)"
_AMOUNT_RANGE_RES = (
    re.compile(
        # Mốc đầu có thể thiếu đơn vị ("3-5 tỷ") nhưng mốc CUỐI phải có đơn vị — nếu không thì "2PN - 3 tỷ"
        # cũng bị coi là khoảng giá.
        rf"\b(\d+(?:[.,]\d+)?)\s*(tỷ|ty|triệu|trieu|tr)?\s*{_RANGE_SEP}\s*(\d+(?:[.,]\d+)?)\s*(tỷ|ty|triệu|trieu|tr)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\btừ\s*(\d+(?:[.,]\d+)?)\s*(tỷ|ty|triệu|trieu|tr)\s*(?:đến|tới)\s*(\d+(?:[.,]\d+)?)\s*(tỷ|ty|triệu|trieu|tr)?\b",
        re.IGNORECASE,
    ),
)


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


def _amount_value(raw: str, unit: str | None) -> int:
    value = float(str(raw).replace(",", "."))
    multiplier = 1_000_000_000 if (unit or "").lower() in ("tỷ", "ty") else 1_000_000
    return int(value * multiplier)


def match_amount_range(text: str) -> tuple[tuple[int, int], tuple[int, int]] | None:
    """Tìm khoảng ngân sách → `((min, max), (vị trí đầu, vị trí cuối))`.

    Trả kèm vị trí để lớp gọi **khoét khoảng ra khỏi câu** trước khi bóc mốc tiền đơn: câu
    "tài chính 2 tỷ, nguyện vọng mua căn từ 3 tỷ đến 5 tỷ" có hai loại số khác nhau (vốn tự có vs ngân sách).
    """
    for pattern in _AMOUNT_RANGE_RES:
        match = pattern.search(text)
        if not match:
            continue
        unit = match.group(2) or match.group(4)
        low = _amount_value(match.group(1), unit)
        high = _amount_value(match.group(3), match.group(4) or unit)
        if low > high:
            low, high = high, low
        if low != high:
            return (low, high), (match.start(), match.end())
    return None


def extract_amount_range(text: str) -> tuple[int, int] | None:
    """Khoảng ngân sách Sale nêu → `(min, max)`; đơn vị của mốc đầu áp cho mốc sau nếu thiếu ("3-5 tỷ").

    Vì sao cần: Sale nói "nguyện vọng mua căn từ 3 tỷ đến 5 tỷ" mà hệ thống chỉ nhớ "2 tỷ" (vốn tự có) thì
    hồ sơ khách mất đúng thông tin quan trọng nhất khi lọc giỏ hàng.
    """
    found = match_amount_range(text)
    return found[0] if found else None


def blank_span(text: str, span: tuple[int, int]) -> str:
    """Thay một đoạn bằng khoảng trắng (giữ nguyên độ dài) — để không bóc lại số trong đoạn đó."""
    start, end = span
    return f"{text[:start]}{' ' * (end - start)}{text[end:]}"


def extract_name(text: str) -> str:
    """Bóc họ tên khách khỏi câu lệnh tự nhiên (loại bỏ từ đệm & SĐT)."""
    cleaned = _NAME_STRIP_PREFIX.sub("", text).strip()
    cleaned = _NAME_STRIP_FILLER.sub("", cleaned).strip()
    phone = _PHONE_RE.search(cleaned)
    if phone and phone.start() > 0:
        cleaned = cleaned[: phone.start()].strip()
    else:
        cleaned = cleaned.split(",")[0].split(";")[0].strip()
    cleaned = re.sub(
        r"[,;:\-]?\s*(?:số\s*(?:điện\s*thoại|đt)?|sđt|sdt|phone|điện\s*thoại)\s*$",
        "",
        cleaned,
        flags=re.IGNORECASE,
    ).strip()
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
    found_range = match_amount_range(text)
    amount_range = found_range[0] if found_range else None
    # "từ 3 tỷ đến 5 tỷ" là KHOẢNG ngân sách — khoét khoảng ra trước khi bóc mốc tiền đơn, nhờ vậy câu
    # "tài chính ban đầu 2 tỷ, nguyện vọng mua căn từ 3 tỷ đến 5 tỷ" giữ được CẢ HAI con số.
    single_amount_text = blank_span(text, found_range[1]) if found_range else text
    entities: dict[str, Any] = {
        "unit_code": extract_unit_code(text),
        "bedrooms": extract_bedrooms(text),
        "amount_vnd": extract_amount(single_amount_text),
        "amount_range_vnd": amount_range,
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

    # Nhánh "hồ sơ đề xuất" phải đứng TRƯỚC nhánh "báo giá": câu "soạn hồ sơ đề xuất rồi lập báo giá
    # trình Quản lý" vừa chứa từ "báo giá" vừa là yêu cầu soạn hồ sơ — nhánh đứng trước quyết định.
    kw = _has(
        lower,
        "hồ sơ đề xuất",
        "đề xuất trình",
        "soạn đề xuất",
        "lập đề xuất",
        "hồ sơ trình duyệt",
        "chuẩn bị hồ sơ",
    )
    if kw:
        return IntentResult(INTENT_COMPOSE_PROPOSAL, 0.85, entities, kw)

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
    #: Mã căn chỉ được lấy từ **ngữ cảnh thật**: câu Sale vừa nói, hoặc slot của phiên/hồ sơ đang mở.
    #: Trước đây hàm này gán cứng `ZEN-A-1205` khi không tìm thấy căn ⇒ thẻ khách hàng tự mọc ra một
    #: "căn hộ quan tâm" mà Sale chưa từng nhắc (lỗi người dùng báo ở đợt 20).
    unit = result.entities.get("unit_code") or current_unit or ""

    if result.intent == INTENT_CREATE_CUSTOMER:
        name = result.entities.get("customer_name") or ""
        # Vốn tự có: CHỈ lấy khi câu Sale nêu đúng một mốc tiền; nếu Sale nêu một KHOẢNG (ngân sách dự
        # kiến) thì không tự quy đổi khoảng đó thành vốn tự có.
        amount_range = result.entities.get("amount_range_vnd")
        own_funds = result.entities.get("amount_vnd")
        needs_bits = [f"Khách {name or 'mới'}"]
        if unit:
            needs_bits.append(f"quan tâm căn {unit}")
        if own_funds:
            needs_bits.append(f"vốn tự có dự kiến {grounding.format_vnd(own_funds)}")
        if amount_range:
            needs_bits.append(
                f"ngân sách dự kiến {grounding.format_vnd(amount_range[0])} – "
                f"{grounding.format_vnd(amount_range[1])}"
            )
        return {
            "action_type": INTENT_CREATE_CUSTOMER,
            "action_data": {
                "customer_name": name,
                "customer_phone": result.entities.get("customer_phone") or "",
                # Để trống khi chưa biết căn — thà trống (Sale tự chọn) hơn là điền một căn không có thật.
                "preferred_unit_code": unit,
                "own_funds_vnd": own_funds,
                "budget_min_vnd": amount_range[0] if amount_range else None,
                "budget_max_vnd": amount_range[1] if amount_range else None,
                "bedrooms": result.entities.get("bedrooms"),
                "needs_summary": ", ".join(needs_bits) + ".",
            },
        }
    if result.intent == INTENT_CREATE_QUOTE:
        scenario = "PA-NHANH" if _has(grounding.normalize(text), "sớm", "nhanh", "chiết khấu") else (
            "PA-VAY" if _has(grounding.normalize(text), "vay", "lãi", "ngân hàng") else "PA-CHUDONG"
        )
        amount_range = result.entities.get("amount_range_vnd")
        # Thẻ báo giá mang luôn ngữ cảnh tài chính đã bóc được: UI dựng payload POST /quotes không phải
        # hỏi lại, và `missing` nói thẳng còn thiếu gì (chưa biết căn) để chặn TRƯỚC khi gọi server —
        # cổng /submit-review phía backend cũng chặn đúng những trường hợp này.
        missing_fields = [name for name, value in (("unit_code", unit),) if not value]
        return {
            "action_type": INTENT_CREATE_QUOTE,
            "action_data": {
                "unit_code": unit,
                "scenario": scenario,
                "own_funds_vnd": result.entities.get("amount_vnd"),
                "budget_min_vnd": amount_range[0] if amount_range else None,
                "budget_max_vnd": amount_range[1] if amount_range else None,
                "bedrooms": result.entities.get("bedrooms"),
                "missing": missing_fields,
            },
        }
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
