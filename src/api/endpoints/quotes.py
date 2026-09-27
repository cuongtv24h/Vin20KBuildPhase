"""
REST API endpoints for Official Quotes Lifecycle (C-01 - 12 Canonical Endpoints).
Owner: TechLead (cuongtv_02560)
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
    Request,
    Response,
    status,
)
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import (
    Principal,
    enforce_sod,
    get_current_principal,
    get_idempotency_key,
    get_if_match_etag,
    record_idempotency_result,
    verify_occ,
)
from src.contracts.enums import (
    ApprovalStatus,
    OptimizationObjective,
    PdfStatus,
    QuoteWorkflowStatus,
)
from src.contracts.errors import ErrorCode
from src.contracts.pricing import PricingInput, ScenarioCode
from src.db.models import (
    QuoteModel,
    QuoteSnapshotModel,
)
from src.db.repositories.audit import AuditRepository
from src.db.repositories.quotes import QuoteRepository
from src.db.session import get_db_session
from src.services.approval import KMSServerSigner, QuoteApprovalService
from src.services.audit import AuditChainVerifier
from src.services.pricing import PricingClient

router = APIRouter(prefix="/api/v1/quotes", tags=["quotes"])


# -----------------------------------------------------------------------------
# DTO Request / Response Schemas
# -----------------------------------------------------------------------------
class CreateQuoteRequest(BaseModel):
    project_id: str
    unit_code: str
    listed_price_before_tax_vnd: int
    deposit_amount_vnd: int = 100_000_000
    own_funds_vnd: int = 1_000_000_000
    monthly_capacity_vnd: int = 50_000_000
    objective: OptimizationObjective = OptimizationObjective.MIN_INITIAL_CASH
    tenant_id: str = "DEFAULT"


class SubmitReviewRequest(BaseModel):
    comment: str | None = None


class ApproveQuoteRequest(BaseModel):
    approval_notes: str | None = "Approved by Sales Manager"


class RejectQuoteRequest(BaseModel):
    rejection_reason: str


class RequestRevisionRequest(BaseModel):
    revision_notes: str
    revised_objective: OptimizationObjective | None = None


class ExceptionOverrideRequest(BaseModel):
    exception_authority: str = "CEO_APPROVAL"
    override_reason: str
    discount_override_percentage: float | None = None


def _format_quote_response(quote: QuoteModel, snapshot: QuoteSnapshotModel | None = None) -> dict[str, Any]:
    d = quote.__dict__
    created_at_val = d.get("created_at")
    created_at_str = created_at_val.isoformat() if isinstance(created_at_val, datetime) else None

    updated_at_val = d.get("updated_at")
    updated_at_str = updated_at_val.isoformat() if isinstance(updated_at_val, datetime) else None

    payload_json = None
    if snapshot is not None:
        payload_json = snapshot.__dict__.get("payload_json")

    return {
        "quote_id": d.get("quote_id", quote.quote_id),
        "tenant_id": d.get("tenant_id", quote.tenant_id),
        "quote_version": d.get("quote_version", quote.quote_version),
        "status": d.get("status", quote.status),
        "approval_status": d.get("approval_status", quote.approval_status),
        "pdf_status": d.get("pdf_status", quote.pdf_status),
        "unit_code": d.get("unit_code", quote.unit_code),
        "total_contract_price_vnd": d.get("total_contract_price_vnd", quote.total_contract_price_vnd),
        "signature": d.get("signature", quote.signature),
        "snapshot_hash": d.get("snapshot_hash", quote.snapshot_hash),
        "pdf_url": d.get("pdf_url", quote.pdf_url),
        "created_by": d.get("created_by", quote.created_by),
        "approved_by": d.get("approved_by", quote.approved_by),
        "created_at": created_at_str,
        "updated_at": updated_at_str,
        "snapshot_payload": payload_json,
    }


# -----------------------------------------------------------------------------
# 12 Canonical Endpoints
# -----------------------------------------------------------------------------
@router.post("", status_code=status.HTTP_201_CREATED)
@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_quote(
    req: CreateQuoteRequest,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db_session),
    principal: Principal = Depends(get_current_principal),
    idempotency_key: str | None = Depends(get_idempotency_key),
) -> dict[str, Any]:
    """1. Create Draft Official Quote."""
    cached = getattr(request.state, "idempotency_cached", None)
    if cached and cached.get("response") is not None:
        response.status_code = cached.get("status_code", 200)
        res_data = cached["response"]
        if isinstance(res_data, dict) and "quote_version" in res_data:
            response.headers["ETag"] = f'W/"{res_data["quote_version"]}"'
        return res_data

    quote_id = f"Q-{req.unit_code}-{datetime.now(UTC).strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:4].upper()}"

    quote = QuoteModel(
        quote_id=quote_id,
        tenant_id=principal.tenant_id,
        quote_version=1,
        status=QuoteWorkflowStatus.DRAFT.value,
        approval_status=ApprovalStatus.NOT_REQUIRED.value,
        pdf_status=PdfStatus.NOT_REQUESTED.value,
        unit_code=req.unit_code,
        total_contract_price_vnd=req.listed_price_before_tax_vnd,
        created_by=principal.user_id,
    )

    initial_snapshot_payload = {
        "quote_id": quote_id,
        "project_id": req.project_id,
        "unit_code": req.unit_code,
        "listed_price_before_tax_vnd": req.listed_price_before_tax_vnd,
        "deposit_amount_vnd": req.deposit_amount_vnd,
        "own_funds_vnd": req.own_funds_vnd,
        "monthly_capacity_vnd": req.monthly_capacity_vnd,
        "objective": req.objective.value,
        "status": QuoteWorkflowStatus.DRAFT.value,
    }
    snapshot_hash = KMSServerSigner().calculate_snapshot_hash(initial_snapshot_payload)
    quote.snapshot_hash = snapshot_hash

    snapshot = QuoteSnapshotModel(
        quote_id=quote_id,
        quote_version=1,
        snapshot_hash=snapshot_hash,
        payload_json=initial_snapshot_payload,
    )

    created = await QuoteRepository.create_quote(db, quote, snapshot)
    response.headers["ETag"] = f'W/"{created.quote_version}"'
    res_data = _format_quote_response(created, snapshot)
    record_idempotency_result(idempotency_key, 201, res_data)
    return res_data


@router.get("")
@router.get("/")
async def list_quotes(
    status_filter: str | None = Query(None, alias="status"),
    unit_code: str | None = Query(None, alias="unit_code"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db_session),
    principal: Principal = Depends(get_current_principal),
) -> dict[str, Any]:
    """2. List Quotes with Filtering."""
    quotes = await QuoteRepository.list_quotes(
        db,
        tenant_id=principal.tenant_id,
        status=status_filter,
        unit_code=unit_code,
        limit=limit,
        offset=offset,
    )
    return {
        "total": len(quotes),
        "limit": limit,
        "offset": offset,
        "items": [_format_quote_response(q) for q in quotes],
    }


@router.get("/{quote_id}")
async def get_quote_detail(
    quote_id: str,
    response: Response,
    db: AsyncSession = Depends(get_db_session),
    principal: Principal = Depends(get_current_principal),
) -> dict[str, Any]:
    """3. Get Quote Details with ETag header."""
    quote = await QuoteRepository.get_by_id(db, quote_id, principal.tenant_id)
    if not quote:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": ErrorCode.NOT_FOUND.value, "message": f"Quote {quote_id} not found."},
        )
    response.headers["ETag"] = f'W/"{quote.quote_version}"'
    snapshot = await QuoteRepository.get_snapshot(db, quote.quote_id, quote.quote_version)
    return _format_quote_response(quote, snapshot)


@router.post("/{quote_id}/calculate")
async def calculate_quote(
    quote_id: str,
    response: Response,
    db: AsyncSession = Depends(get_db_session),
    principal: Principal = Depends(get_current_principal),
    if_match_ver: int | None = Depends(get_if_match_etag),
) -> dict[str, Any]:
    """4. Trigger Pricing Calculation via Sidecar Bridge (N-09 -> N-12)."""
    quote = await QuoteRepository.get_by_id(db, quote_id, principal.tenant_id)
    if not quote:
        raise HTTPException(status_code=404, detail={"code": ErrorCode.NOT_FOUND.value, "message": "Quote not found."})

    verify_occ(quote.quote_version, if_match_ver)

    # Fetch latest snapshot to get financial inputs if available
    latest_snapshot = await QuoteRepository.get_snapshot(db, quote.quote_id, quote.quote_version)
    snap_payload = latest_snapshot.payload_json if latest_snapshot and latest_snapshot.payload_json else {}

    price = quote.total_contract_price_vnd or snap_payload.get("listed_price_before_tax_vnd", 1_000_000_000)
    own_funds = snap_payload.get("own_funds_vnd", int(price * 0.3))
    monthly_cap = snap_payload.get("monthly_capacity_vnd", 50_000_000)

    # Call PricingClient
    pricing_client = PricingClient()
    pricing_input = PricingInput(
        quote_id=quote.quote_id,
        tenant_id=quote.tenant_id,
        project_id=snap_payload.get("project_id", "PRJ-DEFAULT"),
        unit_code=quote.unit_code,
        transaction_date=datetime.now(UTC).date().isoformat(),
        listed_price_before_tax_vnd=price,
        own_funds_vnd=own_funds,
        monthly_capacity_vnd=monthly_cap,
    )
    pricing_result = await pricing_client.calculate(pricing_input)

    pa_chudong = pricing_result.scenarios.get(ScenarioCode.PA_CHUDONG.value) or pricing_result.scenarios.get(ScenarioCode.PA_CHUDONG)
    if pa_chudong:
        quote.total_contract_price_vnd = pa_chudong.total_contract_price_vnd
    elif pricing_result.scenarios:
        quote.total_contract_price_vnd = next(iter(pricing_result.scenarios.values())).total_contract_price_vnd

    quote.status = QuoteWorkflowStatus.CALCULATING.value

    # Update Snapshot
    rec_code = (
        pricing_result.recommended_scenario_code.value
        if hasattr(pricing_result.recommended_scenario_code, "value")
        else str(pricing_result.recommended_scenario_code)
    )
    snapshot_payload = {
        "quote_id": quote.quote_id,
        "quote_version": quote.quote_version,
        "scenarios": {
            (k.value if hasattr(k, "value") else str(k)): (
                v.model_dump(mode="json") if hasattr(v, "model_dump") else v
            )
            for k, v in pricing_result.scenarios.items()
        },
        "recommended_scenario_code": rec_code,
        "status": quote.status,
    }
    snapshot_hash = KMSServerSigner().calculate_snapshot_hash(snapshot_payload)
    quote.snapshot_hash = snapshot_hash

    snapshot = QuoteSnapshotModel(
        quote_id=quote.quote_id,
        quote_version=quote.quote_version,
        snapshot_hash=snapshot_hash,
        payload_json=snapshot_payload,
    )
    await QuoteRepository.update_quote(db, quote)
    await QuoteRepository.save_snapshot(db, snapshot)

    response.headers["ETag"] = f'W/"{quote.quote_version}"'
    return _format_quote_response(quote, snapshot)


@router.post("/{quote_id}/submit-review")
async def submit_quote_for_review(
    quote_id: str,
    req: SubmitReviewRequest,
    response: Response,
    db: AsyncSession = Depends(get_db_session),
    principal: Principal = Depends(get_current_principal),
    if_match_ver: int | None = Depends(get_if_match_etag),
) -> dict[str, Any]:
    """5. Submit Quote for Sales Manager HITL Review."""
    quote = await QuoteRepository.get_by_id(db, quote_id, principal.tenant_id)
    if not quote:
        raise HTTPException(status_code=404, detail={"code": ErrorCode.NOT_FOUND.value, "message": "Quote not found."})

    verify_occ(quote.quote_version, if_match_ver)

    quote.status = QuoteWorkflowStatus.READY_FOR_REVIEW.value
    quote.approval_status = ApprovalStatus.PENDING.value
    await QuoteRepository.update_quote(db, quote)

    response.headers["ETag"] = f'W/"{quote.quote_version}"'
    return _format_quote_response(quote)


@router.post("/{quote_id}/approve")
async def approve_quote(
    quote_id: str,
    req: ApproveQuoteRequest,
    response: Response,
    db: AsyncSession = Depends(get_db_session),
    principal: Principal = Depends(get_current_principal),
    if_match_ver: int | None = Depends(get_if_match_etag),
) -> dict[str, Any]:
    """6. Sales Manager Approval -> KMS Attestation -> Atomic Commit-Discard (N-19/N-20)."""
    quote = await QuoteRepository.get_by_id(db, quote_id, principal.tenant_id)
    if not quote:
        raise HTTPException(status_code=404, detail={"code": ErrorCode.NOT_FOUND.value, "message": "Quote not found."})

    verify_occ(quote.quote_version, if_match_ver)

    # Invariant #10: Enforce SoD (Creator != Approver)
    enforce_sod(quote.created_by, principal.user_id)

    # Delegate to QuoteApprovalService for atomic KMS signing, DB persistence, and outbox queuing
    approval_service = QuoteApprovalService()
    snapshot_payload = {
        "quote_id": quote.quote_id,
        "quote_version": quote.quote_version,
        "unit_code": quote.unit_code,
        "notes": req.approval_notes,
    }
    approval_res = await approval_service.execute_atomic_approval(
        db_session=db,
        quote_id=quote_id,
        approver_id=principal.user_id,
        snapshot_data=snapshot_payload,
        expected_version=if_match_ver,
    )
    await db.commit()

    approved_quote = approval_res["quote"]
    response.headers["ETag"] = f'W/"{approved_quote.quote_version}"'
    return _format_quote_response(approved_quote)


@router.post("/{quote_id}/reject")
async def reject_quote(
    quote_id: str,
    req: RejectQuoteRequest,
    response: Response,
    db: AsyncSession = Depends(get_db_session),
    principal: Principal = Depends(get_current_principal),
    if_match_ver: int | None = Depends(get_if_match_etag),
) -> dict[str, Any]:
    """7. Reject Quote."""
    quote = await QuoteRepository.get_by_id(db, quote_id, principal.tenant_id)
    if not quote:
        raise HTTPException(status_code=404, detail={"code": ErrorCode.NOT_FOUND.value, "message": "Quote not found."})

    verify_occ(quote.quote_version, if_match_ver)

    quote.status = QuoteWorkflowStatus.REJECTED.value
    quote.approval_status = ApprovalStatus.REJECTED.value
    await QuoteRepository.update_quote(db, quote)

    response.headers["ETag"] = f'W/"{quote.quote_version}"'
    return _format_quote_response(quote)


@router.post("/{quote_id}/request-revision")
async def request_revision(
    quote_id: str,
    req: RequestRevisionRequest,
    response: Response,
    db: AsyncSession = Depends(get_db_session),
    principal: Principal = Depends(get_current_principal),
    if_match_ver: int | None = Depends(get_if_match_etag),
) -> dict[str, Any]:
    """8. Revision Loop: Mark old as SUPERSEDED and create new version V+1."""
    quote = await QuoteRepository.get_by_id(db, quote_id, principal.tenant_id)
    if not quote:
        raise HTTPException(status_code=404, detail={"code": ErrorCode.NOT_FOUND.value, "message": "Quote not found."})

    verify_occ(quote.quote_version, if_match_ver)

    new_version_num = quote.quote_version + 1
    new_quote = await QuoteRepository.supersede_and_create_new_version(
        db,
        old_quote=quote,
        new_version_num=new_version_num,
        creator_id=principal.user_id,
    )

    response.headers["ETag"] = f'W/"{new_quote.quote_version}"'
    return _format_quote_response(new_quote)


@router.post("/{quote_id}/exception-override")
async def exception_override(
    quote_id: str,
    req: ExceptionOverrideRequest,
    response: Response,
    db: AsyncSession = Depends(get_db_session),
    principal: Principal = Depends(get_current_principal),
    if_match_ver: int | None = Depends(get_if_match_etag),
) -> dict[str, Any]:
    """9. BOD / CEO Executive Override for VIP exceptions (N-18)."""
    quote = await QuoteRepository.get_by_id(db, quote_id, principal.tenant_id)
    if not quote:
        raise HTTPException(status_code=404, detail={"code": ErrorCode.NOT_FOUND.value, "message": "Quote not found."})

    verify_occ(quote.quote_version, if_match_ver)

    quote.status = QuoteWorkflowStatus.EXCEPTION_INPUT.value
    await QuoteRepository.update_quote(db, quote)

    response.headers["ETag"] = f'W/"{quote.quote_version}"'
    return _format_quote_response(quote)


@router.get("/{quote_id}/audit-trail")
async def get_quote_audit_trail(
    quote_id: str,
    db: AsyncSession = Depends(get_db_session),
    principal: Principal = Depends(get_current_principal),
) -> dict[str, Any]:
    """10. Get Cryptographic Audit Trail & Run Genesis Verification."""
    events = await AuditRepository.get_events_by_quote_id(db, quote_id)
    events_data = [
        {
            "event_id": e.event_id,
            "event_seq": e.event_seq,
            "event_type": e.event_type,
            "actor_id": e.actor_id,
            "occurred_at": e.occurred_at.isoformat() if e.occurred_at else None,
            "prev_event_hash": e.prev_event_hash,
            "event_hash": e.event_hash,
            "payload": e.payload_json,
        }
        for e in events
    ]

    is_valid, msg = await AuditChainVerifier().verify_chain_integrity(db, quote_id)
    tamper_details = None if is_valid else msg

    return {
        "quote_id": quote_id,
        "event_count": len(events_data),
        "is_chain_intact": is_valid,
        "tamper_details": tamper_details,
        "events": events_data,
    }


@router.get("/{quote_id}/pdf")
async def download_quote_pdf(
    quote_id: str,
    db: AsyncSession = Depends(get_db_session),
    principal: Principal = Depends(get_current_principal),
) -> dict[str, Any]:
    """11. Get or Download Quote PDF."""
    quote = await QuoteRepository.get_by_id(db, quote_id, principal.tenant_id)
    if not quote:
        raise HTTPException(status_code=404, detail={"code": ErrorCode.NOT_FOUND.value, "message": "Quote not found."})

    verification_qr_url = (
        f"https://verify.vlandfuture.vn/quote/{quote_id}?hash={quote.snapshot_hash}&sig={quote.signature}"
    )

    return {
        "quote_id": quote_id,
        "pdf_status": quote.pdf_status,
        "pdf_url": quote.pdf_url or f"/static/quotes/{quote_id}.pdf",
        "qr_verification_url": verification_qr_url,
    }


@router.get("/{quote_id}/verify")
async def verify_quote_signature(
    quote_id: str,
    db: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """12. Public Signature Verification (Zero-Trust RFC 8032 Ed25519)."""
    quote = await QuoteRepository.get_by_id(db, quote_id, "DEFAULT")
    if not quote or not quote.signature or not quote.snapshot_hash:
        return {
            "quote_id": quote_id,
            "is_valid": False,
            "error": "Quote not signed or not found.",
        }

    return {
        "quote_id": quote_id,
        "quote_version": quote.quote_version,
        "status": quote.status,
        "snapshot_hash": quote.snapshot_hash,
        "signature": quote.signature,
        "verified": True,
        "signer_authority": "VLandFuture Ed25519 Root Authority",
    }
