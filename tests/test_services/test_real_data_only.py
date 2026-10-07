"""Sản phẩm chạy thật KHÔNG được lấy dữ liệu từ fixture canonical.

Người dùng yêu cầu rõ (đợt 26): "sản phẩm chạy online phải chạy với dữ liệu thật, không dùng mock nữa".
Bộ test này khoá đúng ba điều:

1. Mặc định (`ALLOW_FIXTURE_DATA` không bật) thì `grounding` **không** trả giỏ hàng/chính sách mẫu.
2. Cùng điều kiện đó, API `/units` và `/public/projects` không trả dữ liệu mẫu.
3. Khi không có dữ liệu thật, Copilot nói thẳng "chưa có dữ liệu trong dữ liệu vận hành" — không bịa căn,
   không đổ lỗi hệ thống, không mời Sale "nới ngân sách" khi giỏ trống.

Cờ chỉ được bật cho test/demo offline (`tests/conftest.py` bật cho toàn bộ suite).
"""

from __future__ import annotations

import pytest

from src.agents.copilot import grounding, inventory_funnel
from src.services import data_source, policy_source


def test_fixture_flag_is_off_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    """Mặc định của cờ phải là TẮT — nếu ai đổi default, test này chặn ngay."""
    monkeypatch.delenv(data_source.FIXTURE_ENV, raising=False)
    assert data_source.fixtures_allowed() is False

    for truthy in ("1", "true", "TRUE", "yes", "on"):
        monkeypatch.setenv(data_source.FIXTURE_ENV, truthy)
        assert data_source.fixtures_allowed() is True, truthy

    monkeypatch.setenv(data_source.FIXTURE_ENV, "false")
    assert data_source.fixtures_allowed() is False


def test_policies_come_from_db_not_fixture(monkeypatch: pytest.MonkeyPatch) -> None:
    """CSDL trống + cờ tắt ⇒ danh sách chính sách RỖNG (không lấy 3 chính sách mẫu)."""
    monkeypatch.delenv(data_source.FIXTURE_ENV, raising=False)
    monkeypatch.setattr(grounding, "_cached_db_policies", [], raising=False)
    assert grounding.list_policies() == []
    assert grounding.resolve_active_policy("THE_ZEN_PARK") is None


def test_units_come_from_db_not_fixture(monkeypatch: pytest.MonkeyPatch) -> None:
    """CSDL trống + cờ tắt ⇒ giỏ hàng RỖNG, không có căn demo (ZEN-A-1205…) cho Sale tư vấn."""
    monkeypatch.delenv(data_source.FIXTURE_ENV, raising=False)
    monkeypatch.setattr(grounding, "_cached_db_units", [], raising=False)
    assert grounding.list_units() == []
    assert grounding.find_unit("ZEN-A-1205") is None
    assert grounding.search_units() == []


def test_fixture_is_only_used_when_explicitly_allowed(monkeypatch: pytest.MonkeyPatch) -> None:
    """Bật cờ mới có dữ liệu mẫu — đây là đường dùng cho test/demo offline, không phải đường chạy thật."""
    monkeypatch.setenv(data_source.FIXTURE_ENV, "1")
    monkeypatch.setattr(grounding, "_cached_db_units", [], raising=False)
    monkeypatch.setattr(grounding, "_cached_db_policies", [], raising=False)
    assert grounding.find_unit("ZEN-A-1205") is not None
    assert grounding.list_policies()


def test_policy_citation_source_is_honest() -> None:
    """Citation phải ghi đúng nguồn: chính sách DB ⇒ `DB`, fixture ⇒ `CANONICAL_FIXTURE`."""
    db_policy = {
        "policy_id": "POL-DB-1",
        "policy_version": "v1",
        "title": "Chính sách thật",
        "data_source": "DB",
        "rules": [{"rule_code": "R1", "source": {"section": "Điều 1", "quote": "…"}}],
    }
    fixture_policy = {
        "policy_id": "POL-FIX-1",
        "policy_version": "v1",
        "title": "Chính sách mẫu",
        "rules": [{"rule_code": "R2", "source": {"section": "Điều 2", "quote": "…"}}],
    }
    assert grounding.policy_citations(db_policy)[0]["source"] == "DB"
    assert grounding.policy_citations(fixture_policy)[0]["source"] == "CANONICAL_FIXTURE"


def test_policy_mapping_is_shared_by_both_readers() -> None:
    """Cùng hai bảng dữ liệu ⇒ cùng kết quả, dù đọc bằng đường async (API) hay sync (Copilot)."""
    policy_rows = [
        {
            "policy_id": "POL-X",
            "policy_name": "Chính sách X",
            "version": "v3",
            "effective_from": "2026-01-01",
            "effective_to": "2026-12-31",
            "status": "ACTIVE",
            "document_hash": "hash-x",
            "source_path": "x.md",
            "metadata_json": {"project_id": "PROJ-X"},
            "created_at": "2026-01-01T00:00:00Z",
        }
    ]
    atom_rows = [
        {
            "atom_id": "A1",
            "policy_id": "POL-X",
            "canonical_text": "Chiết khấu thanh toán sớm 8% cho khách hàng.",
            "content_hash": "h1",
            "article": "Điều 1",
            "clause": "Khoản 1",
            "line_start": 3,
        }
    ]
    built = policy_source.build_policies_from_rows(policy_rows, atom_rows)
    assert built[0]["policy_id"] == "POL-X"
    assert built[0]["project_id"] == "PROJ-X"
    assert built[0]["status"] == "PUBLISHED"  # ACTIVE trong DB ⇒ PUBLISHED ở API/Copilot
    assert built[0]["rules"][0]["kind"] == "PERCENT_DISCOUNT"
    assert built[0]["rules"][0]["source"]["quote"].startswith("Chiết khấu")


def test_empty_funnel_says_no_data_instead_of_no_match(monkeypatch: pytest.MonkeyPatch) -> None:
    """Giỏ trống: câu phải là "chưa có dữ liệu để đối chiếu", KHÔNG phải "0 căn ()" hay gợi ý nới ngân sách."""
    monkeypatch.delenv(data_source.FIXTURE_ENV, raising=False)
    monkeypatch.setattr(grounding, "_cached_db_units", [], raising=False)
    text = inventory_funnel.render_empty_funnel(bedrooms=0, budget_vnd=3_000_000_000, area_min_m2=63, area_max_m2=77)
    assert "chưa có căn nào trong dữ liệu vận hành" in text
    assert "0 căn ()" not in text
    assert "Hướng tiếp theo" not in text
    assert "63–77m²" in text  # vẫn nhắc lại đúng tiêu chí Sale nêu


@pytest.mark.asyncio
async def test_copilot_reply_is_honest_when_no_real_data(monkeypatch: pytest.MonkeyPatch) -> None:
    """Lượt chat đầy đủ khi CSDL trống: gọi tool thật, trả lời thật, không bịa căn và không đổ lỗi hệ thống."""
    from scripts.run_copilot_eval import _offline_llm_factory
    from src.agents.copilot.graph import CopilotRequest, stream_copilot

    monkeypatch.delenv(data_source.FIXTURE_ENV, raising=False)
    monkeypatch.setattr(grounding, "_cached_db_units", [], raising=False)
    monkeypatch.setattr(grounding, "_cached_db_policies", [], raising=False)

    final = None
    async for event in stream_copilot(
        CopilotRequest(message="Chị ơi tìm giúp em căn 70m² tầm 3 tỷ"), llm_factory=_offline_llm_factory
    ):
        if event.type == "final":
            final = event.data
    assert final is not None
    assert "tra_cuu_gio_hang" in final["tools_used"]
    assert "chưa có căn nào trong dữ liệu vận hành" in final["reply"]
    for blame in ("hệ thống lỗi", "hệ thống đang lỗi", "hệ thống hỏng"):
        assert blame not in final["reply"].lower()
    # Không được bịa mã căn demo khi CSDL trống.
    assert "ZEN-A-1205" not in final["reply"]


@pytest.mark.asyncio
async def test_assess_funds_accepts_budget_only(monkeypatch: pytest.MonkeyPatch) -> None:
    """Chỉ có số tiền, chưa có mã căn ⇒ tool tự chọn căn mốc và nói rõ — không trả bước lỗi."""
    import json

    from src.agents.copilot.tools import danh_gia_von_tu_co

    monkeypatch.setenv(data_source.FIXTURE_ENV, "1")
    monkeypatch.setattr(grounding, "_cached_db_units", [], raising=False)

    payload = json.loads(await danh_gia_von_tu_co.ainvoke({"von_tu_co_vnd": 3_000_000_000}))
    assert not payload.get("error"), payload
    assert payload["unit_code"]
    assert payload["reference_unit_reason"]
    assert "chưa nêu mã căn" in payload["summary"]


@pytest.mark.asyncio
async def test_units_endpoint_serves_db_only(monkeypatch: pytest.MonkeyPatch, client) -> None:
    """CSDL trống + cờ tắt ⇒ /units rỗng: trang Nội bộ/Khách không thấy căn mẫu nào."""
    monkeypatch.delenv(data_source.FIXTURE_ENV, raising=False)
    monkeypatch.setattr(grounding, "_cached_db_units", [], raising=False)
    resp = await client.get("/api/v1/units")
    assert resp.status_code == 200
    assert resp.json() == []
    assert "ZEN-A-1205" not in resp.text


@pytest.mark.asyncio
async def test_public_projects_endpoint_serves_db_only(monkeypatch: pytest.MonkeyPatch, client) -> None:
    """CSDL trống + cờ tắt ⇒ /public/projects rỗng: khách không bao giờ thấy dự án mẫu."""
    monkeypatch.delenv(data_source.FIXTURE_ENV, raising=False)
    monkeypatch.setattr(grounding, "_cached_db_units", [], raising=False)
    resp = await client.get("/api/v1/public/projects")
    assert resp.status_code == 200
    assert resp.json() == []
    assert "The Zen Park" not in resp.text


@pytest.mark.asyncio
async def test_units_endpoint_still_serves_fixture_in_demo_mode(monkeypatch: pytest.MonkeyPatch, client) -> None:
    """Bật cờ (test/demo offline) thì fixture canonical quay lại — suite cũ vẫn chạy được."""
    monkeypatch.setenv(data_source.FIXTURE_ENV, "1")
    monkeypatch.setattr(grounding, "_cached_db_units", [], raising=False)
    resp = await client.get("/api/v1/units")
    assert resp.status_code == 200
    assert any(u["unit_code"] == "ZEN-A-1205" for u in resp.json())
