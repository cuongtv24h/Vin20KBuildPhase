"""Evidence Linking, Closure & Verification Service (C-04).

Exports EvidenceLinker, CoordinateParser, EvidenceVerifier, AbstentionGenerator, and TDECClosure.
"""

from src.services.evidence.closure.tdec import TDECClosure
from src.services.evidence.coordinate_parser import CoordinateParser, NormalizedCoordinate
from src.services.evidence.linker import ClaimVerificationResult, EvidenceLinker
from src.services.evidence.verification.abstention import AbstentionGenerator
from src.services.evidence.verification.evidence_verifier import EvidenceVerifier

__all__ = [
    "EvidenceLinker",
    "ClaimVerificationResult",
    "CoordinateParser",
    "NormalizedCoordinate",
    "EvidenceVerifier",
    "AbstentionGenerator",
    "TDECClosure",
]
