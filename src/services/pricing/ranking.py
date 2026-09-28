"""
Scenario Ranking Module (ADR-021 Canonical 6-Objective & Tie-Break Engine)
Owner: TechLead (cuongtv_02560)
Component: C-06 / C-01
"""

from __future__ import annotations

from typing import Any

from src.contracts.enums import OptimizationObjective
from src.contracts.pricing import ScenarioCode, ScenarioDetail
from src.pricing_sidecar.arithmetic import format_vnd
from src.pricing_sidecar.contracts import (
    OptimizationObjective as SidecarObjective,
)
from src.pricing_sidecar.contracts import (
    RecommendationResult,
)
from src.pricing_sidecar.engine import resolve_scenario_type


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


def rank_and_recommend(
    scenarios: dict[str, ScenarioDetail],
    objective: OptimizationObjective,
    tie_break_rule: str = "TB-RULE-2026-CHUDONG-V1",
) -> RecommendationResult:
    """
    Ranks scenarios against the objective, applies 3-tier tie-breaking,
    and returns RecommendationResult with quantitative rationale conforming to TD-4.3 & ADR-021.
    """
    recommended_code, ranking_summary = rank_scenarios_by_objective(
        scenarios=scenarios,
        objective=objective,
        tie_break_rule=tie_break_rule,
    )

    sidecar_obj = SidecarObjective(objective.value)
    scenario_type = resolve_scenario_type(recommended_code.value)

    recommended_sc = scenarios[recommended_code.value]
    others = [s for k, s in scenarios.items() if k != recommended_code.value]

    metric_names = {
        OptimizationObjective.MIN_NET_PRICE: ("Giá thuần", "net_price_vnd", "VNĐ"),
        OptimizationObjective.MIN_INITIAL_CASH: ("Vốn ban đầu", "initial_cash_outflow_vnd", "VNĐ"),
        OptimizationObjective.MIN_MONTHLY_BURDEN: ("Áp lực trả hàng tháng", "monthly_burden_vnd", "VNĐ/tháng"),
        OptimizationObjective.MIN_TOTAL_CASH_OUTFLOW: ("Tổng dòng tiền ra", "total_cash_outflow_vnd", "VNĐ"),
        OptimizationObjective.MAX_BENEFIT_VALUE: ("Giá trị ưu đãi", "benefit_value_vnd", "VNĐ"),
        OptimizationObjective.EARLY_HANDOVER: ("Thời gian nhận nhà", "early_days", "ngày"),
    }
    label, attr, unit = metric_names.get(objective, ("Chỉ số", "net_price_vnd", "VNĐ"))
    rec_val = getattr(recommended_sc, attr, 0)
    rec_val_str = f"{format_vnd(rec_val)}/tháng" if unit == "VNĐ/tháng" else (f"{format_vnd(rec_val)}" if unit == "VNĐ" else f"{rec_val} {unit}")

    comparisons = []
    for other in others:
        other_val = getattr(other, attr, 0)
        val_str = f"{format_vnd(other_val)}/tháng" if unit == "VNĐ/tháng" else (f"{format_vnd(other_val)}" if unit == "VNĐ" else f"{other_val} {unit}")
        comparisons.append(f"tối ưu hơn {other.scenario_name} ({val_str})")

    rationale = (
        f"Phương án {recommended_sc.scenario_name} ({recommended_sc.scenario_code.value}) là lựa chọn tối ưu nhất "
        f"theo mục tiêu {objective.value} ({label}: {rec_val_str}). "
        f"So sánh với các phương án còn lại: {'; '.join(comparisons)}."
    )

    return RecommendationResult(
        selected_objective=sidecar_obj,
        recommended_scenario=scenario_type,
        comparison_summary=ranking_summary,
        quantitative_rationale=rationale,
        is_tie_break_applied=len(ranking_summary) > 1,
        tiebreak_rule_id=tie_break_rule,
    )


