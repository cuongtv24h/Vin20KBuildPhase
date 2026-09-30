"""Negative Test Suite for Financial Validation Gate and Sanity Checks (Task 4.5).

FCS v2.6 Reference: Section 9 (Cổng kiểm duyệt Sanity Gate - 6 Sanity Checks)
TD-4.1 Reference: Section 3.2 (Hardened Worker Sanity Verification)
TD-4.4 Reference: Section 3.3 (Financial Sanity Failed Error 422 Envelope)
Implement Plan Detail Reference: Section 7.3 (D2-3 Financial Validation Gate)

Verifies that the validation gate strictly blocks all corrupted, malicious,
or mathematically inconsistent calculation outputs with code FINANCIAL_SANITY_FAILED.
"""

from datetime import date, timedelta
from decimal import Decimal

import pytest

from src.pricing_sidecar.contracts import (
    CalculationStatus,
    ScenarioCalculationResult,
    ScenarioType,
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


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture
def baseline_chudong() -> ScenarioCalculationResult:
    """Standard valid PA-CHUDONG calculation result for apartment testing."""
    return calculate_pa_chudong(
        listed_price_vnd=3_500_000_000,
        deposit_date=date(2026, 3, 15),
        deposit_amount_vnd=100_000_000,
    )


@pytest.fixture
def baseline_nhanh() -> ScenarioCalculationResult:
    """Standard valid PA-NHANH calculation result for apartment testing."""
    return calculate_pa_nhanh(
        listed_price_vnd=3_500_000_000,
        deposit_date=date(2026, 3, 15),
        deposit_amount_vnd=100_000_000,
    )


@pytest.fixture
def baseline_vay() -> ScenarioCalculationResult:
    """Standard valid PA-VAY calculation result for apartment testing."""
    return calculate_pa_vay(
        listed_price_vnd=3_500_000_000,
        deposit_date=date(2026, 3, 15),
        deposit_amount_vnd=100_000_000,
    )


# ===========================================================================
# 1. Sanity Check 1: Net Price Boundary Gate (INV-FIN-01)
# ===========================================================================
class TestSanityGateINV01NetPriceBounds:
    """Verifies that the gate strictly forbids Net Price <= 0 or Net Price > Listed Price."""

    def test_net_price_zero_blocked(self, baseline_chudong: ScenarioCalculationResult) -> None:
        corrupted = baseline_chudong.model_copy(deep=True)
        object.__setattr__(corrupted, "net_price_before_vat", 0)

        errors = check_scenario_sanity(corrupted)
        codes = [e.code for e in errors]
        assert "NET_PRICE_NON_POSITIVE" in codes

        # Verify raise_on_error raises FinancialSanityError
        with pytest.raises(FinancialSanityError) as exc_info:
            validate_scenario_calculation(corrupted, raise_on_error=True)
        assert exc_info.value.error_code == FINANCIAL_SANITY_FAILED_CODE
        assert exc_info.value.status_code == 422

    def test_net_price_negative_blocked(self, baseline_chudong: ScenarioCalculationResult) -> None:
        corrupted = baseline_chudong.model_copy(deep=True)
        object.__setattr__(corrupted, "net_price_before_vat", -50_000_000)

        errors = check_scenario_sanity(corrupted)
        codes = [e.code for e in errors]
        assert "NET_PRICE_NON_POSITIVE" in codes

    def test_net_price_exceeds_listed_price_blocked(self, baseline_chudong: ScenarioCalculationResult) -> None:
        corrupted = baseline_chudong.model_copy(deep=True)
        # Listed price is 3.5B, tamper net price to 3.6B
        object.__setattr__(corrupted, "net_price_before_vat", 3_600_000_000)

        errors = check_scenario_sanity(corrupted, listed_price_vnd=3_500_000_000)
        codes = [e.code for e in errors]
        assert "NET_PRICE_EXCEEDS_LISTED" in codes

        target_err = next(e for e in errors if e.code == "NET_PRICE_EXCEEDS_LISTED")
        assert target_err.expected_vnd == 3_500_000_000
        assert target_err.actual_vnd == 3_600_000_000


# ===========================================================================
# 2. Sanity Check 2: Dual Discount Cap Compliance Gate (INV-FIN-02)
# ===========================================================================
class TestSanityGateINV02DualDiscountCap:
    """Verifies that percentage discount <= 35% and total money discount <= 40% listed."""

    def test_percentage_discount_cap_exceeded_blocked(self, baseline_nhanh: ScenarioCalculationResult) -> None:
        corrupted = baseline_nhanh.model_copy(deep=True)
        # Cap is 35.00%, tamper to 35.50%
        object.__setattr__(corrupted, "total_discount_rate", Decimal("0.3550"))

        errors = check_scenario_sanity(corrupted, max_discount_rate=Decimal("0.3500"))
        codes = [e.code for e in errors]
        assert "PERCENTAGE_DISCOUNT_CAP_EXCEEDED" in codes

        target_err = next(e for e in errors if e.code == "PERCENTAGE_DISCOUNT_CAP_EXCEEDED")
        assert target_err.expected_rate == Decimal("0.3500")
        assert target_err.actual_rate == Decimal("0.3550")

    def test_total_discount_money_cap_exceeded_blocked(self, baseline_chudong: ScenarioCalculationResult) -> None:
        corrupted = baseline_chudong.model_copy(deep=True)
        # Listed price: 3.5B -> 40% max total discount is 1.4B. Tamper fixed discount to 1.45B.
        object.__setattr__(corrupted, "fixed_discount_vnd", 1_450_000_000)

        errors = check_scenario_sanity(
            corrupted,
            listed_price_vnd=3_500_000_000,
            max_total_discount_cap_rate=Decimal("0.4000"),
        )
        codes = [e.code for e in errors]
        assert "TOTAL_DISCOUNT_CAP_EXCEEDED" in codes

        target_err = next(e for e in errors if e.code == "TOTAL_DISCOUNT_CAP_EXCEEDED")
        assert target_err.expected_vnd == 1_400_000_000
        assert target_err.actual_vnd == 1_450_000_000


# ===========================================================================
# 3. Sanity Check 3: Tax & Fee Rate Consistency Gate (INV-FIN-03)
# ===========================================================================
class TestSanityGateINV03TaxAndFeeIntegrity:
    """Verifies that VAT and KPBT strictly match policy snapshot rates (zero tolerance for off-by-one)."""

    def test_vat_off_by_one_vnd_blocked(self, baseline_chudong: ScenarioCalculationResult) -> None:
        corrupted = baseline_chudong.model_copy(deep=True)
        expected_vat = baseline_chudong.vat_amount
        object.__setattr__(corrupted, "vat_amount", expected_vat + 1)

        errors = check_scenario_sanity(corrupted)
        codes = [e.code for e in errors]
        assert "VAT_AMOUNT_MISMATCH" in codes

        target_err = next(e for e in errors if e.code == "VAT_AMOUNT_MISMATCH")
        assert target_err.expected_vnd == expected_vat
        assert target_err.actual_vnd == expected_vat + 1

    def test_kpbt_off_by_one_vnd_blocked(self, baseline_chudong: ScenarioCalculationResult) -> None:
        corrupted = baseline_chudong.model_copy(deep=True)
        expected_kpbt = baseline_chudong.maintenance_fee_amount
        object.__setattr__(corrupted, "maintenance_fee_amount", expected_kpbt - 1)

        errors = check_scenario_sanity(corrupted)
        codes = [e.code for e in errors]
        assert "KPBT_AMOUNT_MISMATCH" in codes

        target_err = next(e for e in errors if e.code == "KPBT_AMOUNT_MISMATCH")
        assert target_err.expected_vnd == expected_kpbt
        assert target_err.actual_vnd == expected_kpbt - 1


# ===========================================================================
# 4. Sanity Check 4: Contract Price Exact Sum Gate (INV-FIN-04)
# ===========================================================================
class TestSanityGateINV04ContractPriceBalance:
    """Verifies that final_contract_price strictly equals Net + VAT + KPBT."""

    def test_contract_price_overstated_blocked(self, baseline_vay: ScenarioCalculationResult) -> None:
        corrupted = baseline_vay.model_copy(deep=True)
        correct_contract = baseline_vay.final_contract_price
        object.__setattr__(corrupted, "final_contract_price", correct_contract + 10_000)

        errors = check_scenario_sanity(corrupted)
        codes = [e.code for e in errors]
        assert "CONTRACT_PRICE_MISMATCH" in codes

        target_err = next(e for e in errors if e.code == "CONTRACT_PRICE_MISMATCH")
        assert target_err.expected_vnd == correct_contract
        assert target_err.actual_vnd == correct_contract + 10_000

    def test_contract_price_understated_blocked(self, baseline_vay: ScenarioCalculationResult) -> None:
        corrupted = baseline_vay.model_copy(deep=True)
        correct_contract = baseline_vay.final_contract_price
        object.__setattr__(corrupted, "final_contract_price", correct_contract - 1)

        errors = check_scenario_sanity(corrupted)
        codes = [e.code for e in errors]
        assert "CONTRACT_PRICE_MISMATCH" in codes


# ===========================================================================
# 5. Sanity Check 5: Cashflow Reconciliation Completeness Gate (INV-FIN-05)
# ===========================================================================
class TestSanityGateINV05CashflowReconciliation:
    """Verifies that schedule sum equals contract price, and each installment balances perfectly."""

    def test_payment_schedule_sum_mismatch_blocked(self, baseline_chudong: ScenarioCalculationResult) -> None:
        corrupted = baseline_chudong.model_copy(deep=True)
        sched = list(corrupted.cashflow_schedule)
        inst0 = sched[0].model_copy(deep=True)
        object.__setattr__(
            inst0,
            "installment_gross_obligation_vnd",
            inst0.installment_gross_obligation_vnd + 100,
        )
        sched[0] = inst0
        object.__setattr__(corrupted, "cashflow_schedule", sched)

        errors = check_scenario_sanity(corrupted)
        codes = [e.code for e in errors]
        assert "PAYMENT_SCHEDULE_SUM_MISMATCH" in codes

    def test_installment_gross_components_mismatch_blocked(self, baseline_chudong: ScenarioCalculationResult) -> None:
        corrupted = baseline_chudong.model_copy(deep=True)
        sched = list(corrupted.cashflow_schedule)
        inst0 = sched[0].model_copy(deep=True)
        object.__setattr__(
            inst0,
            "customer_equity_paid_vnd",
            inst0.customer_equity_paid_vnd - 50_000,
        )
        sched[0] = inst0
        object.__setattr__(corrupted, "cashflow_schedule", sched)

        errors = check_scenario_sanity(corrupted)
        codes = [e.code for e in errors]
        assert "INSTALLMENT_GROSS_MISMATCH" in codes

    def test_installment_additional_cash_due_mismatch_blocked(
        self, baseline_chudong: ScenarioCalculationResult
    ) -> None:
        corrupted = baseline_chudong.model_copy(deep=True)
        sched = list(corrupted.cashflow_schedule)
        inst0 = sched[0].model_copy(deep=True)
        object.__setattr__(
            inst0,
            "installment_additional_cash_due_vnd",
            inst0.installment_additional_cash_due_vnd + 10_000,
        )
        sched[0] = inst0
        object.__setattr__(corrupted, "cashflow_schedule", sched)

        errors = check_scenario_sanity(corrupted)
        codes = [e.code for e in errors]
        assert "INSTALLMENT_CASH_DUE_MISMATCH" in codes


# ===========================================================================
# 6. Sanity Check 6: Non-negativity & Timeline Monotonicity Gate (INV-FIN-06)
# ===========================================================================
class TestSanityGateINV06NonNegativityAndTimeline:
    """Verifies non-negative amounts, deposit credit constraints, and monotonic progression."""

    def test_negative_fixed_discount_blocked(self, baseline_chudong: ScenarioCalculationResult) -> None:
        corrupted = baseline_chudong.model_copy(deep=True)
        object.__setattr__(corrupted, "fixed_discount_vnd", -1)

        errors = check_scenario_sanity(corrupted)
        codes = [e.code for e in errors]
        assert "NEGATIVE_AMOUNT_DETECTED" in codes

    def test_negative_vat_blocked(self, baseline_chudong: ScenarioCalculationResult) -> None:
        corrupted = baseline_chudong.model_copy(deep=True)
        object.__setattr__(corrupted, "vat_amount", -10_000)

        errors = check_scenario_sanity(corrupted)
        codes = [e.code for e in errors]
        assert "NEGATIVE_AMOUNT_DETECTED" in codes

    def test_negative_installment_amount_blocked(self, baseline_chudong: ScenarioCalculationResult) -> None:
        corrupted = baseline_chudong.model_copy(deep=True)
        sched = list(corrupted.cashflow_schedule)
        inst0 = sched[0].model_copy(deep=True)
        object.__setattr__(inst0, "bank_disbursement_vnd", -500_000)
        sched[0] = inst0
        object.__setattr__(corrupted, "cashflow_schedule", sched)

        errors = check_scenario_sanity(corrupted)
        codes = [e.code for e in errors]
        assert "NEGATIVE_AMOUNT_DETECTED" in codes

    def test_deposit_credit_exceeds_equity_blocked(self, baseline_chudong: ScenarioCalculationResult) -> None:
        corrupted = baseline_chudong.model_copy(deep=True)
        sched = list(corrupted.cashflow_schedule)
        inst0 = sched[0].model_copy(deep=True)
        object.__setattr__(
            inst0,
            "deposit_credited_vnd",
            inst0.customer_equity_paid_vnd + 10_000_000,
        )
        sched[0] = inst0
        object.__setattr__(corrupted, "cashflow_schedule", sched)

        errors = check_scenario_sanity(corrupted)
        codes = [e.code for e in errors]
        assert "DEPOSIT_CREDIT_INVALID" in codes

    def test_regressing_due_date_blocked(self, baseline_chudong: ScenarioCalculationResult) -> None:
        corrupted = baseline_chudong.model_copy(deep=True)
        assert len(corrupted.cashflow_schedule) >= 2
        sched = list(corrupted.cashflow_schedule)
        inst1 = sched[1].model_copy(deep=True)
        d1 = sched[0].due_date
        object.__setattr__(inst1, "due_date", d1 - timedelta(days=1))
        sched[1] = inst1
        object.__setattr__(corrupted, "cashflow_schedule", sched)

        errors = check_scenario_sanity(corrupted)
        codes = [e.code for e in errors]
        assert "SCHEDULE_DATE_NON_MONOTONIC" in codes

    def test_regressing_installment_number_blocked(self, baseline_chudong: ScenarioCalculationResult) -> None:
        corrupted = baseline_chudong.model_copy(deep=True)
        sched = list(corrupted.cashflow_schedule)
        inst1 = sched[1].model_copy(deep=True)
        object.__setattr__(inst1, "installment_number", 1)
        sched[1] = inst1
        object.__setattr__(corrupted, "cashflow_schedule", sched)

        errors = check_scenario_sanity(corrupted)
        codes = [e.code for e in errors]
        assert "SCHEDULE_NUMBER_NON_MONOTONIC" in codes


# ===========================================================================
# 7. Composite Violations & Envelope Verification Gate
# ===========================================================================
class TestSanityGateCompositeAndEnvelopeHandling:
    """Verifies multiple concurrent violations collection and RFC 9457 / TD-4.4 envelope outputs."""

    def test_multiple_simultaneous_violations_collected(self, baseline_chudong: ScenarioCalculationResult) -> None:
        """Inject 4 distinct corruptions and ensure all are reported without early termination."""
        corrupted = baseline_chudong.model_copy(deep=True)
        object.__setattr__(corrupted, "net_price_before_vat", 4_000_000_000)  # Violates INV-FIN-01
        object.__setattr__(corrupted, "vat_amount", corrupted.vat_amount + 999)  # Violates INV-FIN-03
        object.__setattr__(corrupted, "final_contract_price", 9_999_999_999)  # Violates INV-FIN-04

        sched = list(corrupted.cashflow_schedule)
        inst1 = sched[1].model_copy(deep=True)
        object.__setattr__(inst1, "due_date", sched[0].due_date - timedelta(days=5))  # Violates INV-FIN-06
        sched[1] = inst1
        object.__setattr__(corrupted, "cashflow_schedule", sched)

        errors = check_scenario_sanity(corrupted, listed_price_vnd=3_500_000_000)
        codes = {e.code for e in errors}

        assert "NET_PRICE_EXCEEDS_LISTED" in codes
        assert "VAT_AMOUNT_MISMATCH" in codes
        assert "CONTRACT_PRICE_MISMATCH" in codes
        assert "SCHEDULE_DATE_NON_MONOTONIC" in codes
        assert len(errors) >= 4

    def test_financial_sanity_error_to_envelope(self, baseline_chudong: ScenarioCalculationResult) -> None:
        """Verify FinancialSanityError produces the exact RFC 9457 / TD-4.4 envelope."""
        corrupted = baseline_chudong.model_copy(deep=True)
        object.__setattr__(corrupted, "fixed_discount_vnd", -5_000)

        with pytest.raises(FinancialSanityError) as exc_info:
            validate_scenario_calculation(corrupted, raise_on_error=True)

        envelope = exc_info.value.to_envelope()
        assert envelope["valid"] is False
        assert envelope["error_code"] == FINANCIAL_SANITY_FAILED_CODE
        assert envelope["status_code"] == 422
        assert "FINANCIAL_SANITY_FAILED" in envelope["message"]
        assert len(envelope["errors"]) >= 1
        assert envelope["errors"][0]["code"] == "NEGATIVE_AMOUNT_DETECTED"

    def test_safe_report_mode_returns_calculation_failed(self, baseline_nhanh: ScenarioCalculationResult) -> None:
        """With raise_on_error=False, returns ValidationReport with status CALCULATION_FAILED."""
        corrupted = baseline_nhanh.model_copy(deep=True)
        object.__setattr__(corrupted, "vat_amount", baseline_nhanh.vat_amount + 123)

        report = validate_scenario_calculation(corrupted, raise_on_error=False)
        assert report.is_valid is False
        assert report.status == CalculationStatus.CALCULATION_FAILED
        assert report.error_message is not None
        assert len(report.field_errors) >= 1
        assert report.invariants_checked == STANDARD_SANITY_INVARIANTS

    def test_validate_pricing_results_isolates_corrupted_scenario(
        self,
        baseline_chudong: ScenarioCalculationResult,
        baseline_nhanh: ScenarioCalculationResult,
        baseline_vay: ScenarioCalculationResult,
    ) -> None:
        """Top-level validate_pricing_results identifies corrupted scenario in a multi-scenario batch."""
        corrupted_nhanh = baseline_nhanh.model_copy(deep=True)
        object.__setattr__(corrupted_nhanh, "maintenance_fee_amount", 0)  # KPBT must be 2%

        scenario_batch = [baseline_chudong, corrupted_nhanh, baseline_vay]

        report = validate_pricing_results(scenario_batch, raise_on_error=False)
        assert report.is_valid is False
        assert report.status == CalculationStatus.CALCULATION_FAILED
        assert any(
            err.get("scenario_type") == ScenarioType.EARLY_95 or err.get("code") == "KPBT_AMOUNT_MISMATCH"
            for err in report.field_errors
        )
