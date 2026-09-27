"""
Pricing Service Package
Owner: TechLead (cuongtv_02560)
Provides PricingClient bridge connecting to UDS Sidecar with deterministic in-process fallback,
FCS v2.6 6-sanity check validation, and ADR-021 6-objective ranking.
"""

from src.services.pricing.client import PricingCalculationError, PricingClient
from src.services.pricing.ranking import rank_scenarios_by_objective
from src.services.pricing.validation import (
    SanityValidationError,
    validate_pricing_result_sanity,
    validate_scenario_sanity,
)

__all__ = [
    "PricingClient",
    "PricingCalculationError",
    "SanityValidationError",
    "validate_pricing_result_sanity",
    "validate_scenario_sanity",
    "rank_scenarios_by_objective",
]
