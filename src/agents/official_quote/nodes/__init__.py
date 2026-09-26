"""Registry 23 node của Official Quote StateGraph (N-01 → N-20, gồm biến thể A/B).

`NODE_REGISTRY` là hợp đồng đặt tên node — test cấu trúc
(`tests/test_agents/official_quote/test_nodes_registry.py`) khóa số lượng và
tên node để chống trôi khi dựng graph.
"""

from collections.abc import Callable

from src.agents.official_quote.nodes.approval import (
    build_approval_package,
    commit_atomic_transaction,
    create_exception_version,
    create_new_quote_revision,
    freeze_approval_intent,
    interrupt_human_review,
    request_server_attestation,
)
from src.agents.official_quote.nodes.context import load_transaction_context
from src.agents.official_quote.nodes.evaluation import (
    detect_policy_conflicts,
    evaluate_policy_clauses,
    safe_decision_gate,
)
from src.agents.official_quote.nodes.explanation import (
    generate_explanation,
    security_guardrail_output,
    validate_explanation,
)
from src.agents.official_quote.nodes.input_guards import (
    security_guardrail_input,
    validate_input,
)
from src.agents.official_quote.nodes.policy_retrieval import (
    retrieve_active_policies,
    security_guardrail_content,
)
from src.agents.official_quote.nodes.pricing import (
    build_pricing_input,
    calculate_scenarios,
    security_guardrail_tool,
    validate_calculation,
)
from src.agents.official_quote.nodes.ranking import rank_scenarios

NODE_REGISTRY: dict[str, Callable[..., object]] = {
    "N-01": validate_input,
    "N-02": security_guardrail_input,
    "N-03": load_transaction_context,
    "N-04": retrieve_active_policies,
    "N-05": security_guardrail_content,
    "N-06": evaluate_policy_clauses,
    "N-07": detect_policy_conflicts,
    "N-08": safe_decision_gate,
    "N-09": build_pricing_input,
    "N-10A": security_guardrail_tool,
    "N-10B": calculate_scenarios,
    "N-11": validate_calculation,
    "N-12": rank_scenarios,
    "N-13": generate_explanation,
    "N-14A": security_guardrail_output,
    "N-14B": validate_explanation,
    "N-15": build_approval_package,
    "N-16": interrupt_human_review,
    "N-17": create_new_quote_revision,
    "N-18": create_exception_version,
    "N-19A": freeze_approval_intent,
    "N-19B": request_server_attestation,
    "N-20": commit_atomic_transaction,
}

__all__ = ["NODE_REGISTRY"]
