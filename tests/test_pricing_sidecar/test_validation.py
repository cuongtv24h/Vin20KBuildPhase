"""Unit tests for Financial Validation Gate and Sanity Checks (Task 3.1 & 3.2).

Conforming to FCS v2.6 §9, TD-4.1 §3.2, TD-4.4 §3.3, and Implement Plan Detail §7.3.
"""

import time
from datetime import date, timedelta
from decimal import Decimal

import pytest

from src.pricing_sidecar.contracts import (
    CalculationStatus,
    PricingCalculationOutput,
    ScenarioCalculationResult,
)
from src.pricing_sidecar.engine import (
    calculate_pa_chudong,
    calculate_pa_nhanh,
    calculate_pa_vay,
)
from src.pricing_sidecar.validation import (
    FINANCIAL_SANITY_FAILED_CODE,
    STANDARD_SANITY_INVARIANTS,
    FinancialSanityError,
    check_scenario_sanity,
    validate_pricing_results,
    validate_scenario_calculation,
)


@pytest.fixture
def canonical_chudong_result() -> ScenarioCalculationResult:
    """Fixture providing a standard PA-CHUDONG calculation result for apartment A-12-05."""
    return calculate_pa_chudong(
        listed_price_vnd=3_500_000_000,
        deposit_date=date(2026, 3, 15),
        deposit_amount_vnd=100_000_000,
    )


@pytest.fixture
def canonical_nhanh_result() -> ScenarioCalculationResult:
    """Fixture providing a standard PA-NHANH calculation result for apartment A-12-05."""
    return calculate_pa_nhanh(
        listed_price_vnd=3_500_000_000,
        deposit_date=date(2026, 3, 15),
        deposit_amount_vnd=100_000_000,
    )


@pytest.fixture
def canonical_vay_result() -> ScenarioCalculationResult:
    """Fixture providing a standard PA-VAY calculation result for apartment A-12-05."""
    return calculate_pa_vay(
        listed_price_vnd=3_500_000_000,
        deposit_date=date(2026, 3, 15),
        deposit_amount_vnd=100_000_000,
    )


# ===========================================================================
# 1. Positive Tests (100% Pass)
# ===========================================================================
class TestSanityChecksPositive:
    """Positive test cases verifying that canonical calculations pass all 6 Sanity Checks."""

    def test_pa_chudong_passes_all_checks(self, canonical_chudong_result: ScenarioCalculationResult) -> None:
        report = validate_scenario_calculation(canonical_chudong_result, raise_on_error=True)
        assert report.is_valid is True
        assert report.status == CalculationStatus.VALID
        assert report.field_errors == []
        assert report.error_message is None
        assert report.invariants_checked == STANDARD_SANITY_INVARIANTS

    def test_pa_nhanh_passes_all_checks(self, canonical_nhanh_result: ScenarioCalculationResult) -> None:
        report = validate_scenario_calculation(canonical_nhanh_result, raise_on_error=True)
        assert report.is_valid is True
        assert report.status == CalculationStatus.VALID
        assert len(report.field_errors) == 0

    def test_pa_vay_passes_all_checks(self, canonical_vay_result: ScenarioCalculationResult) -> None:
        report = validate_scenario_calculation(canonical_vay_result, raise_on_error=True)
        assert report.is_valid is True
        assert report.status == CalculationStatus.VALID
        assert len(report.field_errors) == 0

    def test_validate_pricing_results_all_canonical(
        self,
        canonical_chudong_result: ScenarioCalculationResult,
        canonical_nhanh_result: ScenarioCalculationResult,
        canonical_vay_result: ScenarioCalculationResult,
    ) -> None:
        scenarios = [
            canonical_chudong_result,
            canonical_nhanh_result,
            canonical_vay_result,
        ]
        report = validate_pricing_results(scenarios, raise_on_error=True)
        assert report.is_valid is True
        assert report.status == CalculationStatus.VALID
        assert report.field_errors == []

    def test_validate_pricing_results_output_envelope(
        self, canonical_chudong_result: ScenarioCalculationResult
    ) -> None:
        output_envelope = PricingCalculationOutput(
            calculation_timestamp="2026-09-24T12:00:00Z",
            unit_code="A-12-05",
            scenario_results=[canonical_chudong_result],
            canonical_snapshot_hash="a" * 64,
        )
        report = validate_pricing_results(output_envelope, raise_on_error=True)
        assert report.is_valid is True
        assert report.status == CalculationStatus.VALID


# ===========================================================================
# 2. Sanity Check 1: Net Price Bounds (INV-FIN-01)
# ===========================================================================
class TestSanityCheck1NetBounds:
    """Verifies Sanity Check 1: 0 < net_price_before_vat <= listed_price_vnd."""

    def test_net_price_non_positive_fails(self, canonical_chudong_result: ScenarioCalculationResult) -> None:
        # Construct object bypassing model validator to test validation gate
        mutated = canonical_chudong_result.model_copy(deep=True)
        object.__setattr__(mutated, "net_price_before_vat", 0)

        errors = check_scenario_sanity(mutated)
        codes = [err.code for err in errors]
        assert "NET_PRICE_NON_POSITIVE" in codes

        field_err = next(err for err in errors if err.code == "NET_PRICE_NON_POSITIVE")
        assert field_err.field == "net_price_before_vat"
        assert field_err.actual_vnd == 0
        assert "SANITY_FAIL" in field_err.message

    def test_net_price_exceeds_listed_price_fails(self, canonical_chudong_result: ScenarioCalculationResult) -> None:
        mutated = canonical_chudong_result.model_copy(deep=True)
        object.__setattr__(mutated, "net_price_before_vat", 4_000_000_000)

        errors = check_scenario_sanity(mutated, listed_price_vnd=3_500_000_000)
        codes = [err.code for err in errors]
        assert "NET_PRICE_EXCEEDS_LISTED" in codes

        field_err = next(err for err in errors if err.code == "NET_PRICE_EXCEEDS_LISTED")
        assert field_err.expected_vnd == 3_500_000_000
        assert field_err.actual_vnd == 4_000_000_000


# ===========================================================================
# 3. Sanity Check 2: Dual Discount Cap Compliance (INV-FIN-02)
# ===========================================================================
class TestSanityCheck2DualDiscountCap:
    """Verifies Sanity Check 2: rate <= max_discount_rate and total <= 40% listed."""

    def test_percentage_discount_cap_exceeded(self, canonical_nhanh_result: ScenarioCalculationResult) -> None:
        mutated = canonical_nhanh_result.model_copy(deep=True)
        object.__setattr__(mutated, "total_discount_rate", Decimal("0.3600"))

        errors = check_scenario_sanity(mutated, max_discount_rate=Decimal("0.3500"))
        codes = [err.code for err in errors]
        assert "PERCENTAGE_DISCOUNT_CAP_EXCEEDED" in codes

        field_err = next(err for err in errors if err.code == "PERCENTAGE_DISCOUNT_CAP_EXCEEDED")
        assert field_err.field == "total_discount_rate"
        assert field_err.expected_rate == Decimal("0.3500")
        assert field_err.actual_rate == Decimal("0.3600")

    def test_total_discount_money_cap_exceeded(self, canonical_chudong_result: ScenarioCalculationResult) -> None:
        mutated = canonical_chudong_result.model_copy(deep=True)
        # 3.5B * 40% = 1.4B; set fixed discount to 1.5B
        object.__setattr__(mutated, "fixed_discount_vnd", 1_500_000_000)

        errors = check_scenario_sanity(
            mutated,
            listed_price_vnd=3_500_000_000,
            max_total_discount_cap_rate=Decimal("0.4000"),
        )
        codes = [err.code for err in errors]
        assert "TOTAL_DISCOUNT_CAP_EXCEEDED" in codes

        field_err = next(err for err in errors if err.code == "TOTAL_DISCOUNT_CAP_EXCEEDED")
        assert field_err.expected_vnd == 1_400_000_000
        assert field_err.actual_vnd == 1_500_000_000


# ===========================================================================
# 4. Sanity Check 3: VAT & KPBT Consistency (INV-FIN-03)
# ===========================================================================
class TestSanityCheck3TaxAndFeeConsistency:
    """Verifies Sanity Check 3: VAT and KPBT exact match to policy snapshot rates."""

    def test_vat_mismatch_detected(self, canonical_chudong_result: ScenarioCalculationResult) -> None:
        mutated = canonical_chudong_result.model_copy(deep=True)
        # Offset VAT by 1 VND
        expected = canonical_chudong_result.vat_amount
        object.__setattr__(mutated, "vat_amount", expected + 1)

        errors = check_scenario_sanity(mutated)
        codes = [err.code for err in errors]
        assert "VAT_AMOUNT_MISMATCH" in codes

        field_err = next(err for err in errors if err.code == "VAT_AMOUNT_MISMATCH")
        assert field_err.field == "vat_amount"
        assert field_err.expected_vnd == expected
        assert field_err.actual_vnd == expected + 1

    def test_kpbt_mismatch_detected(self, canonical_chudong_result: ScenarioCalculationResult) -> None:
        mutated = canonical_chudong_result.model_copy(deep=True)
        expected = canonical_chudong_result.maintenance_fee_amount
        object.__setattr__(mutated, "maintenance_fee_amount", expected - 1000)

        errors = check_scenario_sanity(mutated)
        codes = [err.code for err in errors]
        assert "KPBT_AMOUNT_MISMATCH" in codes

        field_err = next(err for err in errors if err.code == "KPBT_AMOUNT_MISMATCH")
        assert field_err.field == "maintenance_fee_amount"
        assert field_err.expected_vnd == expected
        assert field_err.actual_vnd == expected - 1000


# ===========================================================================
# 5. Sanity Check 4: Contract Price Exact Sum (INV-FIN-04)
# ===========================================================================
class TestSanityCheck4ContractPriceBalance:
    """Verifies Sanity Check 4: final_contract_price == net + vat + kpbt."""

    def test_contract_price_mismatch_detected(self, canonical_chudong_result: ScenarioCalculationResult) -> None:
        mutated = canonical_chudong_result.model_copy(deep=True)
        object.__setattr__(
            mutated,
            "final_contract_price",
            canonical_chudong_result.final_contract_price + 500,
        )

        errors = check_scenario_sanity(mutated)
        codes = [err.code for err in errors]
        assert "CONTRACT_PRICE_MISMATCH" in codes

        field_err = next(err for err in errors if err.code == "CONTRACT_PRICE_MISMATCH")
        assert field_err.field == "final_contract_price"
        assert field_err.actual_vnd == canonical_chudong_result.final_contract_price + 500


# ===========================================================================
# 6. Sanity Check 5: Cashflow Reconciliation Completeness (INV-FIN-05)
# ===========================================================================
class TestSanityCheck5CashflowReconciliation:
    """Verifies Sanity Check 5: schedule sum == contract price and internal installment consistency."""

    def test_schedule_total_sum_mismatch(self, canonical_chudong_result: ScenarioCalculationResult) -> None:
        mutated = canonical_chudong_result.model_copy(deep=True)
        # Modify last installment amount by -1 VND
        sched = list(mutated.cashflow_schedule)
        last_inst = sched[-1].model_copy(deep=True)
        object.__setattr__(
            last_inst,
            "installment_gross_obligation_vnd",
            last_inst.installment_gross_obligation_vnd - 1,
        )
        sched[-1] = last_inst
        object.__setattr__(mutated, "cashflow_schedule", sched)

        errors = check_scenario_sanity(mutated)
        codes = [err.code for err in errors]
        assert "PAYMENT_SCHEDULE_SUM_MISMATCH" in codes

        field_err = next(err for err in errors if err.code == "PAYMENT_SCHEDULE_SUM_MISMATCH")
        assert field_err.field == "cashflow_schedule"
        assert field_err.expected_vnd == mutated.final_contract_price
        assert field_err.actual_vnd == mutated.final_contract_price - 1

    def test_installment_gross_obligation_mismatch(self, canonical_chudong_result: ScenarioCalculationResult) -> None:
        mutated = canonical_chudong_result.model_copy(deep=True)
        sched = list(mutated.cashflow_schedule)
        inst0 = sched[0].model_copy(deep=True)
        # equity + bank + kpbt does not match gross
        object.__setattr__(
            inst0,
            "customer_equity_paid_vnd",
            inst0.customer_equity_paid_vnd - 50_000,
        )
        sched[0] = inst0
        object.__setattr__(mutated, "cashflow_schedule", sched)

        errors = check_scenario_sanity(mutated)
        codes = [err.code for err in errors]
        assert "INSTALLMENT_GROSS_MISMATCH" in codes

    def test_installment_additional_cash_due_mismatch(
        self, canonical_chudong_result: ScenarioCalculationResult
    ) -> None:
        mutated = canonical_chudong_result.model_copy(deep=True)
        sched = list(mutated.cashflow_schedule)
        inst0 = sched[0].model_copy(deep=True)
        # Alter additional cash due
        object.__setattr__(
            inst0,
            "installment_additional_cash_due_vnd",
            inst0.installment_additional_cash_due_vnd + 10_000,
        )
        sched[0] = inst0
        object.__setattr__(mutated, "cashflow_schedule", sched)

        errors = check_scenario_sanity(mutated)
        codes = [err.code for err in errors]
        assert "INSTALLMENT_CASH_DUE_MISMATCH" in codes


# ===========================================================================
# 7. Sanity Check 6: Non-negative Amounts & Monotonic Timeline (INV-FIN-06)
# ===========================================================================
class TestSanityCheck6NonNegativeAndMonotonicity:
    """Verifies Sanity Check 6: All amounts >= 0, deposit credit <= equity, monotonic timeline."""

    def test_negative_top_level_vat_amount(self, canonical_chudong_result: ScenarioCalculationResult) -> None:
        mutated = canonical_chudong_result.model_copy(deep=True)
        object.__setattr__(mutated, "vat_amount", -1)

        errors = check_scenario_sanity(mutated)
        codes = [err.code for err in errors]
        assert "NEGATIVE_AMOUNT_DETECTED" in codes

    def test_negative_installment_amount_detected(self, canonical_chudong_result: ScenarioCalculationResult) -> None:
        mutated = canonical_chudong_result.model_copy(deep=True)
        sched = list(mutated.cashflow_schedule)
        inst0 = sched[0].model_copy(deep=True)
        object.__setattr__(inst0, "bank_disbursement_vnd", -10_000_000)
        sched[0] = inst0
        object.__setattr__(mutated, "cashflow_schedule", sched)

        errors = check_scenario_sanity(mutated)
        codes = [err.code for err in errors]
        assert "NEGATIVE_AMOUNT_DETECTED" in codes

    def test_deposit_credited_exceeds_equity_detected(
        self, canonical_chudong_result: ScenarioCalculationResult
    ) -> None:
        mutated = canonical_chudong_result.model_copy(deep=True)
        sched = list(mutated.cashflow_schedule)
        inst0 = sched[0].model_copy(deep=True)
        # Set deposit credited higher than customer equity
        object.__setattr__(
            inst0,
            "deposit_credited_vnd",
            inst0.customer_equity_paid_vnd + 50_000_000,
        )
        sched[0] = inst0
        object.__setattr__(mutated, "cashflow_schedule", sched)

        errors = check_scenario_sanity(mutated)
        codes = [err.code for err in errors]
        assert "DEPOSIT_CREDIT_INVALID" in codes

    def test_schedule_timeline_non_monotonic_detected(
        self, canonical_chudong_result: ScenarioCalculationResult
    ) -> None:
        mutated = canonical_chudong_result.model_copy(deep=True)
        sched = list(mutated.cashflow_schedule)
        inst1 = sched[1].model_copy(deep=True)
        inst0 = sched[0]
        # Make installment 2 date earlier than installment 1
        object.__setattr__(inst1, "due_date", inst0.due_date - timedelta(days=5))
        sched[1] = inst1
        object.__setattr__(mutated, "cashflow_schedule", sched)

        errors = check_scenario_sanity(mutated)
        codes = [err.code for err in errors]
        assert "SCHEDULE_DATE_NON_MONOTONIC" in codes


# ===========================================================================
# 8. Field-Level Error Envelope & Exception Tests (Task 3.2)
# ===========================================================================
class TestFieldLevelErrorEnvelopeAndException:
    """Verifies Task 3.2 field-level error envelope and FinancialSanityError behavior."""

    def test_raise_on_error_raises_financial_sanity_error(
        self, canonical_chudong_result: ScenarioCalculationResult
    ) -> None:
        mutated = canonical_chudong_result.model_copy(deep=True)
        object.__setattr__(mutated, "vat_amount", 100)

        with pytest.raises(FinancialSanityError) as exc_info:
            validate_scenario_calculation(mutated, raise_on_error=True)

        err = exc_info.value
        assert err.error_code == FINANCIAL_SANITY_FAILED_CODE
        assert err.status_code == 422
        assert len(err.field_errors) >= 1
        assert err.field_errors[0].code == "VAT_AMOUNT_MISMATCH"

        envelope = err.to_envelope()
        assert envelope["valid"] is False
        assert envelope["error_code"] == FINANCIAL_SANITY_FAILED_CODE
        assert envelope["status_code"] == 422
        assert isinstance(envelope["errors"], list)
        assert envelope["errors"][0]["code"] == "VAT_AMOUNT_MISMATCH"
        assert envelope["errors"][0]["field"] == "vat_amount"
        assert envelope["errors"][0]["expected_vnd"] == 350_000_000
        assert envelope["errors"][0]["actual_vnd"] == 100

    def test_raise_on_error_false_returns_calculation_failed_report(
        self, canonical_chudong_result: ScenarioCalculationResult
    ) -> None:
        mutated = canonical_chudong_result.model_copy(deep=True)
        object.__setattr__(mutated, "vat_amount", 100)

        report = validate_scenario_calculation(mutated, raise_on_error=False)
        assert report.is_valid is False
        assert report.status == CalculationStatus.CALCULATION_FAILED
        assert report.error_message is not None
        assert FINANCIAL_SANITY_FAILED_CODE in report.error_message
        assert len(report.field_errors) >= 1
        assert report.field_errors[0]["code"] == "VAT_AMOUNT_MISMATCH"

    def test_validate_pricing_results_multiple_scenarios_envelope(
        self,
        canonical_chudong_result: ScenarioCalculationResult,
        canonical_nhanh_result: ScenarioCalculationResult,
    ) -> None:
        mutated_nhanh = canonical_nhanh_result.model_copy(deep=True)
        object.__setattr__(mutated_nhanh, "net_price_before_vat", 0)

        with pytest.raises(FinancialSanityError) as exc_info:
            validate_pricing_results(
                [canonical_chudong_result, mutated_nhanh],
                raise_on_error=True,
            )

        err = exc_info.value
        assert err.error_code == FINANCIAL_SANITY_FAILED_CODE
        assert any(e.code == "NET_PRICE_NON_POSITIVE" for e in err.field_errors)


# ===========================================================================
# 9. Anti-Float Guard & SLA Performance Tests
# ===========================================================================
class TestAntiFloatGuardAndPerformance:
    """Verifies that floats are strictly prohibited and validation executes within SLA."""

    def test_forbid_float_on_vat_rate(self, canonical_chudong_result: ScenarioCalculationResult) -> None:
        with pytest.raises(TypeError, match="FLOAT_PROHIBITED"):
            # Passing float 0.1 instead of Decimal("0.1000")
            validate_scenario_calculation(
                canonical_chudong_result,
                vat_rate=0.1,  # type: ignore
            )

    def test_forbid_float_on_discount_cap(self, canonical_chudong_result: ScenarioCalculationResult) -> None:
        with pytest.raises(TypeError, match="FLOAT_PROHIBITED"):
            validate_scenario_calculation(
                canonical_chudong_result,
                max_discount_rate=0.35,  # type: ignore
            )

    def test_validation_performance_sla_under_20ms(
        self,
        canonical_chudong_result: ScenarioCalculationResult,
        canonical_nhanh_result: ScenarioCalculationResult,
        canonical_vay_result: ScenarioCalculationResult,
    ) -> None:
        scenarios = [
            canonical_chudong_result,
            canonical_nhanh_result,
            canonical_vay_result,
        ]
        # Warmup
        validate_pricing_results(scenarios)

        start = time.perf_counter()
        iterations = 50
        for _ in range(iterations):
            validate_pricing_results(scenarios)
        elapsed = (time.perf_counter() - start) / iterations * 1000  # ms

        # TD-4.4 SLA budget for validate_pricing_results is 20ms
        assert elapsed < 20.0, f"Validation latency {elapsed:.3f}ms exceeded 20ms SLA"
