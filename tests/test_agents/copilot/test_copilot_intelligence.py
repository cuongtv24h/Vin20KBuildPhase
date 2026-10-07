"""Test cho tầng "trí tuệ" mới của Copilot: planner, memory slot, verifier, retry tool.

Đây là các năng lực làm Copilot thông minh hơn thay vì chỉ trả lời một phát:
- planner: câu nhiều ý → nhiều bước, không bỏ sót ý.
- memory: nhớ ngữ cảnh (căn/hồ sơ/ngày) giữa các lượt, tóm tắt hội thoại dài.
- verifier: chặn số liệu không có trong Observation.
- retry: lỗi tool tạm thời được thử lại, không tiêu vốn vòng lặp ReAct.
"""

from __future__ import annotations

import json
from typing import Any

import pytest
from langchain_core.messages import AIMessage

from src.agents.copilot import memory, planner, verifier
from src.agents.copilot.graph import CopilotRequest, stream_copilot
from src.agents.copilot.tools import TOOLS_BY_NAME

# ─── Planner ────────────────────────────────────────────────────────────────


def test_planner_splits_multi_intent_message_into_ordered_steps():
    """Một câu hai ý → hai bước đúng thứ tự nghiệp vụ (tính tiền trước, soạn tin sau)."""
    steps = planner.decompose("Tính phương án cho căn ZEN-A-1205 rồi soạn tin tư vấn cho khách")
    intents = [s.intent for s in steps]
    assert "smart_scenario_compare" in intents or "smart_quote_create" in intents
    assert "smart_compose_message" in intents
    assert intents.index(next(i for i in intents if i.startswith("smart_scenario") or i == "smart_quote_create")) < intents.index(
        "smart_compose_message"
    )
    scenario_step = next(s for s in steps if s.tool == "tinh_phuong_an_thanh_toan")
    assert scenario_step.args["ma_can"] == "ZEN-A-1205"


def test_planner_ignores_small_talk_and_keeps_at_most_three_steps():
    assert planner.decompose("chào em") == []
    steps = planner.decompose(
        "tra chính sách chiết khấu, xem giỏ hàng 2 ngủ, tính phương án căn ZEN-A-1205, soạn tin cho khách"
    )
    assert 0 < len(steps) <= planner.MAX_PLAN_STEPS


def test_planner_does_not_split_on_unrelated_conjunction():
    """'giá và chính sách' không được cắt thành hai bước vô nghĩa."""
    steps = planner.decompose("giá và chính sách của căn ZEN-A-1205 thế nào?")
    assert len(steps) == 1


def test_plan_summary_is_human_readable():
    steps = planner.decompose("tính phương án cho căn ZEN-A-1205 rồi soạn tin")
    summary = planner.plan_summary(steps)
    assert "→" in summary
    assert "soạn tin" in summary


# ─── Memory ─────────────────────────────────────────────────────────────────


def test_memory_resolves_slots_from_history():
    """Lượt trước nói căn nào → lượt sau thiếu mã căn vẫn biết căn đó."""
    history = [
        {"role": "user", "content": "Cho em xem căn ZEN-A-1205"},
        {"role": "assistant", "content": "Dạ căn ZEN-A-1205 còn trống ạ."},
    ]
    slots = memory.resolve_slots(message="tính phương án đi em", history=history)
    assert slots.current_unit == "ZEN-A-1205"
    assert "current_unit" in slots.filled_from_history()


def test_memory_request_wins_over_history():
    history = [{"role": "user", "content": "căn ZEN-A-1205"}]
    slots = memory.resolve_slots(current_unit="ZEN-A-0803", message="căn này thế nào", history=history)
    assert slots.current_unit == "ZEN-A-0803"


def test_memory_extracts_dossier_and_transaction_date():
    slots = memory.resolve_slots(message="hồ sơ DOS-000123 giao dịch ngày 2026-09-26")
    assert slots.lead_dossier_id == "DOS-000123"
    assert slots.transaction_date == "2026-09-26"
    vn_date = memory.extract_slots_from_text("giao dịch 15/03/2026")
    assert vn_date["transaction_date"] == "2026-03-15"


def test_memory_summarizes_old_history_and_keeps_slots():
    history = [{"role": "user", "content": f"câu hỏi số {i} về căn ZEN-A-1205"} for i in range(12)]
    summary = memory.summarize_history(history)
    assert "TÓM TẮT HỘI THOẠI" in summary
    assert "NGỮ CẢNH ĐÃ CHỐT" in summary
    assert "ZEN-A-1205" in summary
    # Không lặp lại phần gần nhất (đã đưa nguyên văn vào prompt)
    assert "câu hỏi số 11" not in summary


def test_memory_enriches_entity_with_slots():
    slots = memory.SessionSlots(current_unit="ZEN-A-1810")
    merged = memory.enrich_entity_with_slots({}, slots)
    assert merged["unit_code"] == "ZEN-A-1810"
    assert merged["unit_code_from"] == "memory"


# ─── Verifier ───────────────────────────────────────────────────────────────


def _obs(summary: str, citations: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    return {"tool": "tinh_phuong_an_thanh_toan", "summary": summary, "citations": citations or []}


def test_verifier_accepts_numbers_present_in_observation():
    obs = [_obs("Tổng HĐMB 4.655.200.000 ₫, chiết khấu 8.0%")]
    result = verifier.verify_reply("Dạ tổng giá hợp đồng là 4.655.200.000 ₫, chiết khấu 8%.", obs)
    assert result.verified is True


def test_verifier_flags_invented_number():
    obs = [_obs("Tổng HĐMB 4.655.200.000 ₫")]
    result = verifier.verify_reply("Dạ tổng giá chỉ 3.200.000.000 ₫ thôi ạ.", obs)
    assert result.verified is False
    assert any("3.200.000.000" in claim for claim in result.unsupported)


def test_verifier_flags_policy_id_not_in_observation():
    obs = [_obs("Chiết khấu thanh toán sớm 8%")]
    result = verifier.verify_reply("Theo CSBH-ZEN-2099-V9.9 thì được 8%.", obs)
    assert result.verified is False
    assert any("CSBH-ZEN-2099-V9.9" in claim for claim in result.unsupported)


def test_verifier_matches_ty_and_percent_units_across_formats():
    obs = [_obs("Giá niêm yết 4.200.000.000 ₫ trước thuế")]
    assert verifier.verify_reply("Giá khoảng 4,2 tỷ ạ.", obs).verified is True


# ─── Tool retry + offline planner ───────────────────────────────────────────


class _FlakyTool:
    """Tool lỗi lần đầu, thành công lần sau."""

    def __init__(self) -> None:
        self.calls = 0

    async def ainvoke(self, _args: dict[str, Any]) -> str:
        self.calls += 1
        if self.calls == 1:
            raise TimeoutError("tạm thời")
        return json.dumps({"summary": "Dữ liệu thật", "citations": []})


@pytest.mark.asyncio
async def test_execute_tool_retries_once_without_burning_iterations(monkeypatch):
    from src.agents.copilot import graph as graph_module

    flaky = _FlakyTool()
    monkeypatch.setitem(graph_module.TOOLS_BY_NAME, "tinh_phuong_an_thanh_toan", flaky)

    payload, raw, attempts = await graph_module._execute_tool(
        {"name": "tinh_phuong_an_thanh_toan", "args": {}}
    )
    assert attempts == 2
    assert flaky.calls == 2
    assert payload["summary"] == "Dữ liệu thật"
    assert json.loads(raw)["summary"] == "Dữ liệu thật"


@pytest.mark.asyncio
async def test_offline_multi_intent_runs_both_tools():
    """Offline (LLM chết) vẫn chạy đủ 2 bước của câu hỏi nhiều ý."""
    from tests.test_agents.copilot.test_copilot_react import FailingLLM  # type: ignore

    events = [
        (e.type, e.data)
        async for e in stream_copilot(
            CopilotRequest(
                message="Tính phương án cho căn ZEN-A-1205 rồi soạn tin tư vấn cho khách",
                current_unit="ZEN-A-1205",
                transaction_date="2026-09-26",
            ),
            llm=FailingLLM(),
        )
    ]
    actions = [d["tool"] for k, d in events if k == "action"]
    assert "tinh_phuong_an_thanh_toan" in actions
    assert "soan_tin_tu_van" in actions
    plan_events = [d for k, d in events if k == "plan"]
    assert plan_events and len(plan_events[0]["steps"]) >= 2
    final = next(d for k, d in events if k == "final")
    assert final["mode"] == "offline_react"
    # Bản nháp F8 + số liệu engine đều nằm trong câu trả lời tổng hợp
    assert "ZEN-A-1205" in final["reply"]


@pytest.mark.asyncio
async def test_final_reply_carries_verification_flag_on_hallucination():
    """Tool trả số thật nhưng LLM bịa số khác → final phải gắn verified=False + cảnh báo."""
    from tests.test_agents.copilot.test_copilot_react import FakeToolCallingLLM

    llm = FakeToolCallingLLM(
        [
            AIMessage(
                content="Em tra chính sách trước ạ.",
                tool_calls=[
                    {
                        "name": "tra_cuu_chinh_sach",
                        "args": {"cau_hoi": "chiết khấu thanh toán sớm", "ngay_hieu_luc": "2026-09-26"},
                        "id": "call-1",
                    }
                ],
            ),
            AIMessage(content="Dạ chính sách chiết khấu 99% cho mọi khách ạ."),
        ]
    )
    events = [
        (e.type, e.data)
        async for e in stream_copilot(
            CopilotRequest(message="chính sách chiết khấu thanh toán sớm thế nào?", transaction_date="2026-09-26"),
            llm=llm,
        )
    ]
    final = next(d for k, d in events if k == "final")
    assert final["verified"] is False
    assert final["verification"]["unsupported_claims"]
    # Chốt P2.4: nội dung trả lời giữ SẠCH để Sale copy gửi khách; cảnh báo nằm ở trường riêng.
    assert "chưa đối chiếu được" not in final["reply"]
    assert "chưa đối chiếu được" in final["internal_notes"]
    assert "99%" in final["internal_notes"], "Nêu đích danh con số không có nguồn"


def test_tools_module_exposes_retry_constants():
    from src.agents.copilot import graph as graph_module

    assert graph_module.TOOL_RETRIES >= 1
    assert graph_module.MAX_TOOL_MESSAGE_CHARS <= 2000
    assert TOOLS_BY_NAME["tra_cuu_ho_so_khach_hang"] is not None


# ─── Cache tool + ngân sách ngữ cảnh (P2) ────────────────────────────────────


class _CountingTool:
    """Tool đếm số lần thực sự chạy, để chứng minh cache có tác dụng."""

    def __init__(self, summary: str = "Giá niêm yết 4.2 tỷ") -> None:
        self.calls = 0
        self.summary = summary

    async def ainvoke(self, _args: dict[str, Any]) -> str:
        self.calls += 1
        return json.dumps({"summary": self.summary, "citations": []})


class _RepeatToolLLM:
    """LLM giả: hai vòng đầu gọi y hệt một tool (tham số đảo thứ tự), vòng ba chốt câu trả lời."""

    def __init__(self) -> None:
        self.calls = 0

    def bind_tools(self, _tools: Any) -> _RepeatToolLLM:
        return self

    async def ainvoke(self, _messages: Any) -> AIMessage:
        self.calls += 1
        if self.calls == 1:
            return AIMessage(
                content="",
                tool_calls=[{"id": "c1", "name": "tra_cuu_gio_hang", "args": {"so_phong_ngu": 2, "du_an": "ZEN"}}],
            )
        if self.calls == 2:
            return AIMessage(
                content="",
                tool_calls=[{"id": "c2", "name": "tra_cuu_gio_hang", "args": {"du_an": "ZEN", "so_phong_ngu": 2}}],
            )
        return AIMessage(content="Căn 2 ngủ của dự án ZEN còn hàng, giá niêm yết 4.2 tỷ.")


@pytest.mark.asyncio
async def test_identical_tool_call_in_same_turn_is_served_from_cache(monkeypatch):
    """Gọi lại y hệt một tool (khác thứ tự tham số) không chạy lại tool, chỉ đánh dấu cached."""
    from src.agents.copilot import graph as graph_module

    counter = _CountingTool()
    monkeypatch.setitem(graph_module.TOOLS_BY_NAME, "tra_cuu_gio_hang", counter)

    events = [
        event
        async for event in stream_copilot(
            CopilotRequest(message="Giỏ hàng còn căn 2 ngủ nào ở ZEN?"),
            llm=_RepeatToolLLM(),
        )
    ]
    observations = [e.data for e in events if e.type == "observation"]
    assert counter.calls == 1, "lần gọi thứ hai phải lấy từ cache"
    assert [o.get("cached") for o in observations] == [False, True]

    final = next(e.data for e in events if e.type == "final")
    assert final["context_budget"]["cached_tool_results"] == 1


@pytest.mark.asyncio
async def test_long_observation_is_trimmed_to_budget_without_breaking_json():
    """Observation dài bị rút gọn nhưng vẫn là JSON hợp lệ và giữ đầu (nơi có số liệu chính)."""
    from src.agents.copilot import graph as graph_module

    raw = json.dumps({"summary": "Số liệu chính. " + "chi tiết " * 500, "citations": [{"id": 1}]})
    out = graph_module._trim_with_budget(raw, remaining_budget=graph_module.MAX_TOTAL_OBSERVATION_CHARS)
    parsed = json.loads(out)  # không được cắt vỡ JSON
    assert parsed["truncated"] is True
    assert parsed["summary"].startswith("Số liệu chính.")
    assert parsed["citations"] == [{"id": 1}]

    tight = graph_module._trim_with_budget(raw, remaining_budget=300)
    assert len(tight) <= len(out)
