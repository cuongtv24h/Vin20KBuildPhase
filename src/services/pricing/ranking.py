"""
Scenario Ranking Module (ADR-021 Canonical 6-Objective & Tie-Break Engine)
Owner: TechLead (cuongtv_02560)
Component: C-06 / C-01
"""

from __future__ import annotations

from typing import Any

from src.contracts.enums import OptimizationObjective
from src.contracts.pricing import ScenarioCode, ScenarioDetail


def rank_scenarios_by_objective(
    scenarios: dict[str, ScenarioDetail],
    objective: OptimizationObjective,
    tie_break_rule: str = "TB-RULE-2026-CHUDONG-V1",
) -> tuple[ScenarioCode, list[dict[str, Any]]]:
    """
    Ranks scenarios based on one of the 6 canonical optimization objectives.
    Applies deterministic tie-breaking (TB-RULE-2026-CHUDONG-V1).
    Returns (recommended_scenario_code, ranking_summary_list).
    """
    if not scenarios:
        raise ValueError("Cannot rank an empty scenario set.")

    items = list(scenarios.values())

    # Preference priority for tie-breaking: PA_CHUDONG (0) > PA_NHANH (1) > PA_VAY (2)
    def tie_break_order(sc: ScenarioDetail) -> int:
        order = {
            ScenarioCode.PA_CHUDONG: 0,
            ScenarioCode.PA_NHANH: 1,
            ScenarioCode.PA_VAY: 2,
        }
        return order.get(sc.scenario_code, 99)

    if objective == OptimizationObjective.MIN_NET_PRICE:
        sorted_scenarios = sorted(
            items, key=lambda s: (s.net_price_vnd, tie_break_order(s))
        )
    elif objective == OptimizationObjective.MIN_INITIAL_CASH:
        sorted_scenarios = sorted(
            items, key=lambda s: (s.initial_cash_outflow_vnd, tie_break_order(s))
        )
    elif objective == OptimizationObjective.MIN_MONTHLY_BURDEN:
        sorted_scenarios = sorted(
            items, key=lambda s: (s.monthly_burden_vnd, tie_break_order(s))
        )
    elif objective == OptimizationObjective.MIN_TOTAL_CASH_OUTFLOW:
        sorted_scenarios = sorted(
            items, key=lambda s: (s.total_cash_outflow_vnd, tie_break_order(s))
        )
    elif objective == OptimizationObjective.MAX_BENEFIT_VALUE:
        sorted_scenarios = sorted(
            items, key=lambda s: (-s.benefit_value_vnd, tie_break_order(s))
        )
    elif objective == OptimizationObjective.EARLY_HANDOVER:
        # Standard progress takes priority for scheduled handover
        sorted_scenarios = sorted(
            items, key=lambda s: (tie_break_order(s), s.total_contract_price_vnd)
        )
    else:
        sorted_scenarios = sorted(items, key=tie_break_order)

    recommended = sorted_scenarios[0].scenario_code

    ranking_summary: list[dict[str, Any]] = []
    for rank, sc in enumerate(sorted_scenarios, start=1):
        ranking_summary.append({
            "rank": rank,
            "scenario_code": sc.scenario_code.value,
            "scenario_name": sc.scenario_name,
            "total_contract_price_vnd": sc.total_contract_price_vnd,
            "net_price_vnd": sc.net_price_vnd,
            "initial_cash_outflow_vnd": sc.initial_cash_outflow_vnd,
            "monthly_burden_vnd": sc.monthly_burden_vnd,
            "total_cash_outflow_vnd": sc.total_cash_outflow_vnd,
            "benefit_value_vnd": sc.benefit_value_vnd,
            "is_feasible": sc.is_feasible,
            "tie_break_rule": tie_break_rule,
        })

    return recommended, ranking_summary
