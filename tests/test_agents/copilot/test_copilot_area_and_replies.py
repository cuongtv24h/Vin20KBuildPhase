"""Khoá lại 2 lỗi thật người dùng báo (đợt 25): câu "tìm giúp em căn 70m² tầm 3 tỷ" và lượt trả lời rỗng.

Vì sao cần: Copilot từng (a) KHÔNG tra giỏ hàng cho câu tìm căn nêu diện tích — rơi vào nhánh xã giao rồi
tự nói "hệ thống đang lỗi, chưa trả về dữ liệu căn hộ", và (b) kết thúc lượt stream mà không có câu trả lời
(UI hiện "Trợ lý chưa phản hồi"). Bộ test này chốt: câu tìm căn LUÔN phải gọi tool, kết quả lọc theo diện
tích phải nói rõ khoảng đã lọc, và mọi lượt stream phải kết thúc bằng một `final` có nội dung.
"""

from __future__ import annotations

import pytest

from src.agents.copilot import intents
from src.agents.copilot.graph import CopilotRequest, stream_copilot
from src.agents.copilot.inventory_funnel import area_range_text, next_steps, render_empty_funnel
from src.agents.copilot.tools import TOOLS_BY_NAME

TX_DATE = "2026-09-15"


def _intent(text: str) -> intents.IntentResult:
    return intents.detect_intent(text)


# ─── Hiểu câu có diện tích ────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "text",
    [
        "Chị ơi tìm giúp em căn 70m² tầm 3 tỷ",
        "Tìm căn hộ khoảng 70m2 ngân sách 3 tỷ",
        "Căn 70 mét vuông giá 3 tỷ còn không em?",
        "Giỏ hàng còn căn 70 m² nào không em?",
    ],
)
def test_browse_question_with_area_is_not_small_talk(text: str) -> None:
    """Câu tìm căn (kể cả có từ đệm "giúp em") phải vào nhánh TRA GIỎ HÀNG, không phải xã giao."""
    result = _intent(text)
    assert result.intent == intents.INTENT_BROWSE_UNITS, result
    assert result.entities["area_range_m2"] == (63.0, 77.0), result.entities
    assert result.entities["area_spec_m2"] == 70.0


def test_single_area_is_widened_but_explicit_range_is_kept() -> None:
    """Một con số diện tích nghĩa là "quanh đó" (±10%); khoảng rõ ràng thì giữ nguyên."""
    assert _intent("tìm căn 70m²").entities["area_range_m2"] == (63.0, 77.0)
    assert _intent("tìm căn từ 65 đến 75m2").entities["area_range_m2"] == (65.0, 75.0)
    assert _intent("tìm căn 60-70m²").entities["area_range_m2"] == (60.0, 70.0)
    # Không nêu diện tích ⇒ không lọc theo diện tích (tránh bắt nhầm con số khác thành m²)
    assert _intent("tìm căn 2 ngủ tầm 3 tỷ").entities["area_range_m2"] is None


def test_customer_lookup_with_unit_is_not_hijacked_by_browse_rule() -> None:
    """Câu có "khách" chen giữa động từ và "căn" là TRA HỒ SƠ KHÁCH — không được kéo sang tìm giỏ hàng."""
    result = _intent("Tìm khách Nguyễn Văn An quan tâm căn ZEN-A-1205")
    assert result.intent == intents.INTENT_LOOKUP_CUSTOMER, result


# ─── Lọc theo diện tích ở tầng tool ───────────────────────────────────────────


@pytest.mark.asyncio
async def test_area_filter_finds_unit_and_states_the_window() -> None:
    raw = await TOOLS_BY_NAME["tra_cuu_gio_hang"].ainvoke(
        {"dien_tich_min_m2": 63.0, "dien_tich_max_m2": 77.0}
    )
    assert "ZEN-A-1205" in raw  # 72.5m²
    assert "63–77m²" in raw, "phải nói rõ khoảng diện tích đang lọc"
    assert "ZEN-A-0803" not in raw, "căn 52m² không nằm trong khoảng 63–77m²"


@pytest.mark.asyncio
async def test_area_filter_excludes_units_without_area_data(monkeypatch: pytest.MonkeyPatch) -> None:
    """Căn chưa có dữ liệu diện tích bị loại khi lọc theo m² — và số lượng đó phải được nói ra."""
    from src.agents.copilot import grounding

    base = list(grounding.UNITS_DATA)
    monkeypatch.setattr(
        grounding,
        "list_units",
        lambda: [*base, {"unit_code": "ZEN-Z-0001", "project_id": "THE_ZEN_PARK", "bedrooms": 2, "area_m2": None, "listed_price_before_tax_vnd": 3_000_000_000, "status": "AVAILABLE"}],
    )
    raw = await TOOLS_BY_NAME["tra_cuu_gio_hang"].ainvoke(
        {"dien_tich_min_m2": 63.0, "dien_tich_max_m2": 77.0}
    )
    assert "ZEN-Z-0001" not in raw, "không được suy diễn diện tích cho căn thiếu dữ liệu"
    assert "ZEN-A-1205" in raw


def test_empty_funnel_for_area_only_query_has_no_nonsense_label() -> None:
    """Sale chỉ nêu diện tích + ngân sách ⇒ phễu phải nói về TOÀN GIỎ, không được sinh nhãn "0PN"."""
    text = render_empty_funnel(bedrooms=0, budget_vnd=3_000_000_000, area_min_m2=63.0, area_max_m2=77.0, area_spec_m2=70.0)
    assert "0PN" not in text
    assert "Tiêu chí diện tích: 63–77m²" in text
    assert "ZEN-A-1205" in text, "phải có căn gần khoảng diện tích nhất để Sale có hướng đi tiếp"
    assert "TOÀN GIỎ" in text
    assert all("0PN" not in step for step in next_steps(0, 3_000_000_000))
    assert area_range_text(63.0, 77.0, 70.0) == "63–77m² (quanh 70m² khách nêu)"


# ─── Chạy trọn pipeline (offline) cho đúng câu người dùng báo lỗi ─────────────


@pytest.mark.asyncio
async def test_offline_reply_for_area_question_has_data_and_no_apology() -> None:
    """Câu của người dùng: phải GỌI tool, trả số liệu thật, và KHÔNG được nói hệ thống lỗi."""
    from scripts.run_copilot_eval import _offline_llm_factory

    final = None
    async for event in stream_copilot(
        CopilotRequest(message="Chị ơi tìm giúp em căn 70m² tầm 3 tỷ", transaction_date=TX_DATE),
        llm_factory=_offline_llm_factory,
    ):
        if event.type == "final":
            final = event.data
    assert final is not None
    assert "tra_cuu_gio_hang" in final["tools_used"], "câu tìm căn PHẢI gọi tool giỏ hàng"
    reply = final["reply"]
    assert "63–77m²" in reply
    assert "ZEN-A-1205" in reply
    assert "0PN" not in reply
    for excuse in ("hệ thống đang lỗi", "hệ thống lỗi", "chưa trả về dữ liệu", "chưa tra được dữ liệu"):
        assert excuse not in reply.lower(), f"không được đổ lỗi hệ thống: {excuse}"
    assert final["grounded"] is True


@pytest.mark.asyncio
async def test_http_chat_answers_the_reported_question_end_to_end(client, monkeypatch: pytest.MonkeyPatch) -> None:
    """Đi qua đúng đường HTTP như app đang chạy (LLM không khả dụng ⇒ nhánh tất định)."""
    import src.services.llm as llm_module

    def _no_llm():  # pragma: no cover — chỉ chạy nếu hệ thống cố gọi LLM thật trong test
        raise RuntimeError("NO_LLM_IN_TEST")

    monkeypatch.setattr(llm_module, "get_llm", _no_llm)
    resp = await client.post(
        "/api/v1/copilot/chat",
        json={"message": "Chị ơi tìm giúp em căn 70m² tầm 3 tỷ", "transaction_date": TX_DATE},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["mode"] == "offline_react"
    assert "tra_cuu_gio_hang" in body["tools_used"]
    assert "63–77m²" in body["reply"]
    assert body["reply"].strip(), "lượt trả lời không được rỗng"


@pytest.mark.asyncio
async def test_offline_reply_mentions_matching_units_for_area_only_question() -> None:
    """Hỏi thuần diện tích (không giá) thì phải ra ĐÚNG căn trong khoảng — có bảng do máy dựng."""
    from scripts.run_copilot_eval import _offline_llm_factory

    final = None
    async for event in stream_copilot(
        CopilotRequest(message="Giỏ hàng còn căn 70m² nào không em?", transaction_date=TX_DATE),
        llm_factory=_offline_llm_factory,
    ):
        if event.type == "final":
            final = event.data
    assert final is not None
    assert "ZEN-A-1205" in final["reply"]
    assert "72.5m²" in final["reply"]
    assert "| Mã căn |" in final["reply"], "danh sách căn luôn trình bày dạng bảng (P1.5)"
