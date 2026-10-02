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

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from pydantic import BaseModel, Field
from sse_starlette.sse import EventSourceResponse

from src.agents.copilot import CopilotService
from src.agents.copilot.graph import CopilotRequest
from src.api.deps import Principal, get_current_principal

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
    critique: dict[str, Any] = Field(default_factory=dict, description="Critic vòng 2: {ok, issues[], hints[]}")
    context_budget: dict[str, Any] = Field(default_factory=dict, description="Chi phí ngữ cảnh của lượt (P2)")
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

class CopilotFeedbackRequest(BaseModel):
    """Phản hồi của Sale về một lượt trả lời (P2 — học từ phản hồi)."""

    message: str = Field(min_length=1, description="Câu hỏi của Sale ở lượt đó")
    reply: str | None = Field(default=None, description="Câu trả lời của Copilot (để đối chiếu)")
    rating: int = Field(description="1 = hữu ích, -1 = chưa đạt, 0 = trung tính", ge=-1, le=1)
    comment: str | None = Field(default=None, description="Lý do (tuỳ chọn)")
    tags: list[str] = Field(default_factory=list, description="Nhãn lỗi: sai_số, thieu_can_cu, kho_hieu…")
    mode: str | None = Field(default=None, description="react | offline_react | guardrail")
    tools_used: list[str] = Field(default_factory=list)
    turn_id: str | None = None


class CopilotFeedbackSummary(BaseModel):
    """Thống kê tổng hợp — KHÔNG chứa nội dung hội thoại nên an toàn để trả cho mọi nhân viên."""

    total: int
    up: int
    down: int
    neutral: int
    satisfaction_rate: float | None = None
    top_negative_tags: list[list[Any]] = Field(default_factory=list)
    by_mode: list[dict[str, Any]] = Field(default_factory=list, description="Phân bố theo chế độ trả lời")
    by_day: list[dict[str, Any]] = Field(default_factory=list, description="Xu hướng 14 ngày: {date, up, down}")
    top_failing_tools: list[list[Any]] = Field(default_factory=list, description="Tool hay xuất hiện ở lượt bị chê")
    recent_negative: list[dict[str, Any]] = Field(default_factory=list, description="5 lượt bị chê gần nhất (đã che PII)")


class CopilotFeedbackEntry(BaseModel):
    """Một dòng phản hồi trong trang quản trị chất lượng (đã che PII)."""

    recorded_at: str | None = None
    rating: int
    label: str
    message: str = ""
    reply: str = ""
    comment: str = ""
    tags: list[str] = Field(default_factory=list)
    mode: str | None = None
    tools_used: list[str] = Field(default_factory=list)
    turn_id: str | None = None


class CopilotFeedbackRecentResponse(BaseModel):
    total: int
    items: list[CopilotFeedbackEntry] = Field(default_factory=list)


class CopilotFeedbackResponse(BaseModel):
    ok: bool
    recorded_at: str
    summary: CopilotFeedbackSummary

@router.post("/feedback", response_model=CopilotFeedbackResponse)
async def copilot_feedback(req: CopilotFeedbackRequest) -> CopilotFeedbackResponse:
    """Ghi nhận đánh giá của Sale và trả về thống kê tích luỹ.

    Không có DB migration: log append-only JSONL (`COPILOT_FEEDBACK_PATH`). Những câu bị chê
    được dùng làm "điều cần tránh" trong system prompt của các lượt sau.
    """
    from src.agents.copilot import feedback as feedback_module

    entry = feedback_module.record_feedback(
        message=req.message,
        reply=req.reply or "",
        rating=req.rating,
        comment=req.comment or "",
        tags=req.tags,
        mode=req.mode,
        tools_used=req.tools_used,
        turn_id=req.turn_id,
    )
    summary = feedback_module.summarize_feedback()
    return CopilotFeedbackResponse(
        ok=True,
        recorded_at=str(entry["recorded_at"]),
        summary=CopilotFeedbackSummary(**summary),
    )


@router.get("/feedback/recent", response_model=CopilotFeedbackRecentResponse)
async def copilot_feedback_recent(
    limit: int = Query(50, ge=1, le=200),
    rating: int | None = Query(None, ge=-1, le=1, description="Lọc theo điểm: 1 hữu ích, -1 chưa đạt"),
    principal: Principal = Depends(get_current_principal),
) -> CopilotFeedbackRecentResponse:
    """Danh sách phản hồi gần nhất cho **trang quản trị chất lượng** (ADMIN / POLICY_ADMIN).

    Trả về nội dung hội thoại nên siết quyền và **che PII** (SĐT/email) trước khi rời server —
    trang chất lượng cần đọc *câu hỏi và câu trả lời* để đánh giá Copilot, không cần dữ liệu khách.
    """
    if not principal.has_role("ADMIN", "POLICY_ADMIN"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Chỉ Quản trị viên hệ thống hoặc Quản trị chính sách được xem phản hồi chi tiết.",
        )

    from src.agents.copilot import feedback as feedback_module

    items = feedback_module.list_recent(limit=limit, rating=rating, mask=True)
    return CopilotFeedbackRecentResponse(total=len(items), items=[CopilotFeedbackEntry(**i) for i in items])


@router.get("/feedback/summary", response_model=CopilotFeedbackSummary)
async def copilot_feedback_summary() -> CopilotFeedbackSummary:
    """Thống kê phản hồi tích luỹ (dùng cho dashboard chất lượng)."""
    from src.agents.copilot import feedback as feedback_module

    return CopilotFeedbackSummary(**feedback_module.summarize_feedback())



# ─── Lịch sử hội thoại (giữ và tra cứu lại được) ──────────────────────────────
# Trước đây hội thoại chỉ nằm trong state React nên đổi trang là mất. Bốn endpoint dưới
# lưu theo từng nhân viên (chủ sở hữu đọc/ghi, không ai xem được của người khác).


def require_staff_principal(
    authorization: str | None = Header(None, alias="Authorization"),
    principal: Principal = Depends(get_current_principal),
) -> Principal:
    """Lịch sử hội thoại là dữ liệu riêng của từng nhân viên → bắt buộc có phiên đăng nhập.

    `get_current_principal` mặc định trả về khách "SALES-001" khi thiếu header (di sản của các
    endpoint chỉ đọc dữ liệu công khai), nên ở đây phải chặn hẳn để không ai ghi/đọc nhờ bucket mặc định.
    """
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Cần đăng nhập để xem lịch sử hội thoại Copilot.",
        )
    return principal


class ConversationMessage(BaseModel):
    role: str = Field(..., description="'user' | 'assistant'")
    content: str
    at: str | None = None
    citations: list[dict[str, Any]] = Field(default_factory=list)
    action_type: str | None = None


class ConversationSummary(BaseModel):
    conversation_id: str
    title: str
    created_at: str | None = None
    updated_at: str | None = None
    message_count: int = 0
    last_message: str = ""


class ConversationDetail(ConversationSummary):
    messages: list[ConversationMessage] = Field(default_factory=list)


class ConversationListResponse(BaseModel):
    total: int
    items: list[ConversationSummary]


class CreateConversationRequest(BaseModel):
    title: str | None = None


class AppendTurnRequest(BaseModel):
    conversation_id: str | None = Field(None, description="Bỏ trống để tạo cuộc mới")
    user_message: str
    assistant_message: str
    citations: list[dict[str, Any]] = Field(default_factory=list)
    action_type: str | None = None


class RenameConversationRequest(BaseModel):
    title: str


@router.get("/conversations", response_model=ConversationListResponse)
async def copilot_list_conversations(
    limit: int = Query(30, ge=1, le=100),
    principal: Principal = Depends(require_staff_principal),
) -> ConversationListResponse:
    """Lịch sử hội thoại của **chính nhân viên đang đăng nhập** (mới nhất trước)."""
    from src.agents.copilot import history as history_module

    items = history_module.list_conversations(principal.user_id, limit=limit)
    return ConversationListResponse(total=len(items), items=[ConversationSummary(**i) for i in items])


@router.post("/conversations", response_model=ConversationDetail, status_code=status.HTTP_201_CREATED)
async def copilot_create_conversation(
    req: CreateConversationRequest | None = None,
    principal: Principal = Depends(require_staff_principal),
) -> ConversationDetail:
    """Mở cuộc hội thoại mới (Sale bấm "Cuộc trò chuyện mới")."""
    from src.agents.copilot import history as history_module

    created = history_module.create_conversation(principal.user_id, (req.title if req else None))
    return ConversationDetail(**created)


@router.get("/conversations/{conversation_id}", response_model=ConversationDetail)
async def copilot_get_conversation(
    conversation_id: str,
    principal: Principal = Depends(require_staff_principal),
) -> ConversationDetail:
    """Đọc lại một cuộc hội thoại cũ (chỉ chủ sở hữu)."""
    from src.agents.copilot import history as history_module

    found = history_module.get_conversation(principal.user_id, conversation_id)
    if not found:
        raise HTTPException(status_code=404, detail="Không tìm thấy cuộc hội thoại này.")
    return ConversationDetail(**found)


@router.post("/conversations/turns", response_model=ConversationDetail, status_code=status.HTTP_201_CREATED)
async def copilot_append_turn(
    req: AppendTurnRequest,
    principal: Principal = Depends(require_staff_principal),
) -> ConversationDetail:
    """Ghi một lượt hỏi–đáp vào hội thoại (tự tạo cuộc mới nếu chưa có `conversation_id`)."""
    from src.agents.copilot import history as history_module

    if not (req.user_message.strip() or req.assistant_message.strip()):
        raise HTTPException(status_code=422, detail="Lượt hội thoại phải có nội dung.")
    updated = history_module.append_turn(
        principal.user_id,
        conversation_id=req.conversation_id,
        user_message=req.user_message,
        assistant_message=req.assistant_message,
        citations=req.citations,
        action_type=req.action_type,
    )
    return ConversationDetail(**updated)


@router.patch("/conversations/{conversation_id}", response_model=ConversationSummary)
async def copilot_rename_conversation(
    conversation_id: str,
    req: RenameConversationRequest,
    principal: Principal = Depends(require_staff_principal),
) -> ConversationSummary:
    from src.agents.copilot import history as history_module

    updated = history_module.rename_conversation(principal.user_id, conversation_id, req.title)
    if not updated:
        raise HTTPException(status_code=404, detail="Không tìm thấy cuộc hội thoại này.")
    return ConversationSummary(**updated)


@router.delete("/conversations/{conversation_id}", status_code=status.HTTP_200_OK)
async def copilot_delete_conversation(
    conversation_id: str,
    principal: Principal = Depends(require_staff_principal),
) -> dict[str, Any]:
    from src.agents.copilot import history as history_module

    if not history_module.delete_conversation(principal.user_id, conversation_id):
        raise HTTPException(status_code=404, detail="Không tìm thấy cuộc hội thoại này.")
    return {"ok": True, "conversation_id": conversation_id}
