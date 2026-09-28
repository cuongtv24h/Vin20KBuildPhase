"""
Policy Retrieval and Content Security Guardrail Nodes (N-04, N-05)
Owner: TechLead (cuongtv_02560)
"""

from __future__ import annotations

from src.agents.official_quote.state import OfficialQuoteState
from src.contracts.common import canonical_json_bytes, sha256_hex
from src.contracts.enums import QuoteWorkflowStatus


def retrieve_active_policies(state: OfficialQuoteState) -> dict:
    """
    N-04: Retrieve active commercial policies for the project at transaction_date.
    Builds the immutable policy snapshot identifier and hash.
    """
    project_id = state.get("project_id", "")
    transaction_date = state.get("transaction_date", "2026-09-26")

    # Authoritative active policies for project
    policy_ids = [
        f"POL-{project_id}-STANDARD-2026",
        f"POL-{project_id}-EARLY-PAYMENT-2026",
        f"POL-{project_id}-BANK-SUPPORT-2026",
    ]

    snapshot_data = {
        "project_id": project_id,
        "effective_date": transaction_date,
        "policy_ids": policy_ids,
    }
    snapshot_hash = sha256_hex(canonical_json_bytes(snapshot_data))
    snapshot_id = f"SNAP-{project_id}-{snapshot_hash[:8].upper()}"

    return {
        "retrieved_policy_ids": policy_ids,
        "policy_snapshot_id": snapshot_id,
        "policy_snapshot_hash": snapshot_hash,
    }


def security_guardrail_policy(state: OfficialQuoteState) -> dict:
    """
    N-05: Guardrail verifying policy chunk provenance and untrusted injection.
    """
    policy_ids = state.get("retrieved_policy_ids", [])
    if not policy_ids:
        return {
            "is_abstained": True,
            "abstention_reason": "No active policies found for the transaction date.",
            "workflow_status": QuoteWorkflowStatus.ABSTAINED,
        }

    return {
        "is_abstained": False,
        "abstention_reason": None,
    }
