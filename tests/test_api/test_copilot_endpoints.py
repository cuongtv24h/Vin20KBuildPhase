"""Test API hợp đồng cho Sales Copilot: /copilot/chat và /copilot/chat/stream."""

from __future__ import annotations

from typing import Any

import pytest
from langchain_core.messages import AIMessage

from src.agents.copilot.graph import CopilotRequest


class FakeService:
    """Service giả — bơm kết quả ReAct đã dựng sẵn để test tầng HTTP."""

    payload: dict[str, Any] = {
        "reply": "Dạ, chiết khấu thanh toán sớm là 8.0% [CSBH-ZEN-2026-V3.1 · Điều 4, Khoản 2b].",
        "action_type": None,
        "action_data": None,
        "suggested_actions": ["Lập báo giá cho căn này"],
        "citations": [
            {
                "policy_id": "CSBH-ZEN-2026-V3.1",
                "section": "Điều 4, Khoản 2b",
                "quote": "chiết khấu 8.0% trên giá bán chưa bao gồm thuế GTGT và KPBT",
                "source": "CANONICAL_FIXTURE",
            }
        ],
        "grounded": True,
        "tools_used": ["tra_cuu_chinh_sach"],
        "iterations": 2,
        "mode": "react",
        "reasoning": [
            {"type": "thought", "text": "Cần tra chính sách trước."},
            {"type": "action", "tool": "tra_cuu_chinh_sach", "args": {}, "ok": None},
            {"type": "observation", "tool": "tra_cuu_chinh_sach", "ok": True, "text": "8.0%"},
            {"type": "final", "text": "Dạ, 8.0%."},
        ],
    }

    def __init__(self, *_: Any, **__: Any) -> None:
        pass

    async def run(self, request: CopilotRequest) -> dict[str, Any]:
        return dict(self.payload)

    async def stream(self, request: CopilotRequest):
        for step in self.payload["reasoning"]:
            yield _Event(step["type"], step)


class _Event:
    def __init__(self, type_: str, data: dict[str, Any]) -> None:
        self.type = type_
        self.data = data


@pytest.mark.asyncio
async def test_copilot_chat_returns_reasoning_and_citations(client, monkeypatch):
    monkeypatch.setattr("src.api.endpoints.copilot.CopilotService", FakeService)

    resp = await client.post(
        "/api/v1/copilot/chat",
        json={"message": "chính sách thanh toán sớm?", "current_unit": "ZEN-A-1205"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["grounded"] is True
    assert body["citations"][0]["policy_id"] == "CSBH-ZEN-2026-V3.1"
    assert body["iterations"] == 2
    assert body["reasoning"][0]["type"] == "thought"


@pytest.mark.asyncio
async def test_copilot_chat_rejects_empty_message(client):
    resp = await client.post("/api/v1/copilot/chat", json={"message": "   "})
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_copilot_stream_emits_sse_frames(client, monkeypatch):
    monkeypatch.setattr("src.api.endpoints.copilot.CopilotService", FakeService)

    async with client.stream(
        "POST", "/api/v1/copilot/chat/stream", json={"message": "chính sách thanh toán sớm?"}
    ) as resp:
        assert resp.status_code == 200
        raw = ""
        async for chunk in resp.aiter_text():
            raw += chunk
            if '"type": "final"' in raw:
                break

    assert "event: copilot" in raw
    assert '"type": "thought"' in raw
    assert '"type": "final"' in raw


@pytest.mark.asyncio
async def test_react_loop_wires_into_endpoint_payload_shape():
    """Chạy thẳng service thật với LLM giả để chắc chắn shape khớp response model."""
    from src.agents.copilot.service import CopilotService

    class _LLM:
        def bind_tools(self, tools: list[Any]) -> _LLM:
            return self

        async def ainvoke(self, messages: list[Any]) -> AIMessage:
            return AIMessage(content="Dạ em sẵn sàng hỗ trợ anh ạ.")

    payload = await CopilotService(llm_factory=_LLM).run(CopilotRequest(message="xin chào"))
    for key in ("reply", "action_type", "action_data", "suggested_actions", "citations", "grounded", "iterations", "mode"):
        assert key in payload


# ─── Phản hồi của Sale (P2 — học từ phản hồi) ───────────────────────────────


@pytest.mark.asyncio
async def test_feedback_endpoint_records_and_returns_summary(client, tmp_path, monkeypatch):
    monkeypatch.setenv("COPILOT_FEEDBACK_PATH", str(tmp_path / "feedback.jsonl"))
    resp = await client.post(
        "/api/v1/copilot/feedback",
        json={
            "message": "Chiết khấu thanh toán sớm là bao nhiêu?",
            "reply": "8.0% [CSBH-ZEN-2026-V3.1]",
            "rating": -1,
            "comment": "thiếu điều kiện áp dụng",
            "tags": ["thieu_dieu_kien"],
            "mode": "react",
            "tools_used": ["tra_cuu_chinh_sach"],
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    assert body["summary"]["total"] == 1
    assert body["summary"]["down"] == 1

    summary = await client.get("/api/v1/copilot/feedback/summary")
    assert summary.status_code == 200
    assert summary.json()["total"] == 1
    assert summary.json()["top_negative_tags"] == [["thieu_dieu_kien", 1]]


@pytest.mark.asyncio
async def test_feedback_endpoint_rejects_out_of_range_rating(client, tmp_path, monkeypatch):
    monkeypatch.setenv("COPILOT_FEEDBACK_PATH", str(tmp_path / "feedback.jsonl"))
    resp = await client.post("/api/v1/copilot/feedback", json={"message": "x", "rating": 5})
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_feedback_endpoint_is_empty_safe_before_any_vote(client, tmp_path, monkeypatch):
    monkeypatch.setenv("COPILOT_FEEDBACK_PATH", str(tmp_path / "chua-ton-tai.jsonl"))
    resp = await client.get("/api/v1/copilot/feedback/summary")
    assert resp.status_code == 200
    assert resp.json()["total"] == 0
    assert resp.json()["satisfaction_rate"] is None
