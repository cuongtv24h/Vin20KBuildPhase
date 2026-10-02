"""
Sales Copilot AI Chat Endpoint (SCR-S00) — phiên bản ReAct Agent.

Nâng cấp so với bản single-shot cũ:
- Vòng lặp ReAct thật (Thought → Action → Observation) với 6 tool nghiệp vụ.
- Grounding bắt buộc: mọi số liệu/điều khoản đến từ tool, kèm `citations`.
- Stream tiến trình suy luận real-time qua SSE (`/copilot/chat/stream`).
- Guardrail đầu vào (prompt injection) & đầu ra (rò rỉ nội bộ).
- Offline mode: LLM lỗi vẫn suy luận tất định + gọi tool thật (demo không cần API key).

Tương thích ngược: `POST /api/v1/copilot/chat` giữ nguyên các trường cũ
(reply, action_type, action_data, suggested_actions) và bổ sung trường mới.
"""

from __future__ import annotations

import json
import logging
from collections.abc import AsyncIterator
from typing import Any

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field
from sse_starlette.sse import EventSourceResponse

from src.agents.copilot import CopilotService
from src.agents.copilot.graph import CopilotRequest

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/copilot", tags=["copilot"])


class ChatMessageItem(BaseModel):
    role: str = Field(..., description="'user' | 'assistant' | 'agent'")
    content: str


class CopilotChatRequest(BaseModel):
    message: str = Field(..., min_length=1, description="Nội dung câu hỏi của Sale")
    history: list[ChatMessageItem] = Field(default_factory=list, description="Lịch sử hội thoại gần nhất")
    current_unit: str | None = Field(None, description="Mã căn đang xem nếu có")
    lead_dossier_id: str | None = Field(None, description="Mã hồ sơ khách hàng đang xem nếu có")
    transaction_date: str | None = Field(None, description="Ngày giao dịch tham chiếu YYYY-MM-DD")
    project_id: str | None = Field(None, description="Dự án đang làm việc")


class CopilotReasoningStep(BaseModel):
    """Một bước suy luận để UI hiển thị timeline."""

    type: str = Field(..., description="guardrail | plan | thought | action | observation")
    text: str | None = None
    tool: str | None = None
    args: dict[str, Any] | None = None
    ok: bool | None = None
    error_code: str | None = None
    attempts: int | None = None
    citations: list[dict[str, Any]] = Field(default_factory=list)
    steps: list[dict[str, Any]] = Field(default_factory=list, description="Bước của planner (event plan)")


class CopilotChatResponse(BaseModel):
    reply: str
    action_type: str | None = None
    action_data: dict[str, Any] | None = None
    suggested_actions: list[str] = Field(default_factory=list)
    citations: list[dict[str, Any]] = Field(default_factory=list, description="Căn cứ đã dùng để trả lời")
    grounded: bool = Field(False, description="Câu trả lời đã đối chiếu dữ liệu chính sách/giỏ hàng chưa")
    tools_used: list[str] = Field(default_factory=list)
    iterations: int = 0
    mode: str = Field("react", description="react | offline_react | error")
    verified: bool = Field(True, description="Mọi số liệu trong câu trả lời có trong Observation không")
    verification: dict[str, Any] = Field(default_factory=dict, description="Chi tiết kết quả kiểm chứng")
    plan: list[dict[str, Any]] = Field(default_factory=list, description="Kế hoạch nhiều bước của planner")
    slots: dict[str, Any] = Field(default_factory=dict, description="Ngữ cảnh phiên đã chốt (căn/hồ sơ/ngày)")
    reasoning: list[dict[str, Any]] = Field(default_factory=list, description="Trace đầy đủ các bước ReAct")


def _to_request(req: CopilotChatRequest) -> CopilotRequest:
    return CopilotRequest(
        message=req.message,
        history=[{"role": h.role, "content": h.content} for h in req.history],
        current_unit=req.current_unit,
        lead_dossier_id=req.lead_dossier_id,
        transaction_date=req.transaction_date,
        project_id=req.project_id,
    )


@router.post("/chat", response_model=CopilotChatResponse)
async def copilot_chat(req: CopilotChatRequest) -> CopilotChatResponse:
    """Chat với Sales Copilot (ReAct + tool grounding, không stream)."""
    user_msg = req.message.strip()
    if not user_msg:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Tin nhắn không được để trống.",
        )

    service = CopilotService()
    payload = await service.run(_to_request(req))
    return CopilotChatResponse(**{k: v for k, v in payload.items() if k in CopilotChatResponse.model_fields})


@router.post("/chat/stream")
async def copilot_chat_stream(req: CopilotChatRequest) -> EventSourceResponse:
    """Chat với Sales Copilot — stream từng bước ReAct bằng SSE.

    Mỗi frame: `event: copilot`, `data: {"type": "...", ...}`.
    UI dùng để vẽ timeline suy luận thật thay cho spinner giả.
    """

    async def event_generator() -> AsyncIterator[dict[str, str]]:
        service = CopilotService()
        try:
            async for event in service.stream(_to_request(req)):
                yield {"event": "copilot", "data": json.dumps({"type": event.type, **event.data}, ensure_ascii=False, default=str)}
        except Exception as exc:  # noqa: BLE001 — stream không được vỡ giữa chừng
            logger.error("Copilot stream lỗi: %s", exc, exc_info=True)
            yield {
                "event": "copilot",
                "data": json.dumps(
                    {
                        "type": "error",
                        "message": "Trợ lý gặp sự cố khi xử lý. Anh/chị thử lại giúp em nhé.",
                    },
                    ensure_ascii=False,
                ),
            }

    return EventSourceResponse(event_generator(), ping=15)
