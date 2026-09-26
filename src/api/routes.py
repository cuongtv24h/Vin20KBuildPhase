from fastapi import APIRouter, HTTPException

from src.agents.graph import agent
from src.api.endpoints import (
    compliance,
    evaluation,
    leads,
    policies,
    pre_sales,
    quote_events,
    quotes,
)
from src.models.schemas import ChatRequest, ChatResponse

router = APIRouter()

# Routers nghiệp vụ PricePolicy AI Agent (hợp đồng TD-4.4).
# Lưu ý: /chat, /status bên dưới là code mẫu của template — sẽ thay bằng
# pre_sales + quotes flow khi C-01/C-09 hoàn thành.
router.include_router(quotes.router)
router.include_router(quote_events.router)
router.include_router(pre_sales.router)
router.include_router(leads.router)
router.include_router(compliance.router)
router.include_router(policies.router)
router.include_router(evaluation.router)


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse:
    """Chat với AI agent."""
    try:
        result = await agent.ainvoke({"query": request.message})
        return ChatResponse(
            response=result.get("response", ""),
            analysis=result.get("analysis", ""),
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/status")
async def agent_status():
    """Kiểm tra trạng thái agent."""
    return {"status": "ready", "agent": "LangGraph Agent v1.0"}
