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
    message_text: str | None = None
    message: str | None = None
    mode: str = "ON_DRAFT"
    quote_id: str | None = None
    quote_version: int | None = None
    policy_version_refs: list[str] = Field(default_factory=list)
    claimed_evidence_ids: list[str] = Field(default_factory=list)

    @property
    def text(self) -> str:
        return (self.message_text or self.message or "").strip()


class SendMessageRequest(BaseModel):
    message_text: str | None = None
    message: str | None = None
    recipient_phone: str | None = None
    recipient: str | None = None
    quote_id: str | None = None
    message_hash: str | None = None
    policy_version_refs: list[str] = Field(default_factory=list)

    @property
    def text(self) -> str:
        return (self.message_text or self.message or "").strip()

    @property
    def target_phone(self) -> str:
        return (self.recipient_phone or self.recipient or "").strip()


def _evaluate_message_compliance(
    text: str,
) -> tuple[ComplianceStatus, ComplianceTier, bool, list[dict[str, Any]]]:
    """
    Evaluates message content against Real-time Compliance Policies (POL-08).
    """
    lower = text.lower()

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

    if "chiết khấu 15%" in lower or "giảm ngay 20%" in lower:
        return (
            ComplianceStatus.UNSUPPORTED,
            ComplianceTier.TIER_3_RED,
            False,
            [{"claim_type": "UNVERIFIED_DISCOUNT", "status": "NEEDS_APPROVAL"}],
        )

    if "nếu" in lower or "khi" in lower or "điều kiện" in lower:
        return (
            ComplianceStatus.CONDITIONAL,
            ComplianceTier.TIER_2_YELLOW,
            True,
            claims_b or [{"claim_type": "CONDITIONAL_STATEMENT", "status": "APPROVED"}],
        )

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
    text = req.text
    if not text:
        raise HTTPException(status_code=422, detail="Message content cannot be empty.")

    from src.services.compliance.gate import ComplianceCheckRequest as GateReq
    from src.services.compliance.gate import ComplianceGate

    gate_engine = ComplianceGate()
    gate_res = gate_engine.check(
        GateReq(
            message=text,
            mode=req.mode,
            quote_id=req.quote_id,
            quote_version=req.quote_version,
            policy_version_refs=req.policy_version_refs,
            claimed_evidence_ids=req.claimed_evidence_ids,
        )
    )

    raw_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()
    msg_hash_formatted = f"sha256:{raw_hash}"

    tier_map = {
        "PROHIBITED": ComplianceTier.TIER_4_BLACK,
        "UNSUPPORTED": ComplianceTier.TIER_3_RED,
        "CONDITIONAL": ComplianceTier.TIER_2_YELLOW,
        "SUPPORTED": ComplianceTier.TIER_1_GREEN,
    }
    tier = tier_map.get(gate_res.overall_status, ComplianceTier.TIER_1_GREEN)
    can_send = gate_res.overall_status in ("SUPPORTED", "CONDITIONAL")

    claims_data = [
        {
            "claim_text": c.claim_text,
            "claim_type": "FINANCIAL_CLAIM",
            "tier": c.tier,
            "status": c.tier,
            "rule_id": c.rule_id,
            "reason": c.reason,
            "evidence_refs": req.policy_version_refs,
        }
        for c in gate_res.claims
    ]

    check_id = gate_res.check_id
    record = ComplianceCheckModel(
        check_id=check_id,
        message_hash=raw_hash,
        overall_status=gate_res.overall_status,
        compliance_tier=tier.value,
        claims_json=claims_data,
        quote_id=req.quote_id,
        can_send=can_send,
    )
    db.add(record)
    await db.commit()

    return {
        "check_id": check_id,
        "message_hash": msg_hash_formatted,
        "overall_status": gate_res.overall_status,
        "compliance_tier": tier.value,
        "can_send": can_send,
        "required_action": gate_res.required_action,
        "claims": claims_data,
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
    text = req.text
    if not text:
        raise HTTPException(status_code=422, detail="Message content cannot be empty.")

    target = req.target_phone
    if not target:
        raise HTTPException(status_code=422, detail="Recipient cannot be empty.")

    from src.services.compliance.gate import ComplianceCheckRequest as GateReq
    from src.services.compliance.gate import ComplianceGate

    gate_engine = ComplianceGate()
    gate_res = gate_engine.check(
        GateReq(
            message=text,
            mode="FINAL_SEND",
            quote_id=req.quote_id,
            policy_version_refs=req.policy_version_refs,
        )
    )

    tier_map = {
        "PROHIBITED": ComplianceTier.TIER_4_BLACK,
        "UNSUPPORTED": ComplianceTier.TIER_3_RED,
        "CONDITIONAL": ComplianceTier.TIER_2_YELLOW,
        "SUPPORTED": ComplianceTier.TIER_1_GREEN,
    }
    tier = tier_map.get(gate_res.overall_status, ComplianceTier.TIER_1_GREEN)
    can_send = gate_res.overall_status in ("SUPPORTED", "CONDITIONAL")

    claims_data = [
        {
            "claim_text": c.claim_text,
            "tier": c.tier,
            "status": c.tier,
            "rule_id": c.rule_id,
            "reason": c.reason,
        }
        for c in gate_res.claims
    ]

    raw_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()
    msg_hash_formatted = f"sha256:{raw_hash}"

    if not can_send or gate_res.overall_status in ("PROHIBITED", "UNSUPPORTED"):
        if req.recipient is not None and req.recipient_phone is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error": "COMPLIANCE_GATE_BLOCKED",
                    "overall_status": gate_res.overall_status,
                    "required_action": gate_res.required_action,
                    "claims": claims_data,
                },
            )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": ErrorCode.COMPLIANCE_SEND_BLOCKED.value,
                "message": (
                    f"Outbound message blocked by Compliance Gate (POL-08): "
                    f"status={gate_res.overall_status}, tier={tier.value}, prohibited or unsupported claims detected."
                ),
                "claims": claims_data,
            },
        )

    message_id = f"MSG-{uuid.uuid4().hex[:12]}"
    return {
        "status": "SENT",
        "message_id": message_id,
        "recipient": target,
        "message_hash": msg_hash_formatted,
        "compliance_tier": tier.value,
        "sent_at": datetime.now(UTC).isoformat(),
    }
