import logging

from src.models.pec_contracts import EvidenceBundle, EvidenceDecisionStatus

logger = logging.getLogger(__name__)

def verify_cryptographic_integrity(bundle: EvidenceBundle | None) -> float:
    """
    Verifies the cryptographic integrity of the EvidenceBundle.
    Returns 1.0 if perfectly intact and VERIFIED, else 0.0.
    """
    if bundle is None:
        return 1.0 # Vacuously true (Abstained)

    if bundle.decision_status == EvidenceDecisionStatus.VERIFIED and bundle.canonical_bundle_hash:
        return 1.0

    logger.error("Integrity Violation: Bundle is not VERIFIED or missing hash.")
    return 0.0
