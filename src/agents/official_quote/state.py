"""
Official Quote State Definition (LangGraph StateGraph Schema)
Owner: TechLead (cuongtv_02560)
Component: C-01 (Official Quote StateGraph Orchestrator)
"""

from __future__ import annotations

from typing import Any, TypedDict

from src.contracts.enums import (
    ApprovalStatus,
    OptimizationObjective,
    PdfStatus,
    QuoteWorkflowStatus,
)


class OfficialQuoteState(TypedDict, total=False):
    """
    Lean, strongly-typed state schema for the 23-node Official Quote StateGraph.
    Enforces Triple Enum Isolation and strict immutable decision lineage.
    """

    # --- Core Identifiers & Context ---
    quote_id: str
    quote_version: int
    trace_id: str
    tenant_id: str
    project_id: str
    unit_code: str
    transaction_date: str
    listed_price_before_tax_vnd: int
    deposit_amount_vnd: int
    own_funds_vnd: int
    monthly_capacity_vnd: int
    objective: OptimizationObjective
    transaction_context: dict[str, Any]

    # --- Security & Input Guardrails ---
    is_input_valid: bool
    security_event: str | None
    security_reason: str | None
    is_blocked: bool
    blocked_reason: str | None

    # --- Policy Retrieval & Conflict Evaluation ---
    retrieved_policy_ids: list[str]
    policy_snapshot_id: str | None
    policy_snapshot_hash: str | None
    policy_clauses: list[dict[str, Any]]
    conflict_report: dict[str, Any] | None
    is_abstained: bool
    abstention_reason: str | None

    # --- Pricing & Sanity Checking ---
    pricing_input: dict[str, Any] | None
    pricing_result: dict[str, Any] | None
    sanity_passed: bool
    sanity_errors: list[str]

    # --- Scenario Ranking & Transparent Explanations ---
    recommended_scenario_code: str | None
    ranking_summary: list[dict[str, Any]]
    dual_explanation: dict[str, Any] | None
    claims_verified: bool
    unsupported_claims: list[str]

    # --- Governance & HITL Approval ---
    approval_package: dict[str, Any] | None
    manager_decision: str | None  # "APPROVE", "REQUEST_REVISION", "REJECT", "SUBMIT_EXCEPTION"
    manager_notes: str | None
    manager_id: str | None
    creator_id: str | None
    revision_count: int
    exception_record: dict[str, Any] | None

    # --- Cryptographic Attestation & Outbox Commit ---
    frozen_snapshot_hash: str | None
    server_attestation_signature: str | None
    public_key_b64: str | None
    previous_audit_event_hash: str | None
    final_audit_event_hash: str | None
    ready_for_commit: bool
    committed: bool

    # --- Triple Enum Isolation (ADR-004) ---
    workflow_status: QuoteWorkflowStatus
    approval_status: ApprovalStatus
    pdf_status: PdfStatus

    # --- Error Diagnostics ---
    errors: list[str]
