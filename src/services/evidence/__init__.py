"""Evidence Linking, Closure & Verification Service (C-04).

Exports EvidenceLinker, CoordinateParser, EvidenceVerifier, AbstentionGenerator, and TDECClosure.

`QuoteEvidenceService` được export ở CUỐI danh sách import: module này dùng lại `EvidenceLinker`
ở trên nên phải để các import nền hoàn tất trước (tránh vòng import một phần).
"""

from src.services.evidence.closure.tdec import TDECClosure
from src.services.evidence.coordinate_parser import CoordinateParser, NormalizedCoordinate
from src.services.evidence.linker import ClaimVerificationResult, EvidenceLinker
from src.services.evidence.verification.abstention import AbstentionGenerator
from src.services.evidence.verification.evidence_verifier import EvidenceVerifier

from src.services.evidence.quote_evidence import (  # isort: skip — xem docstring
    QuoteEvidenceResult,
    QuoteEvidenceService,
    ReadinessItem,
    bundle_id_for,
)

__all__ = [
    "EvidenceLinker",
    "ClaimVerificationResult",
    "CoordinateParser",
    "NormalizedCoordinate",
    "EvidenceVerifier",
    "AbstentionGenerator",
    "TDECClosure",
    "QuoteEvidenceService",
    "QuoteEvidenceResult",
    "ReadinessItem",
    "bundle_id_for",
]
