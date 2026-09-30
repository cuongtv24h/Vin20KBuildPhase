"""Property-Based Test Suite for Financial Calculation Engine (Task 4.6).

FCS v2.6 Reference: Section 11 (Property-Based Testing & Mathematical Invariants)
TD-4.1 Reference: Section 3.2 (Hardened Pricing Engine Invariant Verification)
Implement Plan Detail Reference: Section 7.5 (D2-5 Golden Benchmark & Properties)

Verifies 10 fundamental mathematical properties and invariant theorems using Hypothesis:
1. Reconciliation Completeness: Sum(gross_k) == Final Contract Price (Delta = 0 VND).
2. Non-negativity Invariant: All financial component amounts >= 0.
3. Price Monotonicity: P_listed_A > P_listed_B ==> P_net_A > P_net_B and P_contract_A > P_contract_B.
4. Discount Monotonicity: Additional discount ==> P_net decreases or stays equal.
5. Permutation Invariance: Any permutation of input scenarios yields identical ranking.
6. Deterministic Idempotency: Same input produces byte-identical hash and results.
7. Non-negative Residual: Reconciliation installment absorbs rounding without negative gross.
8. Funding Breakdown Exact Sum: Sum(equity) + Sum(bank) + Sum(kpbt) == Contract Price.
9. Deposit Credit Invariant: Sum(deposit_credited) == deposit_paid and cash_due balances.
10. Canonical Hash Sensitivity: Single bit / 1 VND change produces completely different SHA-256 hash.
"""

from datetime import date, timedelta
from decimal import Decimal

from hypothesis import given, settings
from hypothesis import strategies as st

from src.pricing_sidecar.canonical_hash import generate_canonical_hash
from src.pricing_sidecar.contracts import (
    BenefitApplicationRule,
    BenefitCategory,
    BenefitType,
    OptimizationObjective,
    StructuredPolicyReference,
    ValuationStatus,
)
from src.pricing_sidecar.engine import (
    calculate_pa_chudong,
    calculate_pa_nhanh,
    calculate_pa_vay,
)
from src.pricing_sidecar.ranking import (
    rank_scenarios_by_objective,
    recommend_best_scenario,
)
from src.pricing_sidecar.validation import validate_scenario_calculation

# ---------------------------------------------------------------------------
# Hypothesis Strategies & Settings
# ---------------------------------------------------------------------------
price_strategy = st.integers(min_value=1_000_000_000, max_value=30_000_000_000)
deposit_strategy = st.integers(min_value=50_000_000, max_value=100_000_000)
date_strategy = st.dates(min_value=date(2026, 1, 1), max_value=date(2027, 12, 31))

POLICY_REF = StructuredPolicyReference(
    policy_id="POL-2026-VLF-GEN",
    policy_version="v2.6",
    clause_id="Điều 4 Khoản 1",
    page_number=10,
    source_file_sha256="c" * 64,
    effective_from=date(2026, 1, 1),
    effective_to=date(2026, 12, 31),
)


# ===========================================================================
# 1. Property 1: Reconciliation Completeness (FCS v2.6 §11 Property 1)
# ===========================================================================
class TestProperty1ReconciliationCompleteness:
    """Theorem: Sum of all cashflow installments identically equals final contract price."""

    @settings(max_examples=25, deadline=None)
    @given(listed_price=price_strategy, deposit_date=date_strategy, deposit_amount=deposit_strategy)
    def test_reconciliation_completeness_pa_chudong(
        self, listed_price: int, deposit_date: date, deposit_amount: int
    ) -> None:
        result = calculate_pa_chudong(
            listed_price_vnd=listed_price,
            deposit_date=deposit_date,
            deposit_amount_vnd=deposit_amount,
        )
        total_schedule_gross = sum(item.installment_gross_obligation_vnd for item in result.cashflow_schedule)
        assert total_schedule_gross == result.final_contract_price
        report = validate_scenario_calculation(result)
        assert report.is_valid is True

    @settings(max_examples=25, deadline=None)
    @given(listed_price=price_strategy, deposit_date=date_strategy, deposit_amount=deposit_strategy)
    def test_reconciliation_completeness_pa_nhanh(
        self, listed_price: int, deposit_date: date, deposit_amount: int
    ) -> None:
        result = calculate_pa_nhanh(
            listed_price_vnd=listed_price,
            deposit_date=deposit_date,
            deposit_amount_vnd=deposit_amount,
        )
        total_schedule_gross = sum(item.installment_gross_obligation_vnd for item in result.cashflow_schedule)
        assert total_schedule_gross == result.final_contract_price

    @settings(max_examples=25, deadline=None)
    @given(listed_price=price_strategy, deposit_date=date_strategy, deposit_amount=deposit_strategy)
    def test_reconciliation_completeness_pa_vay(
        self, listed_price: int, deposit_date: date, deposit_amount: int
    ) -> None:
        result = calculate_pa_vay(
            listed_price_vnd=listed_price,
            deposit_date=deposit_date,
            deposit_amount_vnd=deposit_amount,
        )
        total_schedule_gross = sum(item.installment_gross_obligation_vnd for item in result.cashflow_schedule)
        assert total_schedule_gross == result.final_contract_price


# ===========================================================================
# 2. Property 2: Non-Negativity Invariant (FCS v2.6 §11 Property 2)
# ===========================================================================
class TestProperty2NonNegativity:
    """Theorem: Every financial field in top-level output and all installments is strictly non-negative."""

    @settings(max_examples=25, deadline=None)
    @given(listed_price=price_strategy, deposit_date=date_strategy, deposit_amount=deposit_strategy)
    def test_non_negativity_all_scenarios(self, listed_price: int, deposit_date: date, deposit_amount: int) -> None:
        for calc_fn in (calculate_pa_chudong, calculate_pa_nhanh, calculate_pa_vay):
            res = calc_fn(
                listed_price_vnd=listed_price,
                deposit_date=deposit_date,
                deposit_amount_vnd=deposit_amount,
            )
            assert res.net_price_before_vat > 0
            assert res.vat_amount > 0
            assert res.maintenance_fee_amount > 0
            assert res.final_contract_price > 0
            assert res.fixed_discount_vnd >= 0
            assert res.percentage_discount_vnd >= 0
            assert res.initial_gross_obligation_vnd >= 0
            assert res.initial_cash_outflow_vnd >= 0
            assert res.customer_cash_outflow_until_handover >= 0

            for inst in res.cashflow_schedule:
                assert inst.installment_gross_obligation_vnd >= 0
                assert inst.customer_equity_paid_vnd >= 0
                assert inst.bank_disbursement_vnd >= 0
                assert inst.maintenance_fee_paid_vnd >= 0
                assert inst.deposit_credited_vnd >= 0
                assert inst.installment_additional_cash_due_vnd >= 0


# ===========================================================================
# 3. Property 3: Price Monotonicity (FCS v2.6 §11 Property 3)
# ===========================================================================
class TestProperty3PriceMonotonicity:
    """Theorem: Higher listed price strictly implies higher net and contract prices."""

    @settings(max_examples=25, deadline=None)
    @given(
        price_a=st.integers(min_value=2_000_000_000, max_value=20_000_000_000),
        price_diff=st.integers(min_value=100_000_000, max_value=5_000_000_000),
        deposit_date=date_strategy,
    )
    def test_price_monotonicity(self, price_a: int, price_diff: int, deposit_date: date) -> None:
        price_b = price_a + price_diff  # Guaranteed price_b > price_a

        res_a = calculate_pa_chudong(listed_price_vnd=price_a, deposit_date=deposit_date)
        res_b = calculate_pa_chudong(listed_price_vnd=price_b, deposit_date=deposit_date)

        assert res_b.net_price_before_vat > res_a.net_price_before_vat
        assert res_b.final_contract_price > res_a.final_contract_price
        assert res_b.vat_amount > res_a.vat_amount
        assert res_b.maintenance_fee_amount > res_a.maintenance_fee_amount


# ===========================================================================
# 4. Property 4: Discount Monotonicity (FCS v2.6 §11 Property 4)
# ===========================================================================
class TestProperty4DiscountMonotonicity:
    """Theorem: Applying additional discounts monotonically decreases or keeps equal the net price."""

    @settings(max_examples=25, deadline=None)
    @given(
        listed_price=st.integers(min_value=3_000_000_000, max_value=15_000_000_000),
        discount_vnd=st.integers(min_value=10_000_000, max_value=100_000_000),
    )
    def test_discount_monotonicity(self, listed_price: int, discount_vnd: int) -> None:
        benefit = BenefitApplicationRule(
            benefit_id="BENEFIT_MONO_01",
            benefit_code="DISCOUNT_MONO_TEST",
            benefit_name="Chiết khấu test đơn điệu",
            category=BenefitCategory.CASH_DISCOUNT,
            benefit_type=BenefitType.FIXED_CASH,
            fixed_deduction_vnd=discount_vnd,
            percentage_deduction_rate=Decimal("0.0000"),
            valuation_status=ValuationStatus.APPROVED,
            price_deduction_authorized=True,
            source_policy_clause=POLICY_REF,
        )

        res_no_discount = calculate_pa_chudong(listed_price_vnd=listed_price)
        res_with_discount = calculate_pa_chudong(listed_price_vnd=listed_price, approved_benefits=[benefit])

        assert res_with_discount.net_price_before_vat < res_no_discount.net_price_before_vat
        assert res_with_discount.final_contract_price < res_no_discount.final_contract_price


# ===========================================================================
# 5. Property 5: Permutation Invariance in Ranking (FCS v2.6 §11 Property 5)
# ===========================================================================
class TestProperty5PermutationInvariance:
    """Theorem: Permuting the order of input scenarios does not change ranking outcome."""

    @settings(max_examples=25, deadline=None)
    @given(
        listed_price=price_strategy,
        perm_idx=st.sampled_from(
            [
                (0, 1, 2),
                (0, 2, 1),
                (1, 0, 2),
                (1, 2, 0),
                (2, 0, 1),
                (2, 1, 0),
            ]
        ),
        objective=st.sampled_from(list(OptimizationObjective)),
    )
    def test_ranking_permutation_invariance(
        self, listed_price: int, perm_idx: tuple[int, int, int], objective: OptimizationObjective
    ) -> None:
        cd = calculate_pa_chudong(listed_price_vnd=listed_price)
        nh = calculate_pa_nhanh(listed_price_vnd=listed_price)
        vy = calculate_pa_vay(listed_price_vnd=listed_price)

        baseline_scenarios = [cd, nh, vy]
        permuted_scenarios = [baseline_scenarios[i] for i in perm_idx]

        ranked_base = rank_scenarios_by_objective(baseline_scenarios, objective=objective)
        ranked_perm = rank_scenarios_by_objective(permuted_scenarios, objective=objective)

        assert [s.scenario_type for s in ranked_base] == [s.scenario_type for s in ranked_perm]

        rec_base = recommend_best_scenario(baseline_scenarios, objective=objective)
        rec_perm = recommend_best_scenario(permuted_scenarios, objective=objective)
        assert rec_base.recommended_scenario == rec_perm.recommended_scenario


# ===========================================================================
# 6. Property 6: Deterministic Idempotency (FCS v2.6 §11 Property 6)
# ===========================================================================
class TestProperty6DeterministicIdempotency:
    """Theorem: Running identical inputs yields byte-identical snapshots and canonical hashes."""

    @settings(max_examples=25, deadline=None)
    @given(listed_price=price_strategy, deposit_date=date_strategy, deposit_amount=deposit_strategy)
    def test_idempotent_hash(self, listed_price: int, deposit_date: date, deposit_amount: int) -> None:
        run_1 = calculate_pa_chudong(
            listed_price_vnd=listed_price,
            deposit_date=deposit_date,
            deposit_amount_vnd=deposit_amount,
        )
        run_2 = calculate_pa_chudong(
            listed_price_vnd=listed_price,
            deposit_date=deposit_date,
            deposit_amount_vnd=deposit_amount,
        )

        hash_1 = generate_canonical_hash(run_1)
        hash_2 = generate_canonical_hash(run_2)

        assert hash_1 == hash_2
        assert run_1.final_contract_price == run_2.final_contract_price


# ===========================================================================
# 7. Property 7: Non-Negative Residual & Exact Absorption (FCS v2.6 §11 Property 7)
# ===========================================================================
class TestProperty7NonNegativeResidual:
    """Theorem: Residual absorption in last installment preserves non-negativity and exact sum."""

    @settings(max_examples=25, deadline=None)
    @given(listed_price=price_strategy, deposit_date=date_strategy)
    def test_residual_absorption(self, listed_price: int, deposit_date: date) -> None:
        for calc_fn in (calculate_pa_chudong, calculate_pa_nhanh, calculate_pa_vay):
            res = calc_fn(listed_price_vnd=listed_price, deposit_date=deposit_date)
            last_installment = res.cashflow_schedule[-1]
            assert last_installment.is_reconciliation_installment is True
            assert last_installment.installment_gross_obligation_vnd > 0
            assert sum(i.installment_gross_obligation_vnd for i in res.cashflow_schedule) == res.final_contract_price


# ===========================================================================
# 8. Property 8: Funding Breakdown Exact Sum (FCS v2.6 §11 Property 8)
# ===========================================================================
class TestProperty8FundingBreakdownExactSum:
    """Theorem: Sum of equity, bank disbursement, and kpbt across installments balances perfectly."""

    @settings(max_examples=25, deadline=None)
    @given(listed_price=price_strategy, deposit_date=date_strategy, deposit_amount=deposit_strategy)
    def test_funding_breakdown(self, listed_price: int, deposit_date: date, deposit_amount: int) -> None:
        res = calculate_pa_vay(
            listed_price_vnd=listed_price,
            deposit_date=deposit_date,
            deposit_amount_vnd=deposit_amount,
        )
        total_equity = sum(i.customer_equity_paid_vnd for i in res.cashflow_schedule)
        total_bank = sum(i.bank_disbursement_vnd for i in res.cashflow_schedule)
        total_kpbt = sum(i.maintenance_fee_paid_vnd for i in res.cashflow_schedule)

        assert total_kpbt == res.maintenance_fee_amount
        assert total_equity + total_bank + total_kpbt == res.final_contract_price


# ===========================================================================
# 9. Property 9: Deposit Credit Invariant (FCS v2.6 §11 Property 9)
# ===========================================================================
class TestProperty9DepositCreditInvariant:
    """Theorem: Deposit credited across schedule equals initial deposit, and installment cash due balances."""

    @settings(max_examples=25, deadline=None)
    @given(listed_price=price_strategy, deposit_date=date_strategy, deposit_amount=deposit_strategy)
    def test_deposit_credit_conservation(self, listed_price: int, deposit_date: date, deposit_amount: int) -> None:
        res = calculate_pa_chudong(
            listed_price_vnd=listed_price,
            deposit_date=deposit_date,
            deposit_amount_vnd=deposit_amount,
        )
        total_deposit_credited = sum(i.deposit_credited_vnd for i in res.cashflow_schedule)
        assert total_deposit_credited == deposit_amount

        for inst in res.cashflow_schedule:
            # cash_due + deposit_credited must equal equity + kpbt
            assert (
                inst.installment_additional_cash_due_vnd + inst.deposit_credited_vnd
                == inst.customer_equity_paid_vnd + inst.maintenance_fee_paid_vnd
            )


# ===========================================================================
# 10. Property 10: Canonical Hash Sensitivity (FCS v2.6 §11 Property 10)
# ===========================================================================
class TestProperty10CanonicalHashSensitivity:
    """Theorem: Modifying even 1 unit (1 VND, 1 day) produces a distinct SHA-256 hash."""

    @settings(max_examples=25, deadline=None)
    @given(listed_price=price_strategy, deposit_date=date_strategy, deposit_amount=deposit_strategy)
    def test_hash_sensitivity(self, listed_price: int, deposit_date: date, deposit_amount: int) -> None:
        base_res = calculate_pa_chudong(
            listed_price_vnd=listed_price,
            deposit_date=deposit_date,
            deposit_amount_vnd=deposit_amount,
        )
        base_hash = generate_canonical_hash(base_res)

        # 10a. Price shift by +1 VND
        res_price_mod = calculate_pa_chudong(
            listed_price_vnd=listed_price + 1,
            deposit_date=deposit_date,
            deposit_amount_vnd=deposit_amount,
        )
        assert generate_canonical_hash(res_price_mod) != base_hash

        # 10b. Date shift by +1 day
        res_date_mod = calculate_pa_chudong(
            listed_price_vnd=listed_price,
            deposit_date=deposit_date + timedelta(days=1),
            deposit_amount_vnd=deposit_amount,
        )
        assert generate_canonical_hash(res_date_mod) != base_hash
