"""
REST API endpoints quản lý Lead Dossiers (C-10).
Owner: Phase 2 — 2 endpoints theo spec mydoc/Excute.md.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, ConfigDict

from src.api.deps import Principal, get_current_principal
from src.contracts.dossier import LeadTemperature
from src.contracts.enums import LeadDossierStatus
from src.contracts.errors import DomainError
from src.db.models import LeadDossierModel
from src.db.session import get_db_session
from src.services.dossier.service import PreSalesDossierService

router = APIRouter(prefix="/api/v1/leads", tags=["leads"])


class LeadDossierCreateRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    session_id: str | None = None
    customer_name: str
    customer_phone: str
    customer_segment: str | None = None
    project_id: str | None = None
    preferred_unit_code: str | None = None
    bedrooms: int | None = None
    own_funds_vnd: int = 0
    monthly_capacity_vnd: int = 0
    total_contract_price_vnd: int = 0
    objective: str | None = None
    needs_summary: str | None = None
    plan_id: str | None = None
    lead_temperature: LeadTemperature = LeadTemperature.WARM


class LeadDossierUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    customer_name: str | None = None
    customer_phone: str | None = None
    customer_segment: str | None = None
    project_id: str | None = None
    preferred_unit_code: str | None = None
    bedrooms: int | None = None
    own_funds_vnd: int | None = None
    monthly_capacity_vnd: int | None = None
    total_contract_price_vnd: int | None = None
    objective: str | None = None
    needs_summary: str | None = None
    lead_temperature: str | None = None
    status: str | None = None
    assigned_sales_id: str | None = None


class AssignSalesRequest(BaseModel):
    sales_id: str


def _dossier_to_response(
    d: LeadDossierModel, session_constraints: dict[str, Any] | None = None
) -> dict[str, Any]:
    constraints: dict[str, Any] = session_constraints or {}
    if not constraints:
        try:
            sess = d.__dict__.get("session") or getattr(d, "session", None)
            if sess and hasattr(sess, "constraints_json") and sess.constraints_json:
                constraints = sess.constraints_json
        except Exception:
            constraints = {}

    needs_summary = (
        constraints.get("needs_summary")
        or f"Nhu cầu tìm hiểu căn hộ {constraints.get('preferred_unit_code', 'tại dự án Riverside')}".strip()
    )

    now_iso = datetime.now(UTC).isoformat()
    created_iso = d.created_at.isoformat() if d.created_at else now_iso
    sla_iso = d.sla_expires_at.isoformat() if d.sla_expires_at else now_iso

    return {
        "dossier_id": d.dossier_id,
        "session_id": d.session_id,
        "source_session_id": d.session_id,
        "status": d.status,
        "temperature": d.lead_temperature,
        "lead_temperature": d.lead_temperature,
        "customer_name": d.customer_name,
        "customer_phone_masked": d.customer_phone_masked,
        "customer": {
            "full_name": d.customer_name,
            "phone": d.customer_phone_masked or "0912345678",
        },
        "assigned_sales_id": d.assigned_sales_id,
        "created_by": d.created_by,
        "assigned_sale": {
            "user_id": d.assigned_sales_id or "USR-SALE-001",
            "full_name": d.assigned_sales_id or "Chuyên viên Sale",
            "role": "SALE",
        } if d.assigned_sales_id else None,
        "sla_expires_at": sla_iso,
        "sla_due_at": sla_iso,
        "sla_expired": bool(
            d.sla_expires_at
            and d.sla_expires_at.replace(tzinfo=UTC) < datetime.now(UTC)
            and d.status == LeadDossierStatus.NEW.value
        ),
        "consent": {
            "granted_at": created_iso,
            "consent_text_version": "v1.0",
        },
        "needs_summary": needs_summary,
        "constraints": {
            "customer_segment": constraints.get("customer_segment") or "NEW_CUSTOMER",
            "preferred_unit_code": constraints.get("preferred_unit_code") or "R-02.02",
            "bedrooms": constraints.get("bedrooms") or 2,
            "own_funds_vnd": constraints.get("own_funds_vnd") or 1_500_000_000,
            "monthly_capacity_vnd": constraints.get("monthly_capacity_vnd") or 25_000_000,
            "objective": constraints.get("objective") or "MIN_INITIAL_OUTFLOW",
            "total_contract_price_vnd": constraints.get("total_contract_price_vnd") or 0,
        },
        "reference_plan": None,
        "converted_quote_id": d.quote_id,
        "quote_id": d.quote_id,
        "created_at": created_iso,
    }


@router.post("", status_code=201)
@router.post("/", status_code=201)
@router.post("/dossiers", status_code=201)
async def create_dossier(
    payload: LeadDossierCreateRequest,
    principal: Principal = Depends(get_current_principal),
) -> dict[str, Any]:
    """[1/2] POST /leads hoặc /leads/dossiers — tạo LeadDossier thủ công bởi Sales (SLA 15 phút).

    Hồ sơ được ghi nhận `created_by` = nhân viên đang đăng nhập: cơ sở cho quy tắc "Sale chỉ xoá khách
    hàng do mình tạo ra" (xem `PreSalesDossierService.delete_dossier`).
    """
    try:
        async for db in get_db_session():
            service = PreSalesDossierService()
            sess = None
            if payload.session_id:
                try:
                    sess = await service.get_session(db, payload.session_id)
                except Exception:
                    sess = None
            if sess is None:
                sess = await service.create_session(
                    db,
                    initial_message=payload.needs_summary or f"Tạo hồ sơ cho {payload.customer_name}",
                )

            constraints_dict = {
                "customer_segment": payload.customer_segment,
                "project_id": payload.project_id,
                "preferred_unit_code": payload.preferred_unit_code,
                "bedrooms": payload.bedrooms,
                "own_funds_vnd": payload.own_funds_vnd,
                "monthly_capacity_vnd": payload.monthly_capacity_vnd,
                "total_contract_price_vnd": payload.total_contract_price_vnd,
                "objective": payload.objective,
                "needs_summary": payload.needs_summary,
            }

            dossier = await service.create_dossier(
                db,
                session_id=sess.session_id,
                customer_name=payload.customer_name,
                customer_phone=payload.customer_phone,
                constraints=constraints_dict,
                plan_id=payload.plan_id,
                lead_temperature=payload.lead_temperature,
                created_by=principal.user_id,
            )
            await db.commit()
            return _dossier_to_response(dossier, session_constraints=constraints_dict)
    except Exception as exc:
        _raise_http(exc)


@router.get("", response_model=list[dict[str, Any]])
@router.get("/", response_model=list[dict[str, Any]])
@router.get("/dossiers", response_model=list[dict[str, Any]])
async def list_dossiers(status: str | None = None, limit: int = 50) -> list[dict[str, Any]]:
    """[2/2] GET /api/v1/leads hoặc /api/v1/leads/dossiers — danh sách hồ sơ cho Sales Dashboard."""
    try:
        status_enum = LeadDossierStatus(status) if status else None
        async for db in get_db_session():
            service = PreSalesDossierService()
            dossiers = await service.list_dossiers(db, status=status_enum, limit=limit)
            return [_dossier_to_response(d) for d in dossiers]
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid status filter: {status}")
    except Exception as exc:
        _raise_http(exc)


@router.post("/{dossier_id}/convert-to-quote")
async def convert_dossier_to_quote(dossier_id: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    """POST /api/v1/leads/{dossier_id}/convert-to-quote — Chuyển hồ sơ lead thành báo giá chính thức."""
    try:
        quote_id = f"Q-{datetime.now(UTC).strftime('%Y%m%d%H%M%S')}"
        async for db in get_db_session():
            service = PreSalesDossierService()
            dossier = await service.mark_converted(db, dossier_id=dossier_id, quote_id=quote_id)
            await db.commit()
            return {
                "dossier_id": dossier.dossier_id,
                "quote_id": quote_id,
                "status": "APPROVED_FOR_QUOTE",
                "message": f"Hồ sơ {dossier_id} đã được chuyển đổi thành báo giá {quote_id}",
            }
    except Exception as exc:
        _raise_http(exc)


@router.get("/{dossier_id}", response_model=dict[str, Any])
async def get_dossier(dossier_id: str) -> dict[str, Any]:
    """GET /api/v1/leads/{dossier_id} — Chi tiết hồ sơ khách hàng."""
    try:
        async for db in get_db_session():
            service = PreSalesDossierService()
            dossier = await service.get_dossier(db, dossier_id=dossier_id)
            return _dossier_to_response(dossier)
    except Exception as exc:
        _raise_http(exc)


@router.put("/{dossier_id}", response_model=dict[str, Any])
@router.patch("/{dossier_id}", response_model=dict[str, Any])
async def update_dossier(dossier_id: str, payload: LeadDossierUpdateRequest) -> dict[str, Any]:
    """PUT/PATCH /api/v1/leads/{dossier_id} — Cập nhật hồ sơ khách hàng bởi Sale."""
    try:
        async for db in get_db_session():
            service = PreSalesDossierService()
            constraints_dict: dict[str, Any] = {}
            if payload.customer_segment is not None:
                constraints_dict["customer_segment"] = payload.customer_segment
            if payload.project_id is not None:
                constraints_dict["project_id"] = payload.project_id
            if payload.preferred_unit_code is not None:
                constraints_dict["preferred_unit_code"] = payload.preferred_unit_code
            if payload.bedrooms is not None:
                constraints_dict["bedrooms"] = payload.bedrooms
            if payload.own_funds_vnd is not None:
                constraints_dict["own_funds_vnd"] = payload.own_funds_vnd
            if payload.monthly_capacity_vnd is not None:
                constraints_dict["monthly_capacity_vnd"] = payload.monthly_capacity_vnd
            if payload.total_contract_price_vnd is not None:
                constraints_dict["total_contract_price_vnd"] = payload.total_contract_price_vnd
            if payload.objective is not None:
                constraints_dict["objective"] = payload.objective
            if payload.needs_summary is not None:
                constraints_dict["needs_summary"] = payload.needs_summary

            dossier = await service.update_dossier(
                db,
                dossier_id=dossier_id,
                customer_name=payload.customer_name,
                customer_phone=payload.customer_phone,
                lead_temperature=payload.lead_temperature,
                status=payload.status,
                assigned_sales_id=payload.assigned_sales_id,
                constraints=constraints_dict if constraints_dict else None,
            )
            await db.commit()
            return _dossier_to_response(dossier)
    except Exception as exc:
        _raise_http(exc)


@router.delete("/{dossier_id}")
async def delete_dossier(
    dossier_id: str,
    authorization: str | None = Header(None, alias="Authorization"),
    principal: Principal = Depends(get_current_principal),
) -> dict[str, Any]:
    """DELETE /api/v1/leads/{dossier_id} — Xoá hồ sơ khách hàng **do chính mình tạo**.

    Quyền: người tạo hồ sơ (`created_by`) hoặc ADMIN. Xoá hồ sơ của Sale khác → 403. Không có phiên
    đăng nhập → 401 (không dùng principal mặc định cho thao tác phá huỷ dữ liệu).
    """
    if not authorization:
        raise HTTPException(
            status_code=401,
            detail="Cần đăng nhập để xoá hồ sơ khách hàng.",
        )
    try:
        async for db in get_db_session():
            service = PreSalesDossierService()
            await service.delete_dossier(
                db,
                dossier_id=dossier_id,
                actor_id=principal.user_id,
                allow_any=principal.has_role("ADMIN"),
            )
            await db.commit()
            return {"deleted": True, "dossier_id": dossier_id}
    except Exception as exc:
        _raise_http(exc)


def _raise_http(exc: Exception) -> None:
    if isinstance(exc, DomainError):
        raise HTTPException(
            status_code=exc.http_status if exc.http_status >= 400 else 400,
            detail=exc.to_envelope().model_dump(),
        )
    raise HTTPException(status_code=500, detail=str(exc)) from exc
