"""
Scenario Ranking Node (N-12)
Owner: TechLead (cuongtv_02560)
"""

from __future__ import annotations

from src.agents.official_quote.state import OfficialQuoteState
from src.contracts.enums import OptimizationObjective
from src.contracts.pricing import PricingResult
from src.services.pricing import rank_scenarios_by_objective


def rank_scenarios(state: OfficialQuoteState) -> dict:
    """
    N-12: Rank calculated financial scenarios against the selected optimization objective.
    Applies deterministic tie-breaking (TB-RULE-2026-CHUDONG-V1).
    """
    raw_res = state.get("pricing_result") or {}
    result = PricingResult(**raw_res)

    objective = state.get("objective", OptimizationObjective.MIN_INITIAL_CASH)
    scenarios = result.scenarios

    recommended_code, ranking_summary = rank_scenarios_by_objective(
        scenarios=scenarios,
        objective=objective,
    )

    return {
        "recommended_scenario_code": recommended_code.value,
        "ranking_summary": ranking_summary,
    }
