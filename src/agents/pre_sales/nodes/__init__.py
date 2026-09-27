"""Pre-Sales advisory nodes (PS-01 → PS-11). Owner: Phase 2 (C-09)."""

from src.agents.pre_sales.nodes.constraints import (
    node_extract_constraints,
    node_validate_confirm_constraints,
)
from src.agents.pre_sales.nodes.discovery import node_collect_input, node_init
from src.agents.pre_sales.nodes.handoff import (
    node_await_handoff_consent,
    node_safe_abstain_or_handoff,
)
from src.agents.pre_sales.nodes.planning import (
    node_build_reference_plan,
    node_calculate_sidecar,
    node_conflict_gate,
    node_rank_objectives,
    node_resolve_policy,
)

# Khóa 11 mã node chuẩn theo spec Phase 2 trong mydoc/Excute.md
NODE_REGISTRY: dict[str, str] = {
    "PS-01": "init",
    "PS-02": "collect_input",
    "PS-03": "extract_constraints",
    "PS-04": "validate_confirm_constraints",
    "PS-05": "resolve_policy",
    "PS-06": "conflict_gate",
    "PS-07": "calculate_sidecar",
    "PS-08": "rank_objectives",
    "PS-09": "build_reference_plan",
    "PS-10": "await_handoff_consent",
    "PS-11": "safe_abstain_or_handoff",
}

__all__ = [
    "NODE_REGISTRY",
    "node_await_handoff_consent",
    "node_build_reference_plan",
    "node_calculate_sidecar",
    "node_collect_input",
    "node_conflict_gate",
    "node_extract_constraints",
    "node_init",
    "node_rank_objectives",
    "node_resolve_policy",
    "node_safe_abstain_or_handoff",
    "node_validate_confirm_constraints",
]
