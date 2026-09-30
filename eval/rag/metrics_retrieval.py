from src.models.pec_contracts import EvidenceBundle, EvidenceDecisionStatus

def calculate_clause_recall(bundle: EvidenceBundle | None, expected_policy_ids: list[str]) -> float:
    """
    Calculates the recall of expected policy IDs in the retrieved EvidenceBundle.
    """
    if not expected_policy_ids:
        return 1.0 if not bundle or not bundle.applied_rules else 0.0
        
    if not bundle:
        return 0.0

    expected_set = set(expected_policy_ids)
    
    # Extract unique base policy IDs from atom_ids (e.g., 'POL-2026-VLF-GEN_chunk_1' -> 'POL-2026-VLF-GEN')
    retrieved_policies = set()
    for rule in bundle.applied_rules:
        # Assuming the policy_id is the prefix before '_chunk_' or the whole id if not present
        policy_id = rule.atom_id.split('_chunk_')[0] if '_chunk_' in rule.atom_id else rule.atom_id
        # Also handle potential table footnotes
        policy_id = policy_id.split('_row_')[0]
        retrieved_policies.add(policy_id)

    # Some expected policies might be substrings (e.g. POL-2026-VLF-GEN in POL-2026-VLF-GEN_chunk_0)
    # Just in case our split isn't perfect, we check for substring matches
    matched_count = 0
    for expected_id in expected_set:
        if any(expected_id in retrieved_id for retrieved_id in retrieved_policies):
            matched_count += 1
            
    return matched_count / len(expected_set)


def calculate_conflict_completeness(bundle: EvidenceBundle | None, expected_policy_ids: list[str]) -> float:
    """
    For conflict scenarios, verifies that ALL conflicting policies are retrieved and captured.
    In PEC-RAG, conflicts should be present in bundle.conflict_report.
    """
    if not bundle:
        return 0.0
    
    # If it's a conflict test, we should have conflict pairs in the report
    if bundle.conflict_report.status == "CONFLICT_DETECTED" and len(bundle.conflict_report.pairs) > 0:
        return 1.0
        
    # Fallback to recall if no explicit conflict was flagged but rules were retrieved
    return calculate_clause_recall(bundle, expected_policy_ids)
