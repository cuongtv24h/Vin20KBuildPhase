"""Registry node của Pre-Sales StateGraph."""

from src.agents.pre_sales.nodes.constraints import (
    confirm_constraints_node,
    extract_constraints_node,
)
from src.agents.pre_sales.nodes.discovery import discovery_node
from src.agents.pre_sales.nodes.handoff import consent_and_handoff_node
from src.agents.pre_sales.nodes.planning import build_reference_plan_node

PRE_SALES_NODE_REGISTRY: dict[str, object] = {
    "F1_DISCOVERY": discovery_node,
    "F2_EXTRACT_CONSTRAINTS": extract_constraints_node,
    "F2_CONFIRM_CONSTRAINTS": confirm_constraints_node,
    "F3_F5_BUILD_REFERENCE_PLAN": build_reference_plan_node,
    "F6_F7_CONSENT_HANDOFF": consent_and_handoff_node,
}

__all__ = ["PRE_SALES_NODE_REGISTRY"]
