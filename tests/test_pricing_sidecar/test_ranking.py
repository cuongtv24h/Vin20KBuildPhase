"""Unit tests for Deterministic Ranking, Tie-Break, and Recommendation Engine (Tasks 3.3, 3.4, 3.5).

Conforming to FCS v2.6 §7, TD-4.4 §4.1, and Implement Plan Detail §7.4.
"""

import time
from datetime import date

import pytest

from src.pricing_sidecar.contracts import (
    OptimizationObjective,
    ScenarioCalculationResult,
    ScenarioType,
)
from src.pricing_sidecar.engine import (
    calculate_pa_chudong,
    calculate_pa_nhanh,
    calculate_pa_vay,
)
from src.pricing_sidecar.ranking import (
    TIEBREAK_RULE_CANONICAL_ORDER,
    TIEBREAK_RULE_CONTRACT_PRICE,
    NoFeasibleScenarioError,
    get_objective_metric_value,
    rank_scenarios_by_objective,
    recommend_best_scenario,
)


@pytest.fixture
def canonical_chudong() -> ScenarioCalculationResult:
    """Fixture PA-CHUDONG (3.5B, Net 3.5B, Contract 3.92B, Initial 577.5M, Handover 3.724B)."""
    return calculate_pa_chudong(
        listed_price_vnd=3_500_000_000,
        deposit_date=date(2026, 3, 15),
        deposit_amount_vnd=100_000_000,
    )


@pytest.fixture
def canonical_nhanh() -> ScenarioCalculationResult:
    """Fixture PA-NHANH (3.5B, Net 3.22B, Contract 3.6064B, Initial 3.3649B, Handover 3.6064B)."""
    return calculate_pa_nhanh(
        listed_price_vnd=3_500_000_000,
        deposit_date=date(2026, 3, 15),
        deposit_amount_vnd=100_000_000,
    )


@pytest.fixture
def canonical_vay() -> ScenarioCalculationResult:
    """Fixture PA-VAY (3.5B, Net 3.5B, Contract 3.92B, Initial 577.5M, Handover 1.246B)."""
    return calculate_pa_vay(
        listed_price_vnd=3_500_000_000,
        deposit_date=date(2026, 3, 15),
        deposit_amount_vnd=100_000_000,
    )


@pytest.fixture
def standard_canonical_suite(
    canonical_chudong: ScenarioCalculationResult,
    canonical_nhanh: ScenarioCalculationResult,
    canonical_vay: ScenarioCalculationResult,
) -> list[ScenarioCalculationResult]:
    """Suite containing all 3 canonical scenarios for apartment A-12-05."""
    return [canonical_chudong, canonical_nhanh, canonical_vay]


# ===========================================================================
# 1. Tests for 5 Business Objectives (Task 3.3)
# ===========================================================================
class TestObjectiveRanking:
    """Verify deterministic ranking for all 5 business optimization objectives."""

    def test_rank_min_net_price(self, standard_canonical_suite: list[ScenarioCalculationResult]) -> None:
        result = recommend_best_scenario(
            scenarios=standard_canonical_suite,
            objective=OptimizationObjective.MIN_NET_PRICE,
        )
        assert result.recommended_scenario == ScenarioType.EARLY_95
        assert result.selected_objective == OptimizationObjective.MIN_NET_PRICE

        ranked = rank_scenarios_by_objective(standard_canonical_suite, OptimizationObjective.MIN_NET_PRICE)
        assert ranked[0].scenario_type == ScenarioType.EARLY_95
        assert ranked[0].net_price_before_vat == 3_220_000_000
        assert ranked[1].scenario_type == ScenarioType.STANDARD_PROGRESS
        assert ranked[2].scenario_type == ScenarioType.BANK_LOAN_HTLS

    def test_rank_min_contract_price(self, standard_canonical_suite: list[ScenarioCalculationResult]) -> None:
        result = recommend_best_scenario(
            scenarios=standard_canonical_suite,
            objective=OptimizationObjective.MIN_CONTRACT_PRICE,
        )
        assert result.recommended_scenario == ScenarioType.EARLY_95
        assert result.selected_objective == OptimizationObjective.MIN_CONTRACT_PRICE

        ranked = rank_scenarios_by_objective(standard_canonical_suite, OptimizationObjective.MIN_CONTRACT_PRICE)
        assert ranked[0].final_contract_price == 3_606_400_000
        assert ranked[1].final_contract_price == 3_920_000_000

    def test_rank_min_initial_outflow(self, standard_canonical_suite: list[ScenarioCalculationResult]) -> None:
        # Both PA-CHUDONG and PA-VAY have initial cash outflow = 577,500,000 VND
        # PA-NHANH has initial cash outflow = 3,364,900,000 VND
        result = recommend_best_scenario(
            scenarios=standard_canonical_suite,
            objective=OptimizationObjective.MIN_INITIAL_OUTFLOW,
        )
        # Winner must be PA-CHUDONG due to tie-break canonical order 1 vs 3
        assert result.recommended_scenario == ScenarioType.STANDARD_PROGRESS
        assert result.is_tie_break_applied is True
        assert result.tiebreak_rule_id == TIEBREAK_RULE_CANONICAL_ORDER

        ranked = rank_scenarios_by_objective(standard_canonical_suite, OptimizationObjective.MIN_INITIAL_OUTFLOW)
        assert ranked[0].scenario_type == ScenarioType.STANDARD_PROGRESS
        assert ranked[1].scenario_type == ScenarioType.BANK_LOAN_HTLS
        assert ranked[2].scenario_type == ScenarioType.EARLY_95

    def test_rank_min_cash_outflow_to_handover(self, standard_canonical_suite: list[ScenarioCalculationResult]) -> None:
        # PA-VAY customer cash outflow until handover = 1,246,000,000 VND (30% equity + 2% kpbt)
        # PA-NHANH = 3,606,400,000 VND
        # PA-CHUDONG = 3,724,000,000 VND (100% equity prior to recon + 2% kpbt)
        result = recommend_best_scenario(
            scenarios=standard_canonical_suite,
            objective=OptimizationObjective.MIN_CASH_OUTFLOW_TO_HANDOVER,
        )
        assert result.recommended_scenario == ScenarioType.BANK_LOAN_HTLS
        assert result.is_tie_break_applied is False

        ranked = rank_scenarios_by_objective(
            standard_canonical_suite,
            OptimizationObjective.MIN_CASH_OUTFLOW_TO_HANDOVER,
        )
        assert ranked[0].scenario_type == ScenarioType.BANK_LOAN_HTLS
        assert ranked[0].customer_cash_outflow_until_handover == 1_032_500_000
        assert ranked[1].scenario_type == ScenarioType.EARLY_95
        assert ranked[2].scenario_type == ScenarioType.STANDARD_PROGRESS

    def test_rank_max_benefit_value(
        self,
        canonical_chudong: ScenarioCalculationResult,
        canonical_nhanh: ScenarioCalculationResult,
        canonical_vay: ScenarioCalculationResult,
    ) -> None:
        # Mutate benefit values
        sc_chudong = canonical_chudong.model_copy(deep=True)
        object.__setattr__(sc_chudong, "total_benefit_value_vnd", 50_000_000)

        sc_nhanh = canonical_nhanh.model_copy(deep=True)
        object.__setattr__(sc_nhanh, "total_benefit_value_vnd", 0)

        sc_vay = canonical_vay.model_copy(deep=True)
        object.__setattr__(sc_vay, "total_benefit_value_vnd", 200_000_000)

        result = recommend_best_scenario(
            scenarios=[sc_chudong, sc_nhanh, sc_vay],
            objective=OptimizationObjective.MAX_BENEFIT_VALUE,
        )
        assert result.recommended_scenario == ScenarioType.BANK_LOAN_HTLS
        assert result.is_tie_break_applied is False

        ranked = rank_scenarios_by_objective(
            [sc_chudong, sc_nhanh, sc_vay],
            OptimizationObjective.MAX_BENEFIT_VALUE,
        )
        assert ranked[0].scenario_type == ScenarioType.BANK_LOAN_HTLS
        assert ranked[0].total_benefit_value_vnd == 200_000_000
        assert ranked[1].scenario_type == ScenarioType.STANDARD_PROGRESS
        assert ranked[1].total_benefit_value_vnd == 50_000_000
        assert ranked[2].scenario_type == ScenarioType.EARLY_95
        assert ranked[2].total_benefit_value_vnd == 0


# ===========================================================================
# 2. Tests for Deterministic Tie-Break Mechanism (Task 3.4)
# ===========================================================================
class TestDeterministicTieBreak:
    """Verify deterministic 3-tier tie-breaking rules and metadata."""

    def test_tiebreak_tier2_contract_price_priority(
        self,
        canonical_chudong: ScenarioCalculationResult,
        canonical_vay: ScenarioCalculationResult,
    ) -> None:
        # Construct two scenarios tied on MIN_NET_PRICE (both 3.5B)
        # but with different contract prices
        sc1 = canonical_chudong.model_copy(deep=True)
        object.__setattr__(sc1, "final_contract_price", 3_920_000_000)

        sc2 = canonical_vay.model_copy(deep=True)
        object.__setattr__(sc2, "final_contract_price", 3_800_000_000)

        result = recommend_best_scenario(
            scenarios=[sc1, sc2],
            objective=OptimizationObjective.MIN_NET_PRICE,
        )
        # sc2 has lower contract price (3.8B < 3.92B), so it wins via Tier 2
        assert result.recommended_scenario == ScenarioType.BANK_LOAN_HTLS
        assert result.is_tie_break_applied is True
        assert result.tiebreak_rule_id == TIEBREAK_RULE_CONTRACT_PRICE
        assert "Tổng giá HĐMB thấp hơn" in (result.tie_break_reason or "")

    def test_tiebreak_tier3_canonical_scenario_order(
        self,
        canonical_chudong: ScenarioCalculationResult,
        canonical_vay: ScenarioCalculationResult,
    ) -> None:
        # Both tied on initial outflow AND tied on final contract price
        result = recommend_best_scenario(
            scenarios=[canonical_vay, canonical_chudong],  # Pass VAY first
            objective=OptimizationObjective.MIN_INITIAL_OUTFLOW,
        )
        # CHUDONG must win because canonical order is 1 vs 3
        assert result.recommended_scenario == ScenarioType.STANDARD_PROGRESS
        assert result.is_tie_break_applied is True
        assert result.tiebreak_rule_id == TIEBREAK_RULE_CANONICAL_ORDER
        assert "thứ tự chuẩn tắc canonical" in (result.tie_break_reason or "")

    def test_no_tiebreak_when_clear_winner(self, standard_canonical_suite: list[ScenarioCalculationResult]) -> None:
        result = recommend_best_scenario(
            scenarios=standard_canonical_suite,
            objective=OptimizationObjective.MIN_NET_PRICE,
        )
        assert result.is_tie_break_applied is False
        assert result.tiebreak_rule_id is None
        assert result.tie_break_reason is None


# ===========================================================================
# 3. Tests for Infeasible Scenario Filtering (Task 3.5)
# ===========================================================================
class TestInfeasibleScenarioHandling:
    """Verify that infeasible scenarios are excluded from recommendations."""

    def test_infeasible_scenario_cannot_be_recommended(
        self, standard_canonical_suite: list[ScenarioCalculationResult]
    ) -> None:
        # In MIN_NET_PRICE, EARLY_95 is the natural winner.
        # But if EARLY_95 is infeasible, STANDARD_PROGRESS should win instead.
        result = recommend_best_scenario(
            scenarios=standard_canonical_suite,
            objective=OptimizationObjective.MIN_NET_PRICE,
            infeasible_scenarios=[ScenarioType.EARLY_95],
        )
        assert result.recommended_scenario == ScenarioType.STANDARD_PROGRESS

        # In summary, EARLY_95 must be marked is_feasible = False and ranked last
        early_summary = next(s for s in result.comparison_summary if s["scenario_type"] == "EARLY_95")
        assert early_summary["is_feasible"] is False
        assert early_summary["is_recommended"] is False
        assert early_summary["rank"] == 3

    def test_infeasible_scenario_passed_as_string_alias(
        self, standard_canonical_suite: list[ScenarioCalculationResult]
    ) -> None:
        # Pass alias string 'PA-NHANH'
        result = recommend_best_scenario(
            scenarios=standard_canonical_suite,
            objective=OptimizationObjective.MIN_NET_PRICE,
            infeasible_scenarios=["PA-NHANH"],
        )
        assert result.recommended_scenario != ScenarioType.EARLY_95

    def test_all_scenarios_infeasible_raises_error(
        self, standard_canonical_suite: list[ScenarioCalculationResult]
    ) -> None:
        with pytest.raises(NoFeasibleScenarioError, match="NO_FEASIBLE_SCENARIO"):
            recommend_best_scenario(
                scenarios=standard_canonical_suite,
                objective=OptimizationObjective.MIN_NET_PRICE,
                infeasible_scenarios=[
                    ScenarioType.STANDARD_PROGRESS,
                    ScenarioType.EARLY_95,
                    ScenarioType.BANK_LOAN_HTLS,
                ],
            )


# ===========================================================================
# 4. Tests for RecommendationResult Structure & Quantitative Rationale (Task 3.5)
# ===========================================================================
class TestRecommendationResultAndRationale:
    """Verify RecommendationResult envelope integrity and quantitative rationale."""

    def test_quantitative_rationale_contains_exact_amounts(
        self, standard_canonical_suite: list[ScenarioCalculationResult]
    ) -> None:
        result = recommend_best_scenario(
            scenarios=standard_canonical_suite,
            objective=OptimizationObjective.MIN_NET_PRICE,
        )
        rationale = result.quantitative_rationale
        assert "3,220,000,000 VNĐ" in rationale
        assert "tiết kiệm 280,000,000 VNĐ" in rationale
        assert "PA-NHANH" in rationale
        assert "MIN_NET_PRICE" in rationale

    def test_comparison_summary_schema_completeness(
        self, standard_canonical_suite: list[ScenarioCalculationResult]
    ) -> None:
        result = recommend_best_scenario(
            scenarios=standard_canonical_suite,
            objective=OptimizationObjective.MIN_CONTRACT_PRICE,
        )
        summary = result.comparison_summary
        assert len(summary) == 3

        for item in summary:
            assert "rank" in item
            assert "scenario_type" in item
            assert "canonical_code" in item
            assert "net_price_vnd" in item
            assert "contract_price_vnd" in item
            assert "initial_cash_outflow_vnd" in item
            assert "cash_outflow_to_handover_vnd" in item
            assert "total_benefit_value_vnd" in item
            assert "target_metric_value_vnd" in item
            assert "is_feasible" in item
            assert "is_recommended" in item

        # Verify rank 1 is recommended
        rank1 = next(item for item in summary if item["rank"] == 1)
        assert rank1["is_recommended"] is True
        assert rank1["scenario_type"] == "EARLY_95"

    def test_empty_scenarios_raises_value_error(self) -> None:
        with pytest.raises(ValueError, match="không được rỗng"):
            recommend_best_scenario(scenarios=[], objective=OptimizationObjective.MIN_NET_PRICE)

    def test_get_objective_metric_value_helper(self, canonical_chudong: ScenarioCalculationResult) -> None:
        assert get_objective_metric_value(canonical_chudong, OptimizationObjective.MIN_NET_PRICE) == 3_500_000_000
        assert get_objective_metric_value(canonical_chudong, OptimizationObjective.MIN_CONTRACT_PRICE) == 3_920_000_000
        assert get_objective_metric_value(canonical_chudong, OptimizationObjective.MIN_INITIAL_OUTFLOW) == 577_500_000
        assert (
            get_objective_metric_value(canonical_chudong, OptimizationObjective.MIN_CASH_OUTFLOW_TO_HANDOVER)
            == 3_727_500_000
        )
        assert get_objective_metric_value(canonical_chudong, OptimizationObjective.MAX_BENEFIT_VALUE) == 0


# ===========================================================================
# 5. Anti-Float Guard & SLA Performance Tests
# ===========================================================================
class TestAntiFloatGuardAndPerformance:
    """Verify zero-float prohibition and SLA execution speed."""

    def test_forbid_float_in_scenarios_list(self, canonical_chudong: ScenarioCalculationResult) -> None:
        with pytest.raises(TypeError, match="FLOAT_PROHIBITED"):
            # Passing float in list
            rank_scenarios_by_objective(
                [canonical_chudong, 0.5],  # type: ignore
                OptimizationObjective.MIN_NET_PRICE,
            )

    def test_ranking_performance_sla_under_20ms(
        self, standard_canonical_suite: list[ScenarioCalculationResult]
    ) -> None:
        # Warmup
        recommend_best_scenario(standard_canonical_suite, OptimizationObjective.MIN_NET_PRICE)

        start = time.perf_counter()
        iterations = 100
        for _ in range(iterations):
            recommend_best_scenario(
                standard_canonical_suite,
                OptimizationObjective.MIN_NET_PRICE,
            )
        elapsed = (time.perf_counter() - start) / iterations * 1000  # ms

        # TD-4.4 SLA budget for rank_scenarios_by_objective is 20ms
        assert elapsed < 20.0, f"Ranking latency {elapsed:.3f}ms exceeded 20ms SLA"
