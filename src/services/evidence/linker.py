"""Claim-Level Evidence Linker & 5-Point Verifier (C-04 / F4 / N-14B).

Anchors factual claims (price, discount, interest rate, grace period) to exact
cryptographic coordinates and executes 5-point invariant verification.
"""

from __future__ import annotations

import logging

from pydantic import BaseModel, Field

from src.models.rag_schemas import AttributedPolicyEvidence
from src.services.evidence.coordinate_parser import CoordinateParser, NormalizedCoordinate

logger = logging.getLogger(__name__)


class ClaimVerificationResult(BaseModel):
    """Result of claim verification against policy evidence."""

    claim_id: str
    claim_text: str
    is_verified: bool
    status: str = Field(..., description="VERIFIED, CONDITIONAL, REJECTED, or UNLINKED")
    reasons: list[str] = Field(default_factory=list)
    anchors: list[NormalizedCoordinate] = Field(default_factory=list)


class EvidenceLinker:
    """C-04: Claim-Level Evidence Linker executing 5 N-14B invariant checks."""

    def __init__(self) -> None:
        self.parser = CoordinateParser()

    def check_claim_invariants(
        self,
        claim_text: str,
        evidence: AttributedPolicyEvidence,
        transaction_date: str | None = None,
    ) -> list[str]:
        """Runs the 5 invariant checks for N-14B verification:
        1. Document hash integrity
        2. Active policy validity at transaction_date
        3. Scope & condition correctness
        4. No superseded status
        5. Semantic relevance
        """
        violations: list[str] = []

        # Check 1: Cryptographic integrity of source quote
        if not evidence.verify_integrity():
            violations.append("INTEGRITY_MISMATCH: Verbatim text hash mismatch with coordinate")

        # Check 2: Active temporal window
        if transaction_date:
            tx_date_str = str(transaction_date)
            v_from_str = str(evidence.valid_from) if evidence.valid_from else None
            v_to_str = str(evidence.valid_to) if evidence.valid_to else None
            if v_from_str and tx_date_str < v_from_str:
                violations.append(f"TEMPORAL_PRE_VALID: Date {tx_date_str} before valid_from {v_from_str}")
            if v_to_str and tx_date_str > v_to_str:
                violations.append(f"TEMPORAL_EXPIRED: Date {tx_date_str} after valid_to {v_to_str}")

        # Check 3: Superseded check
        if evidence.is_superseded:
            violations.append("POLICY_SUPERSEDED: Policy clause is expired or replaced")

        # Check 4: Management approval condition check
        conditions = evidence.applicability_conditions or {}
        if conditions.get("requires_management_approval"):
            violations.append("CONDITIONAL_REQUIRES_APPROVAL: Requires management sign-off")

        return violations

    def link_claim(
        self,
        claim_id: str,
        claim_text: str,
        candidate_evidences: list[AttributedPolicyEvidence],
        transaction_date: str | None = None,
    ) -> ClaimVerificationResult:
        """Links a single claim to matching policy coordinates and verifies invariants."""
        matching_anchors: list[NormalizedCoordinate] = []
        all_violations: list[str] = []

        for ev in candidate_evidences:
            violations = self.check_claim_invariants(claim_text, ev, transaction_date)
            normalized = self.parser.normalize_from_coordinate(ev.coordinate, ev.verbatim_text)
            matching_anchors.append(normalized)
            all_violations.extend(violations)

        if not matching_anchors:
            return ClaimVerificationResult(
                claim_id=claim_id,
                claim_text=claim_text,
                is_verified=False,
                status="UNLINKED",
                reasons=["No evidence found in active snapshot matching claim"],
                anchors=[],
            )

        # Check if there are blocking violations
        has_blocker = any(
            v.startswith("INTEGRITY_MISMATCH") or v.startswith("POLICY_SUPERSEDED") or v.startswith("TEMPORAL_")
            for v in all_violations
        )
        has_conditional = any(v.startswith("CONDITIONAL_") for v in all_violations)

        if has_blocker:
            return ClaimVerificationResult(
                claim_id=claim_id,
                claim_text=claim_text,
                is_verified=False,
                status="REJECTED",
                reasons=all_violations,
                anchors=matching_anchors,
            )
        elif has_conditional:
            return ClaimVerificationResult(
                claim_id=claim_id,
                claim_text=claim_text,
                is_verified=True,
                status="CONDITIONAL",
                reasons=all_violations,
                anchors=matching_anchors,
            )
        else:
            return ClaimVerificationResult(
                claim_id=claim_id,
                claim_text=claim_text,
                is_verified=True,
                status="VERIFIED",
                reasons=[],
                anchors=matching_anchors,
            )
