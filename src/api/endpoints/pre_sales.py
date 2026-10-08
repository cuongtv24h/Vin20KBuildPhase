"""
REST API endpoints cho Pre-Sales Advisory sessions (C-09).
Owner: Phase 2 — 6 endpoints theo spec mydoc/Excute.md.

Ranh giới: KHÔNG gọi KMS, KHÔNG ghi outbox, KHÔNG import official_quote.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import select

from src.agents.pre_sales.graph import PreSalesSessionRunner
from src.contracts.errors import DomainError, ErrorCode
from src.db.models import PreSalesSessionModel
from src.db.session import get_db_session
from src.orchestrator.checkpointer import get_app_checkpointer
from src.services.dossier.service import PreSalesDossierService

router = APIRouter(prefix="/api/v1/pre-sales", tags=["pre-sales"])

_runner: PreSalesSessionRunner | None = None
_dossier_service = PreSalesDossierService()


def get_runner(request: Request | None = None) -> PreSalesSessionRunner:
    """Lấy runner từ app state (nếu có) hoặc fallback module cache cho multi-process safety."""
    if request is not None and hasattr(request, "app") and hasattr(request.app.state, "pre_sales_runner"):
        runner = request.app.state.pre_sales_runner
        if runner is not None:
            return runner
    global _runner
    if _runner is None:
        _runner = PreSalesSessionRunner(checkpointer=get_app_checkpointer())
    return _runner


class SessionCreateRequest(BaseModel):
    tenant_id: str = "DEFAULT"
    initial_message: str | None = None
    transaction_date: str | None = None


class SessionMessageRequest(BaseModel):
    message: str


class SessionConstraintsConfirmRequest(BaseModel):
    confirmed: bool
    revised_constraints: dict[str, Any] | None = None


class SessionConsentRequest(BaseModel):
    consent_granted: bool
    customer_name: str
    customer_phone: str
    customer_email: str | None = None
    privacy_terms_acknowledged: bool


def _to_response(state: dict[str, Any], session_id: str) -> dict[str, Any]:
    """Chuyển LangGraph state thành payload REST an toàn (che PII)."""
    dossier_payload = state.get("dossier_payload") or {}
    return {
        "session_id": session_id,
        "tenant_id": state.get("tenant_id", "DEFAULT"),
        "status": state.get("status", "ACTIVE"),
        "collected_fields": state.get("collected_fields", []),
        "constraints": state.get("customer_constraints"),
        "constraints_confirmed": state.get("constraints_confirmed", False),
        "plan_id": state.get("plan_id"),
        "recommended_scenario_code": state.get("recommended_scenario_code"),
        "scenarios": state.get("scenarios", {}),
        "watermark_text": state.get("watermark_text"),
        "pdf_path": state.get("pdf_path"),
        "agent_message": state.get("agent_message"),
        "dossier_id": state.get("dossier_id"),
        "handoff_requested": state.get("decision") == "HANDOFF_CREATE_DOSSIER",
        "abstain_reason": state.get("abstain_reason"),
        "interrupt_gate": state.get("_interrupt_gate"),
        "customer_name": dossier_payload.get("customer_name"),
        "customer_phone_masked": dossier_payload.get("customer_phone_masked"),
        "updated_at": datetime.now(UTC).isoformat(),
    }


def _raise_http(exc: Exception) -> None:
    if isinstance(exc, DomainError):
        raise HTTPException(
            status_code=exc.http_status if exc.http_status >= 400 else 400,
            detail=exc.to_envelope().model_dump(),
        )
    raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/sessions", status_code=201)
async def create_session(payload: SessionCreateRequest, request: Request) -> dict[str, Any]:
    """[1/6] POST /sessions — PS-01: khởi tạo phiên tư vấn Pre-Sales (TTL 1800s).

    Persist row `pre_sales_sessions` ngay từ đầu: các endpoint sau (consent
    cần record_consent/get_session theo session_id) và GET /sessions phụ thuộc
    row này — nếu chỉ persist khi handoff sẽ dẫn tới NOT_FOUND/500.
    """
    try:
        session_id = f"PS-{datetime.now(UTC).strftime('%Y%m%d%H%M%S%f')}"
        state = await get_runner(request).start_session(
            tenant_id=payload.tenant_id,
            session_id=session_id,
            initial_message=payload.initial_message,
            transaction_date=payload.transaction_date,
        )
        # Persist session row (SLA/TTL 1800s) — khớp session_id với thread LangGraph
        async for db in get_db_session():
            await PreSalesDossierService().create_session(
                db,
                tenant_id=payload.tenant_id,
                initial_message=payload.initial_message,
                session_id=session_id,
            )
            await db.commit()
        return _to_response(state, session_id)
    except Exception as exc:
        _raise_http(exc)


@router.post("/sessions/{session_id}/messages")
async def submit_message(
    session_id: str,
    payload: SessionMessageRequest,
    request: Request,
    tenant_id: str = "DEFAULT",
) -> dict[str, Any]:
    """[2/6] POST /sessions/{id}/messages — resume interrupt chờ tin nhắn (PS-02)."""
    try:
        state = await get_runner(request).submit_message(tenant_id, session_id, payload.message)
        return _to_response(state, session_id)
    except Exception as exc:
        _raise_http(exc)


@router.post("/sessions/{session_id}/constraints/confirm")
async def confirm_constraints(
    session_id: str,
    payload: SessionConstraintsConfirmRequest,
    request: Request,
    tenant_id: str = "DEFAULT",
) -> dict[str, Any]:
    """[3/6] POST /sessions/{id}/constraints/confirm — resume interrupt PS-04."""
    try:
        state = await get_runner(request).confirm_constraints(
            tenant_id,
            session_id,
            payload.model_dump(),
        )
        return _to_response(state, session_id)
    except Exception as exc:
        _raise_http(exc)


@router.post("/sessions/{session_id}/consent")
async def submit_consent(
    session_id: str,
    payload: SessionConsentRequest,
    request: Request,
    tenant_id: str = "DEFAULT",
) -> dict[str, Any]:
    """[4/6] POST /sessions/{id}/consent — resume interrupt PS-10 + persist dossier."""
    try:
        state = await get_runner(request).provide_consent(
            tenant_id, session_id, payload.model_dump()
        )
        response = _to_response(state, session_id)

        # Persist LeadDossier + CustomerConsent khi khách đồng ý handoff
        if state.get("decision") == "HANDOFF_CREATE_DOSSIER":
            async for db in get_db_session():
                dossier_service = PreSalesDossierService()
                await dossier_service.record_consent(
                    db,
                    session_id=session_id,
                    customer_name=payload.customer_name,
                    customer_phone=payload.customer_phone,
                    customer_email=payload.customer_email,
                )
                # Phân công luôn Sale phụ trách (người ít hồ sơ chờ nhất) và ghi người tạo = người đó:
                # hồ sơ khách tự bàn giao mà vô chủ thì chỉ ADMIN xoá/sửa được, Sale không thấy khách của mình.
                dossier = await dossier_service.create_handoff_dossier(
                    db,
                    session_id=session_id,
                    customer_name=payload.customer_name,
                    customer_phone=payload.customer_phone,
                    constraints=state.get("customer_constraints"),
                    plan_id=state.get("plan_id"),
                )
                await db.commit()
                response["dossier_id"] = dossier.dossier_id
                response["assigned_sales_id"] = dossier.assigned_sales_id
        return response
    except Exception as exc:
        _raise_http(exc)


@router.get("/sessions/{session_id}")
async def get_session(
    session_id: str,
    request: Request,
    tenant_id: str = "DEFAULT",
) -> dict[str, Any]:
    """[5/6] GET /sessions/{id} — xem trạng thái hiện tại của phiên."""
    try:
        runner = get_runner(request)
        snapshot = await runner.graph.aget_state(
            runner.build_config(tenant_id, session_id)
        )
        if not snapshot.values:
            raise DomainError(
                ErrorCode.NOT_FOUND,
                f"Session '{session_id}' không tồn tại.",
            )
        return _to_response(dict(snapshot.values), session_id)
    except Exception as exc:
        _raise_http(exc)


@router.get("/sessions")
async def list_sessions(limit: int = 20) -> dict[str, Any]:
    """[6/6] GET /sessions — liệt kê các phiên gần nhất (theo checkpoint state)."""
    # Phase 2 MVP: liệt kê từ DB pre_sales_sessions
    try:
        result: dict[str, Any] = {"items": [], "count": 0, "limit": limit}
        async for db in get_db_session():

            rows = (
                (
                    await db.execute(
                        select(PreSalesSessionModel)
                        .order_by(PreSalesSessionModel.created_at.desc())
                        .limit(limit)
                    )
                )
                .scalars()
                .all()
            )
            result["items"] = [
                {
                    "session_id": r.session_id,
                    "status": r.status,
                    "created_at": r.created_at.isoformat() if r.created_at else None,
                    "expires_at": r.expires_at.isoformat() if r.expires_at else None,
                }
                for r in rows
            ]
            result["count"] = len(result["items"])
        return result
    except Exception as exc:
        _raise_http(exc)
