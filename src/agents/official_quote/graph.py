"""
Official Quote StateGraph Builder (23 Nodes Topology)
Owner: TechLead (cuongtv_02560)
Component: C-01 (Official Quote StateGraph Orchestrator)
"""

from __future__ import annotations

from typing import Literal

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph

from src.agents.official_quote.nodes import (
    assemble_approval_package,
    await_manager_approval,
    call_pricing_engine,
    commit_quote_transaction,
    detect_conflicts,
    evaluate_exception_approval,
    evaluate_policy_clauses,
    evaluate_revision_request,
    freeze_audit_hash,
    generate_explanations,
    load_transaction_context,
    prepare_pricing_input,
    rank_scenarios,
    request_kms_attestation,
    retrieve_active_policies,
    safe_abstention_gate,
    security_guardrail_input,
    security_guardrail_output,
    security_guardrail_policy,
    tool_guardrail_pricing,
    validate_financial_sanity,
    validate_input,
    verify_claim_evidence,
)
from src.agents.official_quote.state import OfficialQuoteState


# Routing conditions
def route_after_validate_input(state: OfficialQuoteState) -> Literal["security_guardrail_input", "__end__"]:
    if not state.get("is_input_valid", False):
        return END
    return "security_guardrail_input"


def route_after_security_input(state: OfficialQuoteState) -> Literal["load_transaction_context", "__end__"]:
    if state.get("is_blocked", False):
        return END
    return "load_transaction_context"


def route_after_security_policy(state: OfficialQuoteState) -> Literal["evaluate_policy_clauses", "__end__"]:
    if state.get("is_abstained", False):
        return END
    return "evaluate_policy_clauses"


def route_after_safe_abstention(state: OfficialQuoteState) -> Literal["prepare_pricing_input", "evaluate_exception_approval"]:
    if state.get("is_abstained", False):
        return "evaluate_exception_approval"
    return "prepare_pricing_input"


def route_after_tool_guardrail(state: OfficialQuoteState) -> Literal["call_pricing_engine", "__end__"]:
    if state.get("is_blocked", False):
        return END
    return "call_pricing_engine"


def route_after_sanity_validation(state: OfficialQuoteState) -> Literal["rank_scenarios", "__end__"]:
    if not state.get("sanity_passed", False):
        return END
    return "rank_scenarios"


def route_after_security_output(state: OfficialQuoteState) -> Literal["verify_claim_evidence", "__end__"]:
    if state.get("is_blocked", False):
        return END
    return "verify_claim_evidence"


def route_after_claim_verification(state: OfficialQuoteState) -> Literal["assemble_approval_package", "__end__"]:
    if not state.get("claims_verified", False):
        return END
    return "assemble_approval_package"


def route_after_manager_approval(
    state: OfficialQuoteState,
) -> Literal["evaluate_revision_request", "evaluate_exception_approval", "freeze_audit_hash", "__end__"]:
    if state.get("is_blocked", False):
        return END

    decision = state.get("manager_decision", "APPROVE")
    if decision == "REQUEST_REVISION":
        return "evaluate_revision_request"
    elif decision == "SUBMIT_EXCEPTION":
        return "evaluate_exception_approval"
    elif decision == "REJECT":
        return END

    return "freeze_audit_hash"


def build_official_quote_graph(
    checkpointer: BaseCheckpointSaver | None = None,
    interrupt_on_review: bool = True,
):
    """
    Build and compile the 23-node Official Quote StateGraph with revision loop,
    exception routing, and HITL interrupt gate.
    """
    workflow = StateGraph(OfficialQuoteState)

    # 1. Register all 23 Nodes
    workflow.add_node("validate_input", validate_input)
    workflow.add_node("security_guardrail_input", security_guardrail_input)
    workflow.add_node("load_transaction_context", load_transaction_context)
    workflow.add_node("retrieve_active_policies", retrieve_active_policies)
    workflow.add_node("security_guardrail_policy", security_guardrail_policy)
    workflow.add_node("evaluate_policy_clauses", evaluate_policy_clauses)
    workflow.add_node("detect_conflicts", detect_conflicts)
    workflow.add_node("safe_abstention_gate", safe_abstention_gate)
    workflow.add_node("prepare_pricing_input", prepare_pricing_input)
    workflow.add_node("tool_guardrail_pricing", tool_guardrail_pricing)
    workflow.add_node("call_pricing_engine", call_pricing_engine)
    workflow.add_node("validate_financial_sanity", validate_financial_sanity)
    workflow.add_node("rank_scenarios", rank_scenarios)
    workflow.add_node("generate_explanations", generate_explanations)
    workflow.add_node("security_guardrail_output", security_guardrail_output)
    workflow.add_node("verify_claim_evidence", verify_claim_evidence)
    workflow.add_node("assemble_approval_package", assemble_approval_package)
    workflow.add_node("await_manager_approval", await_manager_approval)
    workflow.add_node("evaluate_revision_request", evaluate_revision_request)
    workflow.add_node("evaluate_exception_approval", evaluate_exception_approval)
    workflow.add_node("freeze_audit_hash", freeze_audit_hash)
    workflow.add_node("request_kms_attestation", request_kms_attestation)
    workflow.add_node("commit_quote_transaction", commit_quote_transaction)

    # 2. Edges & Conditional Routing
    workflow.add_edge(START, "validate_input")
    workflow.add_conditional_edges("validate_input", route_after_validate_input)
    workflow.add_conditional_edges("security_guardrail_input", route_after_security_input)
    workflow.add_edge("load_transaction_context", "retrieve_active_policies")
    workflow.add_edge("retrieve_active_policies", "security_guardrail_policy")
    workflow.add_conditional_edges("security_guardrail_policy", route_after_security_policy)
    workflow.add_edge("evaluate_policy_clauses", "detect_conflicts")
    workflow.add_edge("detect_conflicts", "safe_abstention_gate")
    workflow.add_conditional_edges("safe_abstention_gate", route_after_safe_abstention)

    # Exception path loops back to clause evaluation
    workflow.add_edge("evaluate_exception_approval", "evaluate_policy_clauses")

    workflow.add_edge("prepare_pricing_input", "tool_guardrail_pricing")
    workflow.add_conditional_edges("tool_guardrail_pricing", route_after_tool_guardrail)
    workflow.add_edge("call_pricing_engine", "validate_financial_sanity")
    workflow.add_conditional_edges("validate_financial_sanity", route_after_sanity_validation)
    workflow.add_edge("rank_scenarios", "generate_explanations")
    workflow.add_edge("generate_explanations", "security_guardrail_output")
    workflow.add_conditional_edges("security_guardrail_output", route_after_security_output)
    workflow.add_edge("verify_claim_evidence", "assemble_approval_package")
    workflow.add_edge("assemble_approval_package", "await_manager_approval")

    # Manager Decision & Revision Loop Edge
    workflow.add_conditional_edges("await_manager_approval", route_after_manager_approval)
    workflow.add_edge("evaluate_revision_request", "prepare_pricing_input")  # REVISION LOOP!

    # Attestation & Commit Path
    workflow.add_edge("freeze_audit_hash", "request_kms_attestation")
    workflow.add_edge("request_kms_attestation", "commit_quote_transaction")
    workflow.add_edge("commit_quote_transaction", END)

    interrupt_nodes = ["await_manager_approval"] if interrupt_on_review else []
    return workflow.compile(
        checkpointer=checkpointer,
        interrupt_before=interrupt_nodes,
    )
