"""
Pricing Service Package
Owner: TechLead (cuongtv_02560)
Provides PricingClient bridge connecting to UDS Sidecar with deterministic in-process fallback,
FCS v2.6 6-sanity check validation, and ADR-021 6-objective ranking.
"""

from src.services.pricing.client import (
    PricingCalculationError,
    PricingClient,
    get_pricing_client,
)
from src.services.pricing.optimizer import (
    filter_feasible_scenarios,
    generate_reference_plans,
)
from src.services.pricing.ranking import (
    rank_and_recommend,
    rank_scenarios_by_objective,
)
from src.services.pricing.validation import (
    SanityValidationError,
    run_financial_sanity_gate,
    validate_pricing_result_sanity,
    validate_scenario_sanity,
)

__all__ = [
    "PricingClient",
    "get_pricing_client",
    "PricingCalculationError",
    "SanityValidationError",
    "validate_pricing_result_sanity",
    "validate_scenario_sanity",
    "run_financial_sanity_gate",
    "rank_scenarios_by_objective",
    "rank_and_recommend",
    "generate_reference_plans",
    "filter_feasible_scenarios",
]

