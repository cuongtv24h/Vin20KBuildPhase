"""Dịch vụ Sales Copilot — lớp điều phối giữa API và ReAct loop."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator, Callable
from typing import Any

from src.agents.copilot.graph import CopilotEvent, CopilotRequest, stream_copilot

logger = logging.getLogger(__name__)


class CopilotService:
    """Bọc `stream_copilot` cho endpoint: chạy gom (chat) hoặc chạy stream (SSE).

    `llm_factory` được bơm từ ngoài để test có thể thay LLM giả — không cần API key.
    """

    def __init__(self, llm_factory: Callable[[], Any] | None = None, max_iterations: int = 4) -> None:
        self._llm_factory = llm_factory
        self._max_iterations = max_iterations

    async def stream(self, request: CopilotRequest) -> AsyncIterator[CopilotEvent]:
        async for event in stream_copilot(
            request,
            llm_factory=self._llm_factory,
            max_iterations=self._max_iterations,
        ):
            yield event

    async def run(self, request: CopilotRequest) -> dict[str, Any]:
        """Chạy hết vòng lặp, trả về payload cuối + trace đầy đủ."""
        trace: list[dict[str, Any]] = []
        final: dict[str, Any] | None = None
        async for event in self.stream(request):
            if event.type == "final":
                final = dict(event.data)
            trace.append({"type": event.type, **event.data})

        if final is None:  # phòng hờ: loop không phát final
            final = {
                "reply": "Em chưa xử lý được yêu cầu này. Anh/chị thử diễn đạt lại giúp em nhé.",
                "action_type": None,
                "action_data": None,
                "suggested_actions": [],
                "citations": [],
                "grounded": False,
                "tools_used": [],
                "iterations": 0,
                "mode": "error",
                "verified": False,
                "verification": {"verified": False, "reason": "loop không phát final"},
                "plan": [],
                "slots": {},
            }
        final["reasoning"] = trace
        return final


__all__ = ["CopilotService"]
