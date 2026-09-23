import logging
from datetime import datetime

from src.models.rag_schemas import AttributedPolicyEvidence

logger = logging.getLogger(__name__)

def calculate_time_travel_leakage(evidences: list[AttributedPolicyEvidence], query_date_str: str) -> float:
    """
    Verifies that no retrieved evidences are outside their valid date range.
    Leakage should be 0.0. Returns the percentage of leaked clauses.
    """
    if not evidences:
        return 0.0

    query_date = datetime.strptime(query_date_str, "%Y-%m-%d").date()
    leak_count = 0

    for evidence in evidences:
        valid_from = evidence.valid_from
        valid_to = evidence.valid_to

        if query_date < valid_from or query_date > valid_to:
            logger.error(f"Time-Travel Leakage detected: Policy {evidence.coordinate.policy_id} ({valid_from} to {valid_to}) retrieved for query date {query_date}")
            leak_count += 1

    return leak_count / len(evidences)
