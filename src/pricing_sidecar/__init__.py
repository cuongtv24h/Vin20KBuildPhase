"""Pricing Engine Sidecar package.

Pure deterministic financial math engine conforming to FCS v2.6.
"""

from src.pricing_sidecar.arithmetic import (
    PRECISION,
    ROUNDING_RULE,
    assert_no_float,
    forbid_float,
    format_vnd,
    round_vnd,
    safe_rate_amount,
    sum_rates,
    to_decimal,
)
from src.pricing_sidecar.contracts import (
    CANONICAL_SCENARIO_ORDER,
    SCENARIO_ALIAS_MAP,
    VALID_BENEFIT_MAPPING,
    BenefitCategory,
    BenefitType,
    CalculationBase,
    CalculationStatus,
    OptimizationObjective,
    PolicyDecisionStatus,
    QuoteWorkflowStatus,
    ScenarioType,
    ValuationStatus,
)

__all__ = [
    "CANONICAL_SCENARIO_ORDER",
    "PRECISION",
    "ROUNDING_RULE",
    "SCENARIO_ALIAS_MAP",
    "VALID_BENEFIT_MAPPING",
    "BenefitCategory",
    "BenefitType",
    "CalculationBase",
    "CalculationStatus",
    "OptimizationObjective",
    "PolicyDecisionStatus",
    "QuoteWorkflowStatus",
    "ScenarioType",
    "ValuationStatus",
    "assert_no_float",
    "forbid_float",
    "format_vnd",
    "round_vnd",
    "safe_rate_amount",
    "sum_rates",
    "to_decimal",
]
