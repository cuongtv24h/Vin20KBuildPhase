import logging

from src.models.rag_schemas import AttributedPolicyEvidence

logger = logging.getLogger(__name__)

def verify_cryptographic_integrity(evidences: list[AttributedPolicyEvidence]) -> float:
    """
    Verifies the SHA-256 integrity of retrieved evidences.
    Returns the percentage of perfectly intact evidences (should be 1.0).
    """
    if not evidences:
        return 1.0 # Vacuously true

    intact_count = 0

    for evidence in evidences:
        if evidence.verify_integrity():
            intact_count += 1
        else:
            logger.error(f"Integrity Violation: Hash mismatch for {evidence.coordinate.citation_path}")

    return intact_count / len(evidences)
