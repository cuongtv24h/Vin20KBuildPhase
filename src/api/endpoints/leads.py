"""
REST API endpoints quản lý Lead Dossiers (C-10).
Owner: Phase 2 — 2 endpoints theo spec mydoc/Excute.md.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from src.contracts.dossier import LeadTemperature
from src.contracts.enums import LeadDossierStatus
from src.contracts.errors import DomainError
from src.db.models import LeadDossierModel
from src.db.session import get_db_session
from src.services.dossier.service import PreSalesDossierService

router = APIRouter(prefix="/api/v1/leads", tags=["leads"])


class LeadDossierCreateRequest(BaseModel):
    session_id: str
    customer_name: str
    customer_phone: str
    own_funds_vnd: int = 0
    total_contract_price_vnd: int = 0
    plan_id: str | None = None
    lead_temperature: LeadTemperature = LeadTemperature.WARM


class AssignSalesRequest(BaseModel):
    sales_id: str


def _dossier_to_response(d: LeadDossierModel) -> dict[str, Any]:
    return {
        "dossier_id": d.dossier_id,
        "session_id": d.session_id,
        "status": d.status,
        "lead_temperature": d.lead_temperature,
        "customer_name": d.customer_name,
        "customer_phone_masked": d.customer_phone_masked,
        "assigned_sales_id": d.assigned_sales_id,
        "sla_expires_at": d.sla_expires_at.isoformat() if d.sla_expires_at else None,
        "sla_expired": bool(
            d.sla_expires_at
            and d.sla_expires_at.replace(tzinfo=UTC) < datetime.now(UTC)
            and d.status == LeadDossierStatus.NEW.value
        ),
        "quote_id": d.quote_id,
        "created_at": d.created_at.isoformat() if d.created_at else None,
    }


@router.post("/dossiers", status_code=201)
async def create_dossier(payload: LeadDossierCreateRequest) -> dict[str, Any]:
    """[1/2] POST /leads/dossiers — tạo LeadDossier thủ công (SLA 15 phút)."""
    try:
        async for db in get_db_session():
            service = PreSalesDossierService()
            dossier = await service.create_dossier(
                db,
                session_id=payload.session_id,
                customer_name=payload.customer_name,
                customer_phone=payload.customer_phone,
                constraints={
                    "own_funds_vnd": payload.own_funds_vnd,
                    "total_contract_price_vnd": payload.total_contract_price_vnd,
                },
                plan_id=payload.plan_id,
                lead_temperature=payload.lead_temperature,
            )
            await db.commit()
            return _dossier_to_response(dossier)
    except Exception as exc:
        _raise_http(exc)


@router.get("/dossiers")
async def list_dossiers(status: str | None = None, limit: int = 50) -> dict[str, Any]:
    """[2/2] GET /leads/dossiers — danh sách hồ sơ cho Sales Dashboard (SLA gấp nhất trước)."""
    try:
        status_enum = LeadDossierStatus(status) if status else None
        async for db in get_db_session():
            service = PreSalesDossierService()
            dossiers = await service.list_dossiers(db, status=status_enum, limit=limit)
            return {
                "items": [_dossier_to_response(d) for d in dossiers],
                "count": len(dossiers),
            }
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid status filter: {status}")
    except Exception as exc:
        _raise_http(exc)


def _raise_http(exc: Exception) -> None:
    if isinstance(exc, DomainError):
        raise HTTPException(
            status_code=exc.http_status if exc.http_status >= 400 else 400,
            detail=exc.to_envelope().model_dump(),
        )
    raise HTTPException(status_code=500, detail=str(exc)) from exc
