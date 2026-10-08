"""
API Routes Master Aggregator (Mounting all 7 sub-routers - 29 Canonical Endpoints).
Owner: TechLead (cuongtv_02560)
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from src.agents.graph import agent
from src.api.endpoints import (
    admin_cp,
    catalog,
    compliance,
    copilot,
    evaluation,
    leads,
    llm_admin,
    policies,
    pre_sales,
    quote_events,
    quotes,
    settings,
    stt,
    tts_admin,
    tts_speak,
)
from src.models.schemas import ChatRequest, ChatResponse

# Master Router aggregating all domain sub-routers
router = APIRouter()

# -----------------------------------------------------------------------------
# Base Chat & Status Endpoints
# -----------------------------------------------------------------------------
base_router = APIRouter(prefix="/api/v1", tags=["base"])


@base_router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse:
    """Chat với AI agent cơ bản."""
    try:
        result = await agent.ainvoke({"query": request.message})
        return ChatResponse(
            response=result.get("response", ""),
            analysis=result.get("analysis", ""),
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@base_router.get("/status")
async def agent_status():
    """Kiểm tra trạng thái agent."""
    return {"status": "ready", "agent": "LangGraph Agent v1.0"}


# -----------------------------------------------------------------------------
# Mount All Domain Sub-Routers
# -----------------------------------------------------------------------------
router.include_router(base_router)
router.include_router(catalog.router)
router.include_router(admin_cp.router)
router.include_router(pre_sales.router)
router.include_router(leads.router)
router.include_router(quotes.router)
router.include_router(quote_events.router)
router.include_router(compliance.router)
router.include_router(evaluation.router)
router.include_router(llm_admin.router, prefix="/api/v1")
router.include_router(tts_admin.router, prefix="/api/v1")
router.include_router(tts_speak.router, prefix="/api/v1")
router.include_router(stt.router, prefix="/api/v1")
router.include_router(settings.router, prefix="/api/v1")
router.include_router(copilot.router, prefix="/api/v1")
router.include_router(policies.router, prefix="/api/v1")

api_router = router
