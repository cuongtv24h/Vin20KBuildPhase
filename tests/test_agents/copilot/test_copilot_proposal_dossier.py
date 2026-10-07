"""Tool "soạn hồ sơ đề xuất" — chặng đầu của luồng Sale → Copilot → báo giá → Quản lý duyệt.

Khoá lại lỗ hổng thật: Copilot không có tool nào soạn được hồ sơ đề xuất nên Sale phải tự ghép thông tin
(căn, phương án, chính sách) từ nhiều câu trả lời và **không biết còn thiếu gì** trước khi trình Quản lý.
Tool dựng hồ sơ từ dữ liệu canonical + engine tất định, tự kiểm F8 và trả kèm checklist việc còn thiếu.
Việc trình duyệt vẫn do Sale bấm xác nhận — cổng `/quotes/{id}/submit-review` kiểm tra lại bằng chứng C-04.
"""

from __future__ import annotations

import json

import pytest

from src.agents.copilot import intents, planner
from src.agents.copilot.graph import CopilotRequest, stream_copilot
from src.agents.copilot.tools import COPILOT_TOOLS, TOOLS_BY_NAME

#: Ngày nằm trong hiệu lực CSBH-ZEN-2026-V3.1 (2026-08-01 → 2026-12-31).
TX_DATE = "2026-09-15"
#: Ngày không thuộc hiệu lực của bất kỳ văn bản Zen Park nào (V2.0 bắt đầu 2026-05-01).
TX_DATE_OUTSIDE_POLICY = "2026-04-15"


async def _dossier(**kwargs) -> dict:
    raw = await TOOLS_BY_NAME["soan_ho_so_de_xuat"].ainvoke(kwargs)
    return json.loads(raw)


# ─── Hồ sơ dựng từ dữ liệu thật ───────────────────────────────────────────────


@pytest.mark.asyncio
async def test_dossier_has_unit_policy_and_engine_numbers() -> None:
    payload = await _dossier(
        ma_can="ZEN-A-1205",
        ten_khach="Anh Nam",
        von_tu_co_vnd=1_500_000_000,
        ngay_giao_dich=TX_DATE,
    )
    dossier = payload["summary"]
    assert payload["tool"] == "soan_ho_so_de_xuat"
    assert "HỒ SƠ ĐỀ XUẤT" in dossier
    assert "ZEN-A-1205" in dossier
    assert "Anh Nam" in dossier
    # Giá niêm yết lấy từ catalog fixture — không phải con số model tự nghĩ.
    assert "4.200.000.000" in dossier
    # Số tiền của phương án do engine tất định trả về, kèm khuyến nghị.
    assert "giá Net" in dossier
    assert "tổng HĐMB" in dossier
    assert payload["recommended"] in {"PA-CHUDONG", "PA-NHANH", "PA-VAY"}
    assert payload["recommended"] in dossier
    # Chính sách hiệu lực tại ngày giao dịch + điều khoản nguồn.
    assert payload["policy_id"] == "CSBH-ZEN-2026-V3.1"
    assert "CSBH-ZEN-2026-V3.1" in dossier
    sources = {c.get("source") for c in payload["citations"]}
    assert "DETERMINISTIC_ENGINE" in sources
    assert any(c.get("document_hash") for c in payload["citations"])
    # Hồ sơ đã đủ đầu vào ⇒ không còn mục nào phải bổ sung.
    assert payload["missing"] == []
    assert payload["grounded"] is True


# ─── Checklist việc còn thiếu ─────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_dossier_checklist_flags_missing_own_funds() -> None:
    payload = await _dossier(ma_can="ZEN-A-1205", ngay_giao_dich=TX_DATE)
    assert any("Vốn tự có" in item for item in payload["missing"])
    assert "VIỆC CẦN BỔ SUNG" in payload["summary"]


@pytest.mark.asyncio
async def test_dossier_checklist_flags_date_outside_policy_window() -> None:
    payload = await _dossier(
        ma_can="ZEN-A-1205",
        von_tu_co_vnd=1_500_000_000,
        ngay_giao_dich=TX_DATE_OUTSIDE_POLICY,
    )
    assert payload["policy_id"] is None
    assert any("Chính sách" in item for item in payload["missing"])
    assert "Chưa xác định được chính sách" in payload["summary"]


@pytest.mark.asyncio
async def test_dossier_asks_for_unit_when_none_given() -> None:
    payload = await _dossier(ngay_giao_dich=TX_DATE)
    assert payload.get("error")
    assert any("Mã căn" in item for item in payload["missing"])
    assert "mã căn" in payload["summary"].lower()


@pytest.mark.asyncio
async def test_dossier_auto_resolves_unit_from_criteria() -> None:
    payload = await _dossier(
        so_phong_ngu=2,
        gia_toi_da_vnd=5_000_000_000,
        von_tu_co_vnd=1_500_000_000,
        ngay_giao_dich=TX_DATE,
    )
    assert "Căn được chọn tự động" in payload["summary"]
    assert "ZEN-" in payload["summary"]


# ─── Đăng ký tool + đường đi tất định (offline/planner) ───────────────────────


def test_proposal_tool_is_registered() -> None:
    names = {t.name for t in COPILOT_TOOLS}
    assert "soan_ho_so_de_xuat" in names
    assert TOOLS_BY_NAME["soan_ho_so_de_xuat"] is not None


def test_proposal_intent_wins_over_quote_keywords_and_plans_the_tool() -> None:
    """Câu "soạn hồ sơ đề xuất … lập báo giá" phải vào nhánh hồ sơ đề xuất, không bị nhánh báo giá nuốt."""
    message = "soạn hồ sơ đề xuất cho căn ZEN-A-1205 rồi lập báo giá trình Quản lý"
    result = intents.detect_intent(message)
    assert result.intent == intents.INTENT_COMPOSE_PROPOSAL
    steps = planner.decompose(message, result.entities)
    assert steps, "planner phải sinh bước cho yêu cầu soạn hồ sơ đề xuất"
    assert steps[0].tool == "soan_ho_so_de_xuat"
    assert steps[0].args.get("ma_can") == "ZEN-A-1205"


@pytest.mark.asyncio
async def test_proposal_tool_opens_no_db_session(monkeypatch: pytest.MonkeyPatch) -> None:
    """Zero-Trust: soạn hồ sơ chỉ đọc catalog + gọi engine tất định — không mở phiên DB nào."""
    import src.db.session as db_session

    def _boom(*_args, **_kwargs):  # pragma: no cover — chỉ chạy nếu tool vi phạm
        raise AssertionError("Tool soạn hồ sơ đề xuất không được mở phiên DB")

    monkeypatch.setattr(db_session, "async_session_factory", _boom)
    payload = await _dossier(ma_can="ZEN-A-1205", ngay_giao_dich=TX_DATE)
    assert "HỒ SƠ ĐỀ XUẤT" in payload["summary"]


# ─── Chạy đường thật của pipeline (offline ReAct) ─────────────────────────────


@pytest.mark.asyncio
async def test_offline_pipeline_drafts_dossier_and_keeps_reply_clean() -> None:
    """Câu trả lời cuối phải mang cả hồ sơ lẫn checklist, và không lộ tên tool nội bộ."""
    from scripts.run_copilot_eval import _offline_llm_factory

    final = None
    request = CopilotRequest(
        message="soạn hồ sơ đề xuất cho căn ZEN-A-1205 trình Quản lý",
        transaction_date=TX_DATE,
    )
    async for event in stream_copilot(request, llm_factory=_offline_llm_factory):
        if event.type == "final":
            final = event.data
    assert final is not None
    assert "soan_ho_so_de_xuat" in final["tools_used"]
    assert "HỒ SƠ ĐỀ XUẤT" in final["reply"]
    # Checklist còn thiếu (chưa có vốn tự có) phải tới tay Sale.
    assert "Vốn tự có" in final["reply"]
    assert "soan_ho_so_de_xuat" not in final["reply"], "tên tool nội bộ không được lọt vào câu trả lời"
    assert final["mode"] in {"offline_react", "react"}
    assert final["grounded"] is True
