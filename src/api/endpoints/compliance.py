"""Compliance API Router (C-11 / F8).

Provides:
1. POST /api/v1/compliance/check-message (live speech standard & evidence verification)
2. POST /api/v1/messages/send (single issuance gate with strict compliance check)
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from src.services.compliance.gate import (
    ComplianceCheckRequest,
    ComplianceCheckResponse,
    ComplianceGate,
)

router = APIRouter(prefix="/compliance", tags=["Compliance Gate (F8)"])
messages_router = APIRouter(prefix="/messages", tags=["Messages Issuance (F8)"])

# Shared singleton gate
_gate = ComplianceGate()


class SendMessageRequest(BaseModel):
    """Request to send a sales message to customer."""

    message: str = Field(..., description="Message content")
    recipient: str = Field(..., description="Customer phone/email/identifier")
    quote_id: str | None = Field(None, description="Associated quote ID")
    quote_version: int | None = Field(None, description="Associated quote version")
    policy_version_refs: list[str] = Field(default_factory=list, description="Referenced policy versions")
    claimed_evidence_ids: list[str] = Field(default_factory=list, description="Linked evidence IDs")
    channel: str = Field("ZALO", description="ZALO, SMS, EMAIL, IN_APP")


class SendMessageResponse(BaseModel):
    """Issuance response when message passes compliance gate."""

    status: str = Field("SENT", description="Delivery status")
    message_id: str = Field(..., description="Unique message ID")
    message_hash: str = Field(..., description="SHA-256 hash of sent message")
    compliance_check_id: str = Field(..., description="Associated check ID")
    overall_status: str = Field(..., description="SUPPORTED or CONDITIONAL")
    sent_at: str = Field(..., description="ISO timestamp")


@router.post("/check-message", response_model=ComplianceCheckResponse)
async def check_message(request: ComplianceCheckRequest) -> ComplianceCheckResponse:
    """Kiểm tra tuân thủ phát ngôn & mỏ neo chứng cứ (F8).

    Đánh giá qua 3 checkpoint (ON_DRAFT, DEBOUNCE, FINAL_SEND)
    và 4 cấp độ (SUPPORTED, CONDITIONAL, UNSUPPORTED, PROHIBITED).
    """
    try:
        return _gate.check(request)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Lỗi khi kiểm tra tuân thủ phát ngôn: {str(e)}",
        )


@messages_router.post("/send", response_model=SendMessageResponse)
async def send_message(request: SendMessageRequest) -> SendMessageResponse:
    """Cổng phát hành tin nhắn duy nhất (Single Issuance Gate).

    Thực hiện kiểm tra nghiêm ngặt với mode='FINAL_SEND'.
    Nếu vi phạm PROHIBITED hoặc UNSUPPORTED thiếu chứng cứ -> Chặn phát hành (HTTP 400).
    """
    check_req = ComplianceCheckRequest(
        message=request.message,
        mode="FINAL_SEND",
        quote_id=request.quote_id,
        quote_version=request.quote_version,
        policy_version_refs=request.policy_version_refs,
        claimed_evidence_ids=request.claimed_evidence_ids,
    )

    check_res = _gate.check(check_req)

    # Hard enforcement: Block if PROHIBITED or UNSUPPORTED
    if check_res.overall_status in ("PROHIBITED", "UNSUPPORTED"):
        violations = [
            f"[{c.tier}] {c.claim_text}: {c.reason}"
            for c in check_res.claims
            if c.tier in ("PROHIBITED", "UNSUPPORTED")
        ]
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "COMPLIANCE_GATE_BLOCKED",
                "overall_status": check_res.overall_status,
                "required_action": check_res.required_action,
                "violations": violations,
                "message_hash": check_res.message_hash,
            },
        )

    # Approved for send
    msg_id = f"MSG-{uuid.uuid4().hex[:10].upper()}"
    now_iso = datetime.now(UTC).isoformat()

    return SendMessageResponse(
        status="SENT",
        message_id=msg_id,
        message_hash=check_res.message_hash,
        compliance_check_id=check_res.check_id,
        overall_status=check_res.overall_status,
        sent_at=now_iso,
    )
