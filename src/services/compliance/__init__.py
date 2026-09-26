"""Message Compliance Gate Service (C-11 / F8).

Exports ComplianceGate, ComplianceCheckRequest, ComplianceCheckResponse, and POL-08 rules.
"""

from src.services.compliance.gate import (
    ComplianceCheckRequest,
    ComplianceCheckResponse,
    ComplianceClaimFinding,
    ComplianceGate,
)
from src.services.compliance.rules import POL_08_PROHIBITED_PATTERNS

__all__ = [
    "ComplianceGate",
    "ComplianceCheckRequest",
    "ComplianceCheckResponse",
    "ComplianceClaimFinding",
    "POL_08_PROHIBITED_PATTERNS",
]
