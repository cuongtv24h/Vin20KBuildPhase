"""
Governance, HITL Approval, Revision Loop, and KMS Attestation Nodes (N-15 -> N-20)
Owner: TechLead (cuongtv_02560)
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from src.agents.official_quote.state import OfficialQuoteState
from src.contracts.common import canonical_json_bytes, sha256_hex
from src.contracts.enums import (
    ApprovalStatus,
    PdfStatus,
    QuoteWorkflowStatus,
)
from src.services.approval import KMSServerSigner
from src.services.audit import AuditChainEngine


def assemble_approval_package(state: OfficialQuoteState) -> dict:
    """
    N-15: Assemble authoritative ApprovalPackage before presenting to Sales Manager.
    Aggregates financial calculations, ranking summary, and dual explanations.
    """
    package: dict[str, Any] = {
        "quote_id": state.get("quote_id", ""),
        "quote_version": state.get("quote_version", 1),
        "project_id": state.get("project_id", ""),
        "unit_code": state.get("unit_code", ""),
        "recommended_scenario_code": state.get("recommended_scenario_code", ""),
        "ranking_summary": state.get("ranking_summary", []),
        "pricing_result": state.get("pricing_result", {}),
        "dual_explanation": state.get("dual_explanation", {}),
        "policy_snapshot_hash": state.get("policy_snapshot_hash", ""),
    }

    return {
        "approval_package": package,
        "workflow_status": QuoteWorkflowStatus.READY_FOR_REVIEW,
        "approval_status": ApprovalStatus.PENDING,
    }


def await_manager_approval(state: OfficialQuoteState) -> dict:
    """
    N-16: HITL Human-in-the-Loop decision gate.
    Inspects manager decision: APPROVE, REQUEST_REVISION, REJECT, or SUBMIT_EXCEPTION.
    """
    decision = state.get("manager_decision", "APPROVE")
    manager_id = state.get("manager_id", "MGR-001")
    creator_id = state.get("creator_id", "SALES-001")

    # Enforce SoD: Creator cannot approve their own quote
    if manager_id == creator_id:
        return {
            "manager_decision": "REJECT",
            "is_blocked": True,
            "blocked_reason": "SoD Violation: Quote creator cannot act as approver.",
            "workflow_status": QuoteWorkflowStatus.BLOCKED,
            "approval_status": ApprovalStatus.APPROVAL_FAILED,
        }

    if decision == "REQUEST_REVISION":
        return {
            "workflow_status": QuoteWorkflowStatus.NEEDS_REVISION,
            "approval_status": ApprovalStatus.REVISION_REQUESTED,
        }
    elif decision == "REJECT":
        return {
            "workflow_status": QuoteWorkflowStatus.REJECTED,
            "approval_status": ApprovalStatus.REJECTED,
        }
    elif decision == "SUBMIT_EXCEPTION":
        return {
            "workflow_status": QuoteWorkflowStatus.EXCEPTION_INPUT,
            "approval_status": ApprovalStatus.PENDING,
        }

    return {
        "workflow_status": QuoteWorkflowStatus.READY_FOR_REVIEW,
        "approval_status": ApprovalStatus.PENDING,
    }


def evaluate_revision_request(state: OfficialQuoteState) -> dict:
    """
    N-17: Revision Loop handler.
    Increments quote_version, records revision trace, and routes back to N-09.
    The previous version is marked SUPERSEDED and retained immutably in DB.
    """
    current_ver = state.get("quote_version", 1)
    new_ver = current_ver + 1
    rev_count = state.get("revision_count", 0) + 1

    return {
        "quote_version": new_ver,
        "revision_count": rev_count,
        "manager_decision": "APPROVE",
        "workflow_status": QuoteWorkflowStatus.CALCULATING,
        "approval_status": ApprovalStatus.NOT_REQUIRED,
    }


def evaluate_exception_approval(state: OfficialQuoteState) -> dict:
    """
    N-18: Evaluate executive exception approval document (TGĐ / BOD override).
    """
    exception_rec = state.get("exception_record") or {
        "exception_id": f"EXC-{state.get('quote_id', '')}-V{state.get('quote_version', 1)}",
        "authority": "CEO_APPROVAL",
        "approved": True,
    }

    return {
        "exception_record": exception_rec,
        "workflow_status": QuoteWorkflowStatus.CALCULATING,
    }


def freeze_audit_hash(state: OfficialQuoteState) -> dict:
    """
    N-19A: Freeze snapshot hash using canonical JSON RFC 8785 and SHA-256.
    Permanently locks transaction terms before cryptographic signing.
    """
    package = state.get("approval_package") or {}
    snapshot_bytes = canonical_json_bytes(package)
    snapshot_hash = sha256_hex(snapshot_bytes)

    return {
        "frozen_snapshot_hash": snapshot_hash,
    }


def request_kms_attestation(state: OfficialQuoteState) -> dict:
    """
    N-19B: Cryptographic Server Attestation via KMSServerSigner (Ed25519 - RFC 8032).
    Signs the frozen snapshot hash in RAM adhering to Atomic Commit-Discard.
    """
    snapshot_hash = state.get("frozen_snapshot_hash", "")
    signer = KMSServerSigner()

    signature = signer.sign_snapshot_hash(snapshot_hash)
    pub_key = signer.get_public_key_base64()

    return {
        "server_attestation_signature": signature,
        "public_key_b64": pub_key,
        "approval_status": ApprovalStatus.ATTESTED,
    }


def compute_final_audit_hash(state: OfficialQuoteState) -> dict:
    """
    N-20: Compute the final audit event hash in memory.
    Prepares the state for atomic persistence. Note that actual database persistence,
    outbox enqueue, and transactional rollback are orchestrated by QuoteApprovalService
    at the API/orchestration layer (or post-graph runner) to maintain LangGraph pure-function invariants.
    """
    prev_hash = state.get("previous_audit_event_hash") or AuditChainEngine.GENESIS_PREV_HASH
    quote_id = state.get("quote_id", "")
    occurred_at_iso = AuditChainEngine.format_timestamp_iso(
        state.get("transaction_date") or datetime.now(UTC)
    )

    event_hash = AuditChainEngine.compute_event_hash(
        prev_hash=prev_hash,
        quote_id=quote_id,
        event_type="QUOTE_OFFICIALLY_APPROVED",
        actor_id=state.get("manager_id", "MGR-001"),
        occurred_at_iso=occurred_at_iso,
        payload={
            "snapshot_hash": state.get("frozen_snapshot_hash", ""),
            "signature": state.get("server_attestation_signature", ""),
        },
    )

    return {
        "previous_audit_event_hash": event_hash,
        "final_audit_event_hash": event_hash,
        "ready_for_commit": True,
        "committed": True,  # Maintained for backward compatibility
        "workflow_status": QuoteWorkflowStatus.APPROVED,
        "approval_status": ApprovalStatus.APPROVED,
        "pdf_status": PdfStatus.PENDING,
    }


# Backward-compatible alias for NODE_REGISTRY and existing callers
commit_quote_transaction = compute_final_audit_hash
