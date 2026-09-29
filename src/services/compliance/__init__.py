"""Message Compliance Gate Service (C-11 / F8)."""

from src.services.compliance.gate import (
    ComplianceCheckRequest,
    ComplianceCheckResponse,
    ComplianceClaimFinding,
    ComplianceGate,
    ComplianceGateService,
    analyze_message_claims,
    determine_tier,
)
from src.services.compliance.rules import POL_08_PROHIBITED_PATTERNS

__all__ = [
    "ComplianceGate",
    "ComplianceGateService",
    "ComplianceCheckRequest",
    "ComplianceCheckResponse",
    "ComplianceClaimFinding",
    "POL_08_PROHIBITED_PATTERNS",
    "analyze_message_claims",
    "determine_tier",
]
