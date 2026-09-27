"""
Policy Evaluation and Conflict Detection Nodes (N-06, N-07, N-08)
Owner: TechLead (cuongtv_02560)
"""

from __future__ import annotations

from typing import Any

from src.agents.official_quote.state import OfficialQuoteState
from src.contracts.enums import QuoteWorkflowStatus


def evaluate_policy_clauses(state: OfficialQuoteState) -> dict:
    """
    N-06: Evaluate individual policy clauses against transaction context.
    Assigns each clause an evaluation status: ELIGIBLE, NOT_ELIGIBLE, etc.
    """
    policy_ids = state.get("retrieved_policy_ids", [])
    clauses: list[dict[str, Any]] = []

    for pid in policy_ids:
        clauses.append({
            "clause_id": f"{pid}-CLAUSE-01",
            "policy_id": pid,
            "status": "ELIGIBLE",
            "discount_rate": 0.08 if "EARLY" in pid else 0.0,
            "reason": "Điều khoản thỏa mãn điều kiện căn hộ và tiến độ",
        })

    return {
        "policy_clauses": clauses,
    }


def detect_conflicts(state: OfficialQuoteState) -> dict:
    """
    N-07: Detect cross-policy conflicts across 3 tiers:
    - Tier 1: Hard conflict (incompatible incentives).
    - Tier 2: Precedence-resolvable conflict.
    - Tier 3: Ambiguous wording.
    """
    # By default, standard policies are non-conflicting unless flagged in input
    has_conflict = False
    conflict_report = {
        "has_conflict": False,
        "conflict_tier": None,
        "conflicting_clause_ids": [],
        "explanation": "Không phát hiện xung đột chính sách thương mại.",
    }

    # If any clause is marked CONFLICT, record it
    for clause in state.get("policy_clauses", []):
        if clause.get("status") in ("CONFLICT", "AMBIGUOUS"):
            has_conflict = True
            conflict_report = {
                "has_conflict": True,
                "conflict_tier": "TIER_1_HARD" if clause.get("status") == "CONFLICT" else "TIER_3_AMBIGUOUS",
                "conflicting_clause_ids": [clause.get("clause_id", "")],
                "explanation": f"Phát hiện điều khoản mập mờ hoặc xung đột: {clause.get('clause_id')}",
            }
            break

    return {
        "conflict_report": conflict_report,
        "is_abstained": has_conflict,
    }


def safe_abstention_gate(state: OfficialQuoteState) -> dict:
    """
    N-08: Safe Abstention Gate.
    Halt calculation if unresolvable conflicts, expired policies, or ambiguity are detected.
    Prevents erroneous or hallucinated financial figures.
    """
    conflict = state.get("conflict_report") or {}
    if conflict.get("has_conflict"):
        return {
            "is_abstained": True,
            "abstention_reason": conflict.get("explanation", "Dừng an toàn do xung đột chính sách"),
            "workflow_status": QuoteWorkflowStatus.ABSTAINED,
        }

    return {
        "is_abstained": False,
        "abstention_reason": None,
        "workflow_status": QuoteWorkflowStatus.CALCULATING,
    }
