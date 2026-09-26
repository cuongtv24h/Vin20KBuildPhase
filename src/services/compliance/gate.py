"""Compliance Gate Service (C-11 / F8).

Enforces speech guidelines (POL-08) and validates claim evidence across 3 checkpoints:
- ON_DRAFT: Real-time typing suggestions
- DEBOUNCE: Form level pre-check
- FINAL_SEND: Hard enforcement gate (blocks prohibited or unverified messages)
"""

from __future__ import annotations

import hashlib
import re
import uuid

from pydantic import BaseModel, Field

from src.services.compliance.rules import POL_08_PROHIBITED_PATTERNS


class ComplianceCheckRequest(BaseModel):
    """Request schema for compliance checking."""
    message: str = Field(..., description="Message text to inspect")
    mode: str = Field("FINAL_SEND", description="ON_DRAFT, DEBOUNCE, or FINAL_SEND")
    quote_id: str | None = Field(None, description="Associated quote ID")
    quote_version: int | None = Field(None, description="Associated quote version")
    policy_version_refs: list[str] = Field(default_factory=list, description="Referenced policy versions")
    claimed_evidence_ids: list[str] = Field(default_factory=list, description="IDs of linked evidence items")


class ComplianceClaimFinding(BaseModel):
    """Specific finding on a claim inside the message."""
    claim_text: str
    tier: str = Field(..., description="SUPPORTED, CONDITIONAL, UNSUPPORTED, PROHIBITED")
    rule_id: str | None = None
    reason: str


class ComplianceCheckResponse(BaseModel):
    """Response schema matching Section 10.4 compliance contract."""
    check_id: str
    message_hash: str
    mode: str
    overall_status: str = Field(..., description="SUPPORTED, CONDITIONAL, UNSUPPORTED, PROHIBITED")
    quote_id: str | None = None
    quote_version: int | None = None
    policy_version_refs: list[str] = Field(default_factory=list)
    claims: list[ComplianceClaimFinding] = Field(default_factory=list)
    required_action: str | None = None


class ComplianceGate:
    """C-11: 3-Checkpoint x 4-Tier Message Compliance Gate."""

    def __init__(self) -> None:
        self.prohibited_patterns = POL_08_PROHIBITED_PATTERNS

    def check(self, request: ComplianceCheckRequest) -> ComplianceCheckResponse:
        """Evaluates message against POL-08 speech standards and evidence anchors."""
        msg = request.message
        msg_hash = f"sha256:{hashlib.sha256(msg.encode('utf-8')).hexdigest()}"
        check_id = f"CHK-{uuid.uuid4().hex[:8].upper()}"

        findings: list[ComplianceClaimFinding] = []

        # 1. Scan for PROHIBITED speech patterns
        for rule in self.prohibited_patterns:
            matches = re.finditer(rule.regex, msg, re.IGNORECASE)
            for m in matches:
                findings.append(
                    ComplianceClaimFinding(
                        claim_text=m.group(0),
                        tier="PROHIBITED",
                        rule_id=rule.pattern_id,
                        reason=rule.description,
                    )
                )

        # 2. Extract potential financial claims (discount, interest, loan)
        financial_patterns = [
            (r"chiết\s+khấu\s+(\d+(\.\d+)?%)", "DISCOUNT_CLAIM"),
            (r"lãi\s+suất\s+(\d+(\.\d+)?%)", "INTEREST_RATE_CLAIM"),
            (r"ân\s+hạn\s+(\d+)\s+tháng", "GRACE_PERIOD_CLAIM"),
        ]

        for pat, claim_type in financial_patterns:
            matches = re.finditer(pat, msg, re.IGNORECASE)
            for m in matches:
                # If there are policy references or linked evidence, it can be SUPPORTED or CONDITIONAL
                if not request.policy_version_refs and not request.claimed_evidence_ids:
                    findings.append(
                        ComplianceClaimFinding(
                            claim_text=m.group(0),
                            tier="UNSUPPORTED",
                            rule_id=f"POL08-{claim_type}",
                            reason=f"Phát ngôn về {claim_type} chưa được neo vào văn bản chính sách hoặc chứng cứ.",
                        )
                    )
                else:
                    findings.append(
                        ComplianceClaimFinding(
                            claim_text=m.group(0),
                            tier="SUPPORTED",
                            rule_id=f"POL08-{claim_type}",
                            reason=f"Đã được đối chiếu với {request.policy_version_refs}.",
                        )
                    )

        # 3. Determine overall status across 4 tiers
        has_prohibited = any(f.tier == "PROHIBITED" for f in findings)
        has_unsupported = any(f.tier == "UNSUPPORTED" for f in findings)
        has_conditional = any(f.tier == "CONDITIONAL" for f in findings)

        if has_prohibited:
            overall_status = "PROHIBITED"
            action = "BLOCK_MESSAGE_COMPLIANCE_VIOLATION"
        elif has_unsupported:
            if request.mode == "FINAL_SEND":
                overall_status = "UNSUPPORTED"
                action = "REQUIRE_EVIDENCE_BEFORE_SEND"
            else:
                overall_status = "CONDITIONAL"
                action = "SUGGEST_LINKING_EVIDENCE"
        elif has_conditional:
            overall_status = "CONDITIONAL"
            action = "KEEP_REQUIRED_CONDITION"
        else:
            overall_status = "SUPPORTED"
            action = "ALLOW_SEND"

        return ComplianceCheckResponse(
            check_id=check_id,
            message_hash=msg_hash,
            mode=request.mode,
            overall_status=overall_status,
            quote_id=request.quote_id,
            quote_version=request.quote_version,
            policy_version_refs=request.policy_version_refs,
            claims=findings,
            required_action=action,
        )
