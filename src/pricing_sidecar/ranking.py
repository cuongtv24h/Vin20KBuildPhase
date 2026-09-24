"""Deterministic Scenario Ranking & Recommendation Engine.

FCS v2.6 Reference: Section 7 (Giải thuật Xếp hạng Tối ưu & Tie-Break)
TD-4.4 Reference: Section 4.1 (Tool Contract rank_scenarios_by_objective)
Implement Plan Detail Reference: Section 7.4 (D2-4 Ranking và Objective)
"""

from collections.abc import Sequence
from typing import Any

from src.pricing_sidecar.arithmetic import (
    assert_no_float,
    forbid_float,
    format_vnd,
)
from src.pricing_sidecar.contracts import (
    CANONICAL_SCENARIO_ORDER,
    OptimizationObjective,
    RecommendationResult,
    ScenarioCalculationResult,
    ScenarioType,
)
from src.pricing_sidecar.engine import resolve_scenario_type

# ---------------------------------------------------------------------------
# Tie-Break Rule Identifiers (Task 3.4 / FCS §7.2)
# ---------------------------------------------------------------------------
TIEBREAK_RULE_CONTRACT_PRICE: str = "TIEBREAK-CONTRACT-PRICE-v1"
TIEBREAK_RULE_CANONICAL_ORDER: str = "TIEBREAK-CANONICAL-ORDER-v1"

OBJECTIVE_LABELS: dict[OptimizationObjective, str] = {
    OptimizationObjective.MIN_NET_PRICE: "Giá Net trước thuế thấp nhất (MIN_NET_PRICE)",
    OptimizationObjective.MIN_CONTRACT_PRICE: "Tổng Giá trị HĐMB thấp nhất (MIN_CONTRACT_PRICE)",
    OptimizationObjective.MIN_INITIAL_OUTFLOW: "Dòng tiền ban đầu Đợt 1 thấp nhất (MIN_INITIAL_OUTFLOW)",
    OptimizationObjective.MIN_CASH_OUTFLOW_TO_HANDOVER: "Tổng vốn tự có nộp đến nhận bàn giao thấp nhất (MIN_CASH_OUTFLOW_TO_HANDOVER)",
    OptimizationObjective.MAX_BENEFIT_VALUE: "Tổng giá trị ưu đãi nhận được cao nhất (MAX_BENEFIT_VALUE)",
}

OBJECTIVE_METRIC_NAMES: dict[OptimizationObjective, str] = {
    OptimizationObjective.MIN_NET_PRICE: "Giá Net trước thuế",
    OptimizationObjective.MIN_CONTRACT_PRICE: "Tổng Giá trị HĐMB",
    OptimizationObjective.MIN_INITIAL_OUTFLOW: "Dòng tiền ban đầu Đợt 1",
    OptimizationObjective.MIN_CASH_OUTFLOW_TO_HANDOVER: "Vốn tự có nộp đến bàn giao",
    OptimizationObjective.MAX_BENEFIT_VALUE: "Tổng giá trị ưu đãi",
}


# ---------------------------------------------------------------------------
# Specialized Exception for Feasibility Handling (Task 3.5)
# ---------------------------------------------------------------------------
class NoFeasibleScenarioError(ValueError):
    """Ngoại lệ phát sinh khi toàn bộ các kịch bản đều không khả thi (infeasible)."""

    pass


# ---------------------------------------------------------------------------
# Metric Value Extraction Helper (Task 3.3)
# ---------------------------------------------------------------------------
def get_objective_metric_value(
    scenario: ScenarioCalculationResult,
    objective: OptimizationObjective,
) -> int:
    """Trích xuất chỉ số tài chính nguyên VNĐ tương ứng với hàm mục tiêu kinh doanh.

    Args:
        scenario: Kết quả tính toán kịch bản tài chính.
        objective: Hàm mục tiêu kinh doanh PRD v2.3 / FCS v2.6 §7.

    Returns:
        int: Giá trị tiền tệ nguyên VNĐ của chỉ số mục tiêu.
    """
    assert_no_float(scenario, objective)
    if objective == OptimizationObjective.MIN_NET_PRICE:
        return scenario.net_price_before_vat
    elif objective == OptimizationObjective.MIN_CONTRACT_PRICE:
        return scenario.final_contract_price
    elif objective == OptimizationObjective.MIN_INITIAL_OUTFLOW:
        return scenario.initial_cash_outflow_vnd
    elif objective == OptimizationObjective.MIN_CASH_OUTFLOW_TO_HANDOVER:
        return scenario.customer_cash_outflow_until_handover
    elif objective == OptimizationObjective.MAX_BENEFIT_VALUE:
        return scenario.total_benefit_value_vnd
    else:
        raise ValueError(f"UNSUPPORTED_OBJECTIVE: Mục tiêu '{objective}' không được hỗ trợ.")


def _parse_infeasible_set(
    infeasible_scenarios: Sequence[ScenarioType | str] | None,
) -> set[ScenarioType]:
    """Chuẩn hóa danh sách kịch bản không khả thi thành set các ScenarioType."""
    if not infeasible_scenarios:
        return set()
    result: set[ScenarioType] = set()
    for item in infeasible_scenarios:
        if isinstance(item, ScenarioType):
            result.add(item)
        elif isinstance(item, str):
            result.add(resolve_scenario_type(item))
        else:
            raise TypeError(
                f"FLOAT_PROHIBITED: Kiểu dữ liệu không hợp lệ trong infeasible_scenarios: {type(item)}"
            )
    return result


# ---------------------------------------------------------------------------
# Core Scenario Ranking Function (Task 3.3 & 3.4)
# ---------------------------------------------------------------------------
@forbid_float
def rank_scenarios_by_objective(
    scenarios: Sequence[ScenarioCalculationResult],
    objective: OptimizationObjective,
    infeasible_scenarios: Sequence[ScenarioType | str] | None = None,
) -> list[ScenarioCalculationResult]:
    """Xếp hạng các kịch bản tài chính theo mục tiêu kinh doanh và cơ chế Tie-Break tất định.

    Áp dụng thuật toán 3 tầng:
    - Tầng 1 (Primary Metric): Giá trị của objective được chọn.
    - Tầng 2 (Secondary Tie-Break): final_contract_price (tổng giá HĐMB thấp hơn ưu tiên trước).
    - Tầng 3 (Tertiary Canonical Tie-Break): canonical_scenario_order (STANDARD_PROGRESS: 1 -> EARLY_95: 2 -> BANK_LOAN_HTLS: 3).

    Các kịch bản infeasible được tự động xếp cuối cùng danh sách.

    Args:
        scenarios: Danh sách các kịch bản đã tính toán.
        objective: Hàm mục tiêu tối ưu kinh doanh.
        infeasible_scenarios: Danh sách mã hoặc enum kịch bản không khả thi (tùy chọn).

    Returns:
        list[ScenarioCalculationResult]: Danh sách các kịch bản đã được sắp xếp từ tối ưu nhất đến kém nhất.
    """
    assert_no_float(scenarios, objective, infeasible_scenarios)
    if not scenarios:
        return []

    infeasible_set = _parse_infeasible_set(infeasible_scenarios)

    def sort_key(s: ScenarioCalculationResult) -> tuple[int, int, int, int]:
        # Kịch bản infeasible xếp sau: is_infeasible (0 = feasible, 1 = infeasible)
        is_infeasible = 1 if s.scenario_type in infeasible_set else 0
        canonical_rank = CANONICAL_SCENARIO_ORDER.get(s.scenario_type, 99)

        if objective == OptimizationObjective.MAX_BENEFIT_VALUE:
            # Tối đa hóa giá trị: số âm lớn nhất sẽ đứng đầu
            primary_val = -s.total_benefit_value_vnd
            secondary_val = s.final_contract_price
            return (is_infeasible, primary_val, secondary_val, canonical_rank)
        elif objective == OptimizationObjective.MIN_NET_PRICE:
            primary_val = s.net_price_before_vat
            secondary_val = s.final_contract_price
            return (is_infeasible, primary_val, secondary_val, canonical_rank)
        elif objective == OptimizationObjective.MIN_CONTRACT_PRICE:
            primary_val = s.final_contract_price
            secondary_val = s.net_price_before_vat
            return (is_infeasible, primary_val, secondary_val, canonical_rank)
        elif objective == OptimizationObjective.MIN_INITIAL_OUTFLOW:
            primary_val = s.initial_cash_outflow_vnd
            secondary_val = s.final_contract_price
            return (is_infeasible, primary_val, secondary_val, canonical_rank)
        elif objective == OptimizationObjective.MIN_CASH_OUTFLOW_TO_HANDOVER:
            primary_val = s.customer_cash_outflow_until_handover
            secondary_val = s.final_contract_price
            return (is_infeasible, primary_val, secondary_val, canonical_rank)
        else:
            raise ValueError(f"UNSUPPORTED_OBJECTIVE: Mục tiêu '{objective}' không được hỗ trợ.")

    return sorted(scenarios, key=sort_key)


# ---------------------------------------------------------------------------
# Quantitative Rationale Generator (Task 3.5)
# ---------------------------------------------------------------------------
def generate_quantitative_rationale(
    recommended: ScenarioCalculationResult,
    other_scenarios: Sequence[ScenarioCalculationResult],
    objective: OptimizationObjective,
    is_tie_break_applied: bool = False,
    tie_break_reason: str | None = None,
) -> str:
    """Sinh lời giải trình định lượng so sánh chi tiết số tiền chênh lệch VNĐ theo FCS §7."""
    assert_no_float(recommended, other_scenarios, objective, is_tie_break_applied, tie_break_reason)
    rec_type_code = recommended.scenario_type.canonical_code
    rec_val = get_objective_metric_value(recommended, objective)
    metric_label = OBJECTIVE_METRIC_NAMES.get(objective, objective.value)
    rec_val_str = format_vnd(rec_val)

    rationale_parts: list[str] = [
        f"Phương án {recommended.scenario_name} ({rec_type_code}) là lựa chọn tối ưu nhất "
        f"theo mục tiêu {OBJECTIVE_LABELS.get(objective, objective.value)}, "
        f"đạt chỉ số {metric_label} là {rec_val_str}."
    ]

    comparisons: list[str] = []
    for other in other_scenarios:
        other_code = other.scenario_type.canonical_code
        other_val = get_objective_metric_value(other, objective)
        other_val_str = format_vnd(other_val)

        if objective == OptimizationObjective.MAX_BENEFIT_VALUE:
            diff_vnd = rec_val - other_val
            if diff_vnd > 0:
                comparisons.append(
                    f"vượt trội hơn {other_code} ({other_val_str}) là {format_vnd(diff_vnd)}"
                )
            elif diff_vnd == 0:
                comparisons.append(f"ngang bằng với {other_code} ({other_val_str})")
            else:
                comparisons.append(f"kém hơn {other_code} ({other_val_str})")
        else:
            # Các mục tiêu tối thiểu hóa chi phí (MIN_*)
            diff_vnd = other_val - rec_val
            if diff_vnd > 0:
                pct_diff = (diff_vnd / other_val * 100) if other_val > 0 else 0
                comparisons.append(
                    f"tiết kiệm {format_vnd(diff_vnd)} (-{pct_diff:.2f}%) so với {other_code} ({other_val_str})"
                )
            elif diff_vnd == 0:
                comparisons.append(f"tương đương về {metric_label} với {other_code} ({other_val_str})")
            else:
                comparisons.append(f"cao hơn {other_code} ({other_val_str})")

    if comparisons:
        rationale_parts.append("Đối chiếu chi tiết: " + "; ".join(comparisons) + ".")

    if is_tie_break_applied and tie_break_reason:
        rationale_parts.append(f"Ghi chú phân định hòa: {tie_break_reason}")

    return " ".join(rationale_parts)


# ---------------------------------------------------------------------------
# High-Level Recommendation Function (Task 3.3, 3.4, 3.5)
# ---------------------------------------------------------------------------
@forbid_float
def recommend_best_scenario(
    scenarios: Sequence[ScenarioCalculationResult],
    objective: OptimizationObjective = OptimizationObjective.MIN_NET_PRICE,
    infeasible_scenarios: Sequence[ScenarioType | str] | None = None,
) -> RecommendationResult:
    """Thực thi toàn bộ quy trình xếp hạng, phân định hòa và kết xuất RecommendationResult.

    Conforming to Tool Contract TD-4.4 `rank_scenarios_by_objective`.

    Args:
        scenarios: Danh sách các kịch bản tài chính cần đánh giá.
        objective: Hàm mục tiêu tối ưu kinh doanh (mặc định MIN_NET_PRICE).
        infeasible_scenarios: Danh sách các kịch bản bị loại trừ khỏi khuyến nghị.

    Returns:
        RecommendationResult: Kết quả khuyến nghị phương án tối ưu, kèm so sánh định lượng và lý giải.

    Raises:
        ValueError: Nếu danh sách scenarios rỗng.
        NoFeasibleScenarioError: Nếu 100% kịch bản đều infeasible.
    """
    assert_no_float(scenarios, objective, infeasible_scenarios)
    if not scenarios:
        raise ValueError("Danh sách kịch bản scenarios không được rỗng để thực hiện xếp hạng.")

    infeasible_set = _parse_infeasible_set(infeasible_scenarios)
    ranked = rank_scenarios_by_objective(
        scenarios=scenarios,
        objective=objective,
        infeasible_scenarios=infeasible_scenarios,
    )

    # Lọc danh sách khả thi
    feasible_ranked = [s for s in ranked if s.scenario_type not in infeasible_set]
    if not feasible_ranked:
        raise NoFeasibleScenarioError(
            f"NO_FEASIBLE_SCENARIO: Toàn bộ {len(scenarios)} kịch bản tính toán đều nằm trong danh sách không khả thi."
        )

    winner = feasible_ranked[0]
    is_tie_break_applied = False
    tiebreak_rule_id: str | None = None
    tie_break_reason: str | None = None

    # Kiểm tra phân định hòa giữa kịch bản hạng 1 và hạng 2 khả thi
    if len(feasible_ranked) >= 2:
        runner_up = feasible_ranked[1]
        winner_val = get_objective_metric_value(winner, objective)
        runner_up_val = get_objective_metric_value(runner_up, objective)

        if winner_val == runner_up_val:
            is_tie_break_applied = True
            # Kiểm tra xem hòa được phân định ở Tầng 2 hay Tầng 3
            if winner.final_contract_price != runner_up.final_contract_price:
                tiebreak_rule_id = TIEBREAK_RULE_CONTRACT_PRICE
                tie_break_reason = (
                    f"Cả hai phương án {winner.scenario_type.canonical_code} và "
                    f"{runner_up.scenario_type.canonical_code} đều đạt chỉ số mục tiêu {winner_val:,} VNĐ. "
                    f"Áp dụng quy tắc {TIEBREAK_RULE_CONTRACT_PRICE}: "
                    f"{winner.scenario_type.canonical_code} được ưu tiên do có Tổng giá HĐMB thấp hơn "
                    f"({format_vnd(winner.final_contract_price)} so với {format_vnd(runner_up.final_contract_price)})."
                )
            else:
                tiebreak_rule_id = TIEBREAK_RULE_CANONICAL_ORDER
                tie_break_reason = (
                    f"Cả hai phương án {winner.scenario_type.canonical_code} và "
                    f"{runner_up.scenario_type.canonical_code} đều cùng chỉ số mục tiêu ({winner_val:,} VNĐ) "
                    f"và cùng Tổng giá HĐMB ({format_vnd(winner.final_contract_price)}). "
                    f"Áp dụng quy tắc {TIEBREAK_RULE_CANONICAL_ORDER}: "
                    f"{winner.scenario_type.canonical_code} được ưu tiên theo thứ tự chuẩn tắc canonical."
                )

    # Tạo bảng comparison_summary
    comparison_summary: list[dict[str, Any]] = []
    for rank_idx, s in enumerate(ranked, start=1):
        is_feas = s.scenario_type not in infeasible_set
        comparison_summary.append({
            "rank": rank_idx,
            "scenario_type": s.scenario_type.value,
            "canonical_code": s.scenario_type.canonical_code,
            "scenario_name": s.scenario_name,
            "net_price_vnd": s.net_price_before_vat,
            "contract_price_vnd": s.final_contract_price,
            "initial_cash_outflow_vnd": s.initial_cash_outflow_vnd,
            "cash_outflow_to_handover_vnd": s.customer_cash_outflow_until_handover,
            "total_benefit_value_vnd": s.total_benefit_value_vnd,
            "target_metric_value_vnd": get_objective_metric_value(s, objective),
            "is_feasible": is_feas,
            "is_recommended": (s.scenario_type == winner.scenario_type),
        })

    # Tạo quantitative rationale
    other_feasible = [s for s in feasible_ranked if s.scenario_type != winner.scenario_type]
    rationale = generate_quantitative_rationale(
        recommended=winner,
        other_scenarios=other_feasible,
        objective=objective,
        is_tie_break_applied=is_tie_break_applied,
        tie_break_reason=tie_break_reason,
    )

    return RecommendationResult(
        selected_objective=objective,
        recommended_scenario=winner.scenario_type,
        comparison_summary=comparison_summary,
        quantitative_rationale=rationale,
        is_tie_break_applied=is_tie_break_applied,
        tiebreak_rule_id=tiebreak_rule_id,
        tie_break_reason=tie_break_reason,
    )
