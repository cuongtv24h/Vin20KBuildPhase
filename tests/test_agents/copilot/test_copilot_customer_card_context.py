"""Thẻ khách hàng & ngữ cảnh căn (chốt đợt 20 — sửa lỗi #16, #17).

Hai lỗi người dùng bắt được khi dùng thật:

1. Câu "tạo khách hàng mới Chu Thúy Quỳnh, số điện thoại 0924442345, tài chính ban đầu 2 tỷ,
   nguyện vọng mua căn từ 3 tỷ đến 5 tỷ" cho ra thẻ có tên **"Chu Thúy Quỳnh, số"**, một **căn hộ
   quan tâm bịa** (`ZEN-A-1205`) và **mất khoảng ngân sách 3–5 tỷ**.
2. Sau khi bấm "Chọn PA vay 0%", thẻ "Xác nhận tham số tạo báo giá" vẫn ghi "Chưa chọn căn" dù mã
   căn nằm ngay trong ngữ cảnh hội thoại.

Bộ test này khoá lại: bóc tách sạch, không bịa, giữ đủ số liệu, và ngữ cảnh căn được chuyển vào
tham số hành động (planner/`build_action_card`).
"""

from __future__ import annotations

from src.agents.copilot import intents, planner

CUSTOMER_MESSAGE = (
    "tạo khách hàng mới Chu Thúy Quỳnh, số điện thoại 0924442345, tài chính ban đầu 2 tỷ, "
    "nguyện vọng mua căn từ 3 tỷ đến 5 tỷ"
)


def _card(message: str = CUSTOMER_MESSAGE, context: dict | None = None) -> dict:
    result = intents.detect_intent(message)
    card = intents.build_action_card(message, result, context or {"current_unit": None})
    assert card is not None, "câu tạo khách hàng phải sinh thẻ hành động"
    return card["action_data"]


# ─── Bóc tách tên / SĐT ────────────────────────────────────────────────────────


def test_customer_name_has_no_phone_label_tail() -> None:
    """Tên khách không được dính đuôi ", số" (nhãn SĐT bị cắt dở)."""
    data = _card()
    assert data["customer_name"] == "Chu Thúy Quỳnh"
    assert not data["customer_name"].lower().endswith(("số", "số điện thoại", "sđt", "sdt"))


def test_customer_phone_is_extracted() -> None:
    assert _card()["customer_phone"] == "0924442345"


def test_name_extraction_variants() -> None:
    """Các cách viết nhãn SĐT khác nhau đều phải cho ra đúng tên."""
    cases = {
        "tạo khách Nguyễn Văn A sđt 0912345678 vốn 1,5 tỷ": "Nguyễn Văn A",
        "thêm khách hàng Trần Thị B, số 0987654321": "Trần Thị B",
        "tạo khách hàng mới Lê Minh C, điện thoại 0905123456": "Lê Minh C",
    }
    for message, expected in cases.items():
        assert intents.extract_name(message) == expected, message


# ─── Không bịa căn ────────────────────────────────────────────────────────────


def test_card_never_invents_a_unit() -> None:
    """Không có căn trong câu nói ⇒ thẻ khách để trống căn (trước đây luôn là `ZEN-A-1205`)."""
    data = _card()
    assert data["preferred_unit_code"] == ""
    assert "ZEN-A-1205" not in data["needs_summary"]


def test_card_takes_unit_from_conversation_context() -> None:
    """Căn đang mở trong phiên (ngữ cảnh thật) thì được đưa vào thẻ."""
    data = _card("tạo khách mới Hà My", {"current_unit": "SAP-D-4201"})
    assert data["preferred_unit_code"] == "SAP-D-4201"
    assert "SAP-D-4201" in data["needs_summary"]


# ─── Ngân sách / vốn tự có ────────────────────────────────────────────────────


def test_budget_range_is_kept_next_to_own_funds() -> None:
    """Câu có HAI loại số (vốn tự có 2 tỷ · ngân sách 3–5 tỷ) ⇒ giữ đủ cả hai, đúng vai."""
    data = _card()
    assert data["own_funds_vnd"] == 2_000_000_000
    assert data["budget_min_vnd"] == 3_000_000_000
    assert data["budget_max_vnd"] == 5_000_000_000
    summary = data["needs_summary"]
    assert "2.000.000.000" in summary and "3.000.000.000" in summary and "5.000.000.000" in summary


def test_budget_range_resolves_shared_unit() -> None:
    """Khoảng viết tắt "3-5 tỷ" vẫn hiểu là 3 tỷ – 5 tỷ (mốc sau quyết định đơn vị)."""
    assert intents.extract_amount_range("ngân sách 3-5 tỷ") == (3_000_000_000, 5_000_000_000)
    assert intents.extract_amount_range("từ 3 tỷ đến 5 tỷ") == (3_000_000_000, 5_000_000_000)
    assert intents.extract_amount_range("ngân sách 500 triệu - 1 tỷ") == (500_000_000, 1_000_000_000)


def test_dash_without_unit_on_second_mark_is_not_a_range() -> None:
    """"2PN - 3 tỷ" không phải khoảng giá — đừng gộp số phòng ngủ vào ngân sách."""
    assert intents.extract_amount_range("căn 2PN - 3 tỷ") is None
    assert intents.extract_amount_range("vốn tự có 3 tỷ") is None


def test_needs_summary_has_no_trailing_comma_noise() -> None:
    summary = _card()["needs_summary"]
    assert ", ," not in summary
    assert not summary.startswith("Khách ,")


# ─── Ngữ cảnh căn cho bước soạn tin / lập báo giá (lỗi #16) ───────────────────


def test_planner_inherits_unit_from_session_context() -> None:
    """Bước soạn tin không nêu mã căn vẫn phải dùng căn đang mở trong phiên."""
    plan = planner.decompose("soạn tin nhắn tư vấn gửi khách", {}, context_unit="SAP-D-4201")
    assert [step.args.get("ma_can") for step in plan] == ["SAP-D-4201"]


def test_planner_never_defaults_to_a_demo_unit() -> None:
    """Không có ngữ cảnh ⇒ để trống, không mượn mã căn demo."""
    plan = planner.decompose("soạn tin nhắn tư vấn gửi khách", {})
    assert all(step.args.get("ma_can") != "ZEN-A-1205" for step in plan)
    assert all(str(step.reason) for step in plan)


def test_message_can_still_name_its_own_unit() -> None:
    """Mã căn nêu ngay trong câu lệnh vẫn thắng ngữ cảnh phiên."""
    plan = planner.decompose("soạn tin về căn G-03.02", {}, context_unit="SAP-D-4201")
    assert [step.args.get("ma_can") for step in plan] == ["G-03.02"]


# ─── Bảng gợi ý căn phải bám ngân sách khách vừa nêu (lỗi #17b) ───────────────


def test_browse_step_uses_budget_range_ceiling() -> None:
    """Câu có khoảng 3–5 tỷ ⇒ bước lọc giỏ lấy trần 5 tỷ, không trả về cả căn 6,1 tỷ."""
    result = intents.detect_intent(CUSTOMER_MESSAGE)
    steps = [s for s in planner.decompose(CUSTOMER_MESSAGE, result.entities) if s.tool == "tra_cuu_gio_hang"]
    assert steps, "cần một bước tra giỏ hàng để gợi ý căn"
    assert steps[0].args["gia_toi_da_vnd"] == 5_000_000_000


def test_budget_ceiling_prefers_range_over_single_amount() -> None:
    """'Vốn tự có 2 tỷ' + 'nguyện vọng 3–5 tỷ': nguyện vọng mới là mốc lọc giỏ."""
    entity = {"amount_vnd": 2_000_000_000, "amount_range_vnd": (3_000_000_000, 5_000_000_000)}
    assert planner._budget_ceiling(entity) == 5_000_000_000
    assert planner._budget_ceiling({"amount_vnd": 2_000_000_000}) == 2_000_000_000
    assert planner._budget_ceiling({}) == 0


def test_offline_reply_keeps_both_amounts_and_no_invented_unit() -> None:
    """Câu trả lời (nhánh dự phòng tất định) phải nêu đủ 2 tỷ + 3–5 tỷ và không nhắc căn bịa."""
    import asyncio

    from scripts.run_copilot_eval import _offline_llm_factory
    from src.agents.copilot.graph import CopilotRequest, stream_copilot

    async def run() -> dict:
        final: dict = {}
        async for event in stream_copilot(
            CopilotRequest(message=CUSTOMER_MESSAGE, transaction_date="2026-10-03"),
            llm_factory=_offline_llm_factory,
        ):
            if event.type == "final":
                final = event.data
        return final

    final = asyncio.run(run())
    reply = str(final.get("reply") or "")
    assert "2.000.000.000" in reply and "5.000.000.000" in reply
    assert "ZEN-A-1205, " not in reply  # không nhắc căn nào như "căn hộ quan tâm" của khách
    data = final.get("action_data") or {}
    assert data.get("preferred_unit_code") == ""
