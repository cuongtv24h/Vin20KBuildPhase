from src.models.rag_schemas import AttributedPolicyEvidence


def calculate_clause_recall(evidences: list[AttributedPolicyEvidence], expected_policy_ids: list[str]) -> float:
    """
    Calculates the recall of expected policy IDs in the retrieved evidences.
    Returns a float between 0.0 and 1.0.
    """
    if not expected_policy_ids:
        return 1.0 if not evidences else 0.0

    expected_set = set(expected_policy_ids)
    retrieved_policies = set([e.coordinate.policy_id for e in evidences])

    intersection = expected_set.intersection(retrieved_policies)
    return len(intersection) / len(expected_set)

def calculate_conflict_completeness(evidences: list[AttributedPolicyEvidence], expected_policy_ids: list[str]) -> float:
    """
    For conflict scenarios, verifies that ALL conflicting policies are retrieved so the Pruner can evaluate them.
    """
    return calculate_clause_recall(evidences, expected_policy_ids)
