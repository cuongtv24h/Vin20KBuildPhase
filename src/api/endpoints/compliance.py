"""
REST API endpoints for Real-time Message Compliance Gate & F8 Backend Gatekeeper.
Owner: TechLead (cuongtv_02560)
"""

from __future__ import annotations

import hashlib
import uuid
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import Principal, get_current_principal
from src.contracts.enums import ComplianceStatus, ComplianceTier
from src.contracts.errors import ErrorCode
from src.db.models import ComplianceCheckModel
from src.db.session import get_db_session
from src.services.compliance.gate import analyze_message_claims, determine_tier

router = APIRouter(prefix="/api/v1", tags=["compliance"])


class ComplianceCheckRequest(BaseModel):
    message_text: str = Field(..., min_length=1)
    quote_id: str | None = None


class SendMessageRequest(BaseModel):
    message_text: str = Field(..., min_length=1)
    recipient_phone: str = Field(..., min_length=8)
    quote_id: str | None = None
    message_hash: str | None = None


def _evaluate_message_compliance(
    text: str,
) -> tuple[ComplianceStatus, ComplianceTier, bool, list[dict[str, Any]]]:
    """
    Evaluates message content against Real-time Compliance Policies (POL-08).

    HỢP NHẤT 2 ENGINE (audit TASK-REVIEW-02): hợp kết quả engine blacklist từ
    khóa của Phase 4 với engine phân tích claims của Phase 5
    (`src/services/compliance/gate.py`) theo nguyên tắc BẮT KỲ tầng nào chặn
    thì chặn — xoá blind-spot chéo giữa 2 tầng (vd 'cam kết sinh lời 20%'
    từng lọt qua tầng HTTP). Đối chiếu Invariant #7 / INV-RT-11.
    """
    lower = text.lower()

    # ---- Engine A (Phase 4): blacklist từ khóa cấm tuyệt đối ----
    prohibited_keywords = [
        "cam kết lợi nhuận",
        "chắc chắn có lãi",
        "bao duyệt vay",
        "duyệt vay 100%",
        "bao đỗ hồ sơ",
        "lãi suất vĩnh viễn",
    ]
    for kw in prohibited_keywords:
        if kw in lower:
            return (
                ComplianceStatus.PROHIBITED,
                ComplianceTier.TIER_4_BLACK,
                False,
                [{"claim_type": "PROHIBITED_PROMISE", "keyword": kw, "status": "BLOCKED"}],
            )

    # ---- Engine B (Phase 5): phân tích claims tài chính + dẫn chứng ----
    claims_b = analyze_message_claims(text)
    tier_b = determine_tier(claims_b)
    if tier_b == ComplianceTier.TIER_4_BLACK:
        return (
            ComplianceStatus.PROHIBITED,
            ComplianceTier.TIER_4_BLACK,
            False,
            claims_b or [{"claim_type": "PROHIBITED_PROMISE", "status": "BLOCKED"}],
        )
    if tier_b == ComplianceTier.TIER_3_RED:
        return (
            ComplianceStatus.UNSUPPORTED,
            ComplianceTier.TIER_3_RED,
            False,
            claims_b,
        )

    # ---- Rule 2 (Phase 4): chiết khấu mạnh không trích dẫn chính sách ----
    if "chiết khấu 15%" in lower or "giảm ngay 20%" in lower:
        return (
            ComplianceStatus.UNSUPPORTED,
            ComplianceTier.TIER_3_RED,
            False,
            [{"claim_type": "UNVERIFIED_DISCOUNT", "status": "NEEDS_APPROVAL"}],
        )

    # ---- Rule 3 (Phase 4): phát ngôn có điều kiện ----
    if "nếu" in lower or "khi" in lower or "điều kiện" in lower:
        return (
            ComplianceStatus.CONDITIONAL,
            ComplianceTier.TIER_2_YELLOW,
            True,
            claims_b or [{"claim_type": "CONDITIONAL_STATEMENT", "status": "APPROVED"}],
        )

    # SUPPORTED: can_send theo tier engine B (YELLOW cho gửi, RED thì đã chặn ở trên)
    return (
        ComplianceStatus.SUPPORTED,
        ComplianceTier.TIER_1_GREEN if tier_b == ComplianceTier.TIER_1_GREEN else tier_b,
        True,
        claims_b or [{"claim_type": "STANDARD_CONSULTATION", "status": "APPROVED"}],
    )


@router.post("/compliance/check-message")
async def check_message_compliance(
    req: ComplianceCheckRequest,
    db: AsyncSession = Depends(get_db_session),
    principal: Principal = Depends(get_current_principal),
) -> dict[str, Any]:
    """Evaluates draft message compliance before sending (F8 checkpoint)."""
    msg_hash = hashlib.sha256(req.message_text.strip().encode("utf-8")).hexdigest()
    status_val, tier, can_send, claims = _evaluate_message_compliance(req.message_text)

    check_id = f"CHK-{uuid.uuid4().hex[:12]}"
    record = ComplianceCheckModel(
        check_id=check_id,
        message_hash=msg_hash,
        overall_status=status_val.value,
        compliance_tier=tier.value,
        claims_json=claims,
        quote_id=req.quote_id,
        can_send=can_send,
    )
    db.add(record)
    await db.commit()

    return {
        "check_id": check_id,
        "message_hash": msg_hash,
        "overall_status": status_val.value,
        "compliance_tier": tier.value,
        "can_send": can_send,
        "claims": claims,
    }


@router.post("/messages/send")
async def send_message(
    req: SendMessageRequest,
    db: AsyncSession = Depends(get_db_session),
    principal: Principal = Depends(get_current_principal),
) -> dict[str, Any]:
    """
    Invariant #7: Backend Gatekeeper for Outbound Customer Messages.
    Guarantees no unapproved or prohibited claims reach customers.
    """
    msg_hash = hashlib.sha256(req.message_text.strip().encode("utf-8")).hexdigest()
    status_val, tier, can_send, claims = _evaluate_message_compliance(req.message_text)

    if not can_send or status_val in (ComplianceStatus.PROHIBITED, ComplianceStatus.UNSUPPORTED):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": ErrorCode.COMPLIANCE_SEND_BLOCKED.value,
                "message": (
                    f"Outbound message blocked by Compliance Gate (POL-08): "
                    f"status={status_val.value}, tier={tier.value}, prohibited or unsupported claims detected."
                ),
                "claims": claims,
            },
        )

    # Allowed: simulate dispatch
    message_id = f"MSG-{uuid.uuid4().hex[:12]}"
    return {
        "status": "SENT",
        "message_id": message_id,
        "recipient": req.recipient_phone,
        "message_hash": msg_hash,
        "compliance_tier": tier.value,
        "sent_at": datetime.now(UTC).isoformat(),
    }
