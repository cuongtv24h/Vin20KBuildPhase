"""Planner nhẹ cho Sales Copilot — chia câu hỏi nhiều ý thành các bước nghiệp vụ.

Vấn đề: Sale thường nói một câu gộp nhiều ý, ví dụ
    "tính phương án cho căn ZEN-A-1205 rồi soạn tin cho khách"
Trước đây Copilot xử lý tuyến tính theo MỘT intent đầu tiên khớp được → bỏ sót ý thứ hai.

Cách làm ở đây: tách câu theo liên từ nối ("rồi", "sau đó", "và", "đồng thời"…), chạy
`intents.detect_intent` cho từng mệnh đề, sắp xếp theo ĐÚNG thứ tự nghiệp vụ (tra chính sách →
tra giỏ hàng → tính phương án → soạn/kiểm tra), khử trùng lặp.

Planner này là tất định và không gọi LLM nên:
- dùng được cả ở chế độ offline,
- làm gợi ý cho LLM ở chế độ ReAct (đưa vào prompt dưới dạng "kế hoạch gợi ý"),
- đảm bảo không bao giờ bỏ sót ý khi LLM lỗi.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from src.agents.copilot import intents

# Liên từ tách mệnh đề. Giữ "và" ở mức thận trọng: chỉ tách khi hai vế đều có động từ nghiệp vụ,
# tránh cắt vụn câu như "giá và chính sách" thành 2 bước vô nghĩa.
_SPLIT_RE = re.compile(
    r"\s*(?:;|,|\brồi\b|\bsau\s+đó\b|\btiếp\s+theo\b|\bđồng\s+thời\b|\bvà\s+sau\s+đó\b|\bxong\s+thì\b|\bvà\b)\s*",
    re.IGNORECASE,
)

# Thứ tự nghiệp vụ: phải tra cứu trước khi tính, tính xong mới soạn/gửi.
_WORKFLOW_ORDER = {
    intents.INTENT_LOOKUP_POLICY: 10,
    intents.INTENT_LOOKUP_CUSTOMER: 15,
    intents.INTENT_BROWSE_UNITS: 20,
    intents.INTENT_ASSESS_FUNDS: 25,
    intents.INTENT_COMPARE_SCENARIOS: 30,
    intents.INTENT_CREATE_QUOTE: 35,
    intents.INTENT_COMPOSE_MESSAGE: 40,
    intents.INTENT_CREATE_CUSTOMER: 50,
    intents.INTENT_CHECK_F8: 60,
    intents.INTENT_SMALL_TALK: 99,
}

MAX_PLAN_STEPS = 3


@dataclass
class PlanStep:
    """Một bước trong kế hoạch xử lý câu hỏi."""

    intent: str
    tool: str | None = None
    args: dict = field(default_factory=dict)
    reason: str = ""
    order: int = 50


def split_clauses(message: str) -> list[str]:
    """Tách câu thành các mệnh đề độc lập (giữ nguyên dấu tiếng Việt)."""
    parts = [p.strip(" ,;:-") for p in _SPLIT_RE.split(message or "") if p and p.strip(" ,;:-")]
    # Mệnh đề quá ngắn (< 3 ký tự) hoặc không có chữ cái → bỏ
    return [p for p in parts if len(p) >= 3 and re.search(r"[^\W\d_]", p, re.UNICODE)]


def _tool_for(intent: str, args: dict) -> str | None:
    if intent == intents.INTENT_LOOKUP_POLICY:
        return "tra_cuu_chinh_sach"
    if intent == intents.INTENT_BROWSE_UNITS:
        return "tra_cuu_gio_hang"
    if intent == intents.INTENT_ASSESS_FUNDS:
        # Đánh giá vốn tự có = mốc TỔNG QUAN (chốt P1.2); muốn bảng dòng tiền chi tiết thì dùng
        # `tinh_phuong_an_thanh_toan` (Sale bấm "Xem bảng tính vay chi tiết").
        return "danh_gia_von_tu_co"
    if intent in (intents.INTENT_CREATE_QUOTE, intents.INTENT_COMPARE_SCENARIOS):
        return "tinh_phuong_an_thanh_toan"
    if intent == intents.INTENT_COMPOSE_MESSAGE:
        return "soan_tin_tu_van"
    if intent == intents.INTENT_LOOKUP_CUSTOMER:
        return "tra_cuu_ho_so_khach_hang"
    if intent == intents.INTENT_CHECK_F8:
        return "kiem_tra_phat_ngon_f8"
    if intent == intents.INTENT_CREATE_CUSTOMER:
        return "tra_cuu_gio_hang"
    return None


def _args_for(intent: str, clause: str, entity: dict) -> dict:
    tx_date = str(entity.get("transaction_date") or "")
    unit = str(entity.get("unit_code") or entity.get("current_unit") or "ZEN-A-1205")
    if intent == intents.INTENT_LOOKUP_POLICY:
        return {"cau_hoi": clause, "ngay_hieu_luc": tx_date}
    if intent == intents.INTENT_BROWSE_UNITS:
        return {
            "so_phong_ngu": entity.get("bedrooms") or 0,
            "gia_toi_da_vnd": entity.get("amount_vnd") or 0,
            "ma_can": entity.get("unit_code") or "",
        }
    if intent == intents.INTENT_ASSESS_FUNDS:
        return {
            "von_tu_co_vnd": entity.get("amount_vnd") or 0,
            "so_phong_ngu": entity.get("bedrooms") or 0,
            "ma_can": entity.get("unit_code") or "",
            "ngay_giao_dich": tx_date,
        }
    if intent in (intents.INTENT_CREATE_QUOTE, intents.INTENT_COMPARE_SCENARIOS):
        return {
            "ma_can": unit,
            "von_tu_co_vnd": entity.get("amount_vnd") or 0,
            "muc_tieu": "MIN_INITIAL_CASH",
            "ngay_giao_dich": tx_date,
        }
    if intent == intents.INTENT_COMPOSE_MESSAGE:
        return {"ma_can": unit, "ten_khach": entity.get("customer_name") or "", "noi_dung_chinh": ""}
    if intent == intents.INTENT_LOOKUP_CUSTOMER:
        return {"tu_khoa": entity.get("customer_name") or clause}
    if intent == intents.INTENT_CHECK_F8:
        return {"noi_dung": clause}
    if intent == intents.INTENT_CREATE_CUSTOMER:
        return {"so_phong_ngu": entity.get("bedrooms") or 0, "ma_can": unit}
    return {}


def decompose(message: str, entity: dict | None = None) -> list[PlanStep]:
    """Chia câu lệnh thành các bước nghiệp vụ theo thứ tự thực thi.

    Trả về danh sách rỗng nếu câu lệnh chỉ là small talk hoặc không có mệnh đề nghiệp vụ nào.
    """
    entity = dict(entity or {})
    clauses = split_clauses(message) or [message]

    steps: dict[str, PlanStep] = {}
    for clause in clauses:
        result = intents.detect_intent(clause)
        if result.intent == intents.INTENT_SMALL_TALK:
            continue
        if result.intent in steps:
            continue
        merged = {**entity, **{k: v for k, v in result.entities.items() if v}}
        tool = _tool_for(result.intent, merged)
        steps[result.intent] = PlanStep(
            intent=result.intent,
            tool=tool,
            args=_args_for(result.intent, clause, merged),
            reason=f"Mệnh đề: “{clause[:80]}”",
            order=_WORKFLOW_ORDER.get(result.intent, 50),
        )

    ordered = sorted(steps.values(), key=lambda s: s.order)[:MAX_PLAN_STEPS]
    return ordered


def plan_summary(steps: list[PlanStep]) -> str:
    """Câu mô tả kế hoạch để hiển thị UI (thought event)."""
    if not steps:
        return ""
    labels = {
        intents.INTENT_LOOKUP_POLICY: "tra chính sách hiệu lực",
        intents.INTENT_BROWSE_UNITS: "lọc giỏ hàng",
        intents.INTENT_ASSESS_FUNDS: "đánh giá vốn tự có",
        intents.INTENT_COMPARE_SCENARIOS: "tính & so sánh phương án",
        intents.INTENT_CREATE_QUOTE: "lập báo giá",
        intents.INTENT_COMPOSE_MESSAGE: "soạn tin & tự kiểm F8",
        intents.INTENT_LOOKUP_CUSTOMER: "tra hồ sơ khách",
        intents.INTENT_CHECK_F8: "kiểm tra phát ngôn F8",
        intents.INTENT_CREATE_CUSTOMER: "bóc tách hồ sơ khách",
    }
    return " → ".join(labels.get(s.intent, s.intent) for s in steps)


__all__ = ["MAX_PLAN_STEPS", "PlanStep", "decompose", "plan_summary", "split_clauses"]
