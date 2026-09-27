"""
Official Quote StateGraph Node Registry
Owner: TechLead (cuongtv_02560)
Locks all 23 canonical node functions in the official NODE_REGISTRY.
"""

from src.agents.official_quote.nodes.approval import (
    assemble_approval_package,
    await_manager_approval,
    commit_quote_transaction,
    compute_final_audit_hash,
    evaluate_exception_approval,
    evaluate_revision_request,
    freeze_audit_hash,
    request_kms_attestation,
)
from src.agents.official_quote.nodes.context import load_transaction_context
from src.agents.official_quote.nodes.evaluation import (
    detect_conflicts,
    evaluate_policy_clauses,
    safe_abstention_gate,
)
from src.agents.official_quote.nodes.explanation import (
    generate_explanations,
    security_guardrail_output,
    verify_claim_evidence,
)
from src.agents.official_quote.nodes.input_guards import (
    security_guardrail_input,
    validate_input,
)
from src.agents.official_quote.nodes.policy_retrieval import (
    retrieve_active_policies,
    security_guardrail_policy,
)
from src.agents.official_quote.nodes.pricing import (
    call_pricing_engine,
    prepare_pricing_input,
    tool_guardrail_pricing,
    validate_financial_sanity,
)
from src.agents.official_quote.nodes.ranking import rank_scenarios

# Authoritative 23-node registry
NODE_REGISTRY = {
    # Phase 1: Input & Context
    "validate_input": validate_input,
    "security_guardrail_input": security_guardrail_input,
    "load_transaction_context": load_transaction_context,
    # Phase 2: Policy Retrieval & Evaluation
    "retrieve_active_policies": retrieve_active_policies,
    "security_guardrail_policy": security_guardrail_policy,
    "evaluate_policy_clauses": evaluate_policy_clauses,
    "detect_conflicts": detect_conflicts,
    "safe_abstention_gate": safe_abstention_gate,
    # Phase 3: Pricing & Sanity
    "prepare_pricing_input": prepare_pricing_input,
    "tool_guardrail_pricing": tool_guardrail_pricing,
    "call_pricing_engine": call_pricing_engine,
    "validate_financial_sanity": validate_financial_sanity,
    # Phase 4: Ranking & Explanation
    "rank_scenarios": rank_scenarios,
    "generate_explanations": generate_explanations,
    "security_guardrail_output": security_guardrail_output,
    "verify_claim_evidence": verify_claim_evidence,
    # Phase 5: Governance & Approval
    "assemble_approval_package": assemble_approval_package,
    "await_manager_approval": await_manager_approval,
    "evaluate_revision_request": evaluate_revision_request,
    "evaluate_exception_approval": evaluate_exception_approval,
    "freeze_audit_hash": freeze_audit_hash,
    "request_kms_attestation": request_kms_attestation,
    "commit_quote_transaction": commit_quote_transaction,
}

__all__ = [
    "NODE_REGISTRY",
    "validate_input",
    "security_guardrail_input",
    "load_transaction_context",
    "retrieve_active_policies",
    "security_guardrail_policy",
    "evaluate_policy_clauses",
    "detect_conflicts",
    "safe_abstention_gate",
    "prepare_pricing_input",
    "tool_guardrail_pricing",
    "call_pricing_engine",
    "validate_financial_sanity",
    "rank_scenarios",
    "generate_explanations",
    "security_guardrail_output",
    "verify_claim_evidence",
    "assemble_approval_package",
    "await_manager_approval",
    "evaluate_revision_request",
    "evaluate_exception_approval",
    "freeze_audit_hash",
    "request_kms_attestation",
    "commit_quote_transaction",
    "compute_final_audit_hash",
]
