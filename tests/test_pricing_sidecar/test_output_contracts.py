"""Unit tests for Pydantic Output Models, Invariant Gates, and Anti-Float Guard.

FCS v2.6 Reference: Section 4.5 & Section 7
TD-4.4 Reference: Section 4 (Tool & Governance Contracts)
"""

from datetime import date
from decimal import Decimal

import pytest
from pydantic import ValidationError

from src.pricing_sidecar.contracts import (
    CalculationStatus,
    CashflowInstallmentOutput,
    OptimizationObjective,
    PricingCalculationOutput,
    RecommendationResult,
    ScenarioCalculationResult,
    ScenarioType,
    ValidationReport,
)


# ===========================================================================
# 1. CashflowInstallmentOutput Tests
# ===========================================================================
class TestCashflowInstallmentOutput:
    """Test individual installment output verification and invariants."""

    def test_valid_installment_milestone_1(self) -> None:
        """TC-01 Milestone 1: 15% equity, 100M cọc, 477.5M nộp thêm."""
        inst = CashflowInstallmentOutput(
            installment_number=1,
            milestone_name="Đợt 1: Ký HĐMB",
            due_date=date(2026, 3, 15),
            customer_equity_paid_vnd=577_500_000,
            bank_disbursement_vnd=0,
            maintenance_fee_paid_vnd=0,
            installment_gross_obligation_vnd=577_500_000,
            installment_additional_cash_due_vnd=477_500_000,
            deposit_credited_vnd=100_000_000,
            is_handover_milestone=False,
            is_reconciliation_installment=False,
        )
        assert inst.installment_number == 1
        assert inst.installment_gross_obligation_vnd == 577_500_000
        assert inst.installment_additional_cash_due_vnd == 477_500_000

    def test_valid_installment_handover_with_kpbt(self) -> None:
        """Handover milestone: equity 20% + 100% KPBT."""
        inst = CashflowInstallmentOutput(
            installment_number=8,
            milestone_name="Đợt 8: Bàn giao nhà",
            due_date=date(2027, 6, 1),
            customer_equity_paid_vnd=770_000_000,
            bank_disbursement_vnd=0,
            maintenance_fee_paid_vnd=70_000_000,
            installment_gross_obligation_vnd=840_000_000,
            installment_additional_cash_due_vnd=840_000_000,
            deposit_credited_vnd=0,
            is_handover_milestone=True,
            is_reconciliation_installment=False,
        )
        assert inst.is_handover_milestone
        assert inst.maintenance_fee_paid_vnd == 70_000_000

    def test_gross_obligation_mismatch_rejected(self) -> None:
        """Gross obligation != equity + bank + kpbt raises ValueError."""
        with pytest.raises(ValueError, match="không khớp với tổng equity"):
            CashflowInstallmentOutput(
                installment_number=1,
                milestone_name="Đợt 1",
                due_date=date(2026, 3, 15),
                customer_equity_paid_vnd=500_000_000,
                bank_disbursement_vnd=0,
                maintenance_fee_paid_vnd=0,
                installment_gross_obligation_vnd=600_000_000,  # Mismatch!
                installment_additional_cash_due_vnd=500_000_000,
                deposit_credited_vnd=0,
            )

    def test_deposit_credited_exceeds_equity_rejected(self) -> None:
        """deposit_credited_vnd > customer_equity_paid_vnd raises ValueError."""
        with pytest.raises(ValueError, match="vượt quá customer_equity_paid_vnd"):
            CashflowInstallmentOutput(
                installment_number=1,
                milestone_name="Đợt 1",
                due_date=date(2026, 3, 15),
                customer_equity_paid_vnd=50_000_000,
                bank_disbursement_vnd=0,
                maintenance_fee_paid_vnd=0,
                installment_gross_obligation_vnd=50_000_000,
                installment_additional_cash_due_vnd=0,
                deposit_credited_vnd=100_000_000,  # Exceeds 50M!
            )

    def test_additional_cash_due_mismatch_rejected(self) -> None:
        """additional_cash_due != equity - deposit + kpbt raises ValueError."""
        with pytest.raises(ValueError, match="không khớp với số tiền thực nộp dự kiến"):
            CashflowInstallmentOutput(
                installment_number=1,
                milestone_name="Đợt 1",
                due_date=date(2026, 3, 15),
                customer_equity_paid_vnd=500_000_000,
                bank_disbursement_vnd=0,
                maintenance_fee_paid_vnd=0,
                installment_gross_obligation_vnd=500_000_000,
                installment_additional_cash_due_vnd=300_000_000,  # Expected 400M!
                deposit_credited_vnd=100_000_000,
            )

    def test_float_rejected_by_anti_float_guard(self) -> None:
        """Anti-Float guard rejects float in cashflow installment."""
        with pytest.raises(TypeError, match="FLOAT_PROHIBITED"):
            CashflowInstallmentOutput(
                installment_number=1,
                milestone_name="Đợt 1",
                due_date=date(2026, 3, 15),
                customer_equity_paid_vnd=500000000.0,  # float!
                bank_disbursement_vnd=0,
                maintenance_fee_paid_vnd=0,
                installment_gross_obligation_vnd=500000000,
                installment_additional_cash_due_vnd=500000000,
            )


@pytest.fixture
def valid_scenario_result() -> ScenarioCalculationResult:
    """Valid TC-01 Scenario Calculation Result for A-12-05."""
    return ScenarioCalculationResult(
        scenario_type=ScenarioType.STANDARD_PROGRESS,
        scenario_name="Phương án Tiến độ Chuẩn (PA-CHUDONG)",
        listed_price_vnd=3_500_000_000,
        fixed_discount_vnd=0,
        base_after_fixed_vnd=3_500_000_000,
        total_discount_rate=Decimal("0.0000"),
        percentage_discount_vnd=0,
        net_price_before_vat=3_500_000_000,
        vat_rate=Decimal("0.1000"),
        vat_amount=350_000_000,
        maintenance_fee_rate=Decimal("0.0200"),
        maintenance_fee_amount=70_000_000,
        final_contract_price=3_920_000_000,
        initial_gross_obligation_vnd=577_500_000,
        initial_cash_outflow_vnd=477_500_000,
        customer_cash_outflow_until_handover=3_725_000_000,
        total_benefit_value_vnd=0,
    )


# ===========================================================================
# 2. ScenarioCalculationResult Tests
# ===========================================================================
class TestScenarioCalculationResult:
    """Test scenario arithmetic invariants and cashflow reconciliation."""

    def test_valid_scenario_result_creation(
        self, valid_scenario_result: ScenarioCalculationResult
    ) -> None:
        assert valid_scenario_result.final_contract_price == 3_920_000_000
        assert valid_scenario_result.net_price_before_vat == 3_500_000_000

    def test_base_after_fixed_mismatch_rejected(self) -> None:
        """base_after_fixed_vnd != listed - fixed raises ValueError."""
        with pytest.raises(ValueError, match="base_after_fixed_vnd"):
            ScenarioCalculationResult(
                scenario_type=ScenarioType.STANDARD_PROGRESS,
                scenario_name="Test",
                listed_price_vnd=3_500_000_000,
                fixed_discount_vnd=100_000_000,
                base_after_fixed_vnd=3_500_000_000,  # Should be 3.4B!
                total_discount_rate=Decimal("0.0000"),
                percentage_discount_vnd=0,
                net_price_before_vat=3_500_000_000,
                vat_rate=Decimal("0.1000"),
                vat_amount=350_000_000,
                maintenance_fee_rate=Decimal("0.0200"),
                maintenance_fee_amount=70_000_000,
                final_contract_price=3_920_000_000,
                initial_gross_obligation_vnd=500_000_000,
                initial_cash_outflow_vnd=400_000_000,
                customer_cash_outflow_until_handover=3_500_000_000,
            )

    def test_net_price_mismatch_rejected(self) -> None:
        """net_price != base - percentage_discount raises ValueError."""
        with pytest.raises(ValueError, match="net_price_before_vat"):
            ScenarioCalculationResult(
                scenario_type=ScenarioType.STANDARD_PROGRESS,
                scenario_name="Test",
                listed_price_vnd=3_500_000_000,
                fixed_discount_vnd=0,
                base_after_fixed_vnd=3_500_000_000,
                total_discount_rate=Decimal("0.0800"),
                percentage_discount_vnd=280_000_000,
                net_price_before_vat=3_500_000_000,  # Should be 3.22B!
                vat_rate=Decimal("0.1000"),
                vat_amount=322_000_000,
                maintenance_fee_rate=Decimal("0.0200"),
                maintenance_fee_amount=64_400_000,
                final_contract_price=3_606_400_000,
                initial_gross_obligation_vnd=500_000_000,
                initial_cash_outflow_vnd=400_000_000,
                customer_cash_outflow_until_handover=3_500_000_000,
            )

    def test_contract_price_mismatch_rejected(self) -> None:
        """final_contract_price != Net + VAT + KPBT raises ValueError."""
        with pytest.raises(ValueError, match="final_contract_price"):
            ScenarioCalculationResult(
                scenario_type=ScenarioType.STANDARD_PROGRESS,
                scenario_name="Test",
                listed_price_vnd=3_500_000_000,
                fixed_discount_vnd=0,
                base_after_fixed_vnd=3_500_000_000,
                total_discount_rate=Decimal("0.0000"),
                percentage_discount_vnd=0,
                net_price_before_vat=3_500_000_000,
                vat_rate=Decimal("0.1000"),
                vat_amount=350_000_000,
                maintenance_fee_rate=Decimal("0.0200"),
                maintenance_fee_amount=70_000_000,
                final_contract_price=3_900_000_000,  # Expected 3,920,000,000!
                initial_gross_obligation_vnd=500_000_000,
                initial_cash_outflow_vnd=400_000_000,
                customer_cash_outflow_until_handover=3_500_000_000,
            )

    def test_cashflow_schedule_reconciliation_check(self) -> None:
        """Sum of cashflow schedule gross obligations must equal final_contract_price."""
        inst1 = CashflowInstallmentOutput(
            installment_number=1,
            milestone_name="Đợt 1",
            due_date=date(2026, 3, 15),
            customer_equity_paid_vnd=2_000_000_000,
            bank_disbursement_vnd=0,
            maintenance_fee_paid_vnd=0,
            installment_gross_obligation_vnd=2_000_000_000,
            installment_additional_cash_due_vnd=2_000_000_000,
        )
        inst2 = CashflowInstallmentOutput(
            installment_number=2,
            milestone_name="Đợt 2",
            due_date=date(2026, 6, 15),
            customer_equity_paid_vnd=1_850_000_000,
            bank_disbursement_vnd=0,
            maintenance_fee_paid_vnd=70_000_000,
            installment_gross_obligation_vnd=1_920_000_000,
            installment_additional_cash_due_vnd=1_920_000_000,
            is_handover_milestone=True,
            is_reconciliation_installment=True,
        )

        # Total = 2B + 1.92B = 3.92B == final_contract_price
        result = ScenarioCalculationResult(
            scenario_type=ScenarioType.STANDARD_PROGRESS,
            scenario_name="Test",
            listed_price_vnd=3_500_000_000,
            fixed_discount_vnd=0,
            base_after_fixed_vnd=3_500_000_000,
            total_discount_rate=Decimal("0.0000"),
            percentage_discount_vnd=0,
            net_price_before_vat=3_500_000_000,
            vat_rate=Decimal("0.1000"),
            vat_amount=350_000_000,
            maintenance_fee_rate=Decimal("0.0200"),
            maintenance_fee_amount=70_000_000,
            final_contract_price=3_920_000_000,
            initial_gross_obligation_vnd=2_000_000_000,
            initial_cash_outflow_vnd=2_000_000_000,
            customer_cash_outflow_until_handover=3_920_000_000,
            cashflow_schedule=[inst1, inst2],
        )
        assert len(result.cashflow_schedule) == 2

        # If inst2 has mismatch (e.g. 1.90B instead of 1.92B -> sum = 3.90B != 3.92B)
        inst2_mismatch = CashflowInstallmentOutput(
            installment_number=2,
            milestone_name="Đợt 2",
            due_date=date(2026, 6, 15),
            customer_equity_paid_vnd=1_830_000_000,
            bank_disbursement_vnd=0,
            maintenance_fee_paid_vnd=70_000_000,
            installment_gross_obligation_vnd=1_900_000_000,
            installment_additional_cash_due_vnd=1_900_000_000,
            is_handover_milestone=True,
            is_reconciliation_installment=True,
        )
        with pytest.raises(ValueError, match="Tổng nghĩa vụ dòng tiền"):
            ScenarioCalculationResult(
                scenario_type=ScenarioType.STANDARD_PROGRESS,
                scenario_name="Test",
                listed_price_vnd=3_500_000_000,
                fixed_discount_vnd=0,
                base_after_fixed_vnd=3_500_000_000,
                total_discount_rate=Decimal("0.0000"),
                percentage_discount_vnd=0,
                net_price_before_vat=3_500_000_000,
                vat_rate=Decimal("0.1000"),
                vat_amount=350_000_000,
                maintenance_fee_rate=Decimal("0.0200"),
                maintenance_fee_amount=70_000_000,
                final_contract_price=3_920_000_000,
                initial_gross_obligation_vnd=2_000_000_000,
                initial_cash_outflow_vnd=2_000_000_000,
                customer_cash_outflow_until_handover=3_920_000_000,
                cashflow_schedule=[inst1, inst2_mismatch],
            )


# ===========================================================================
# 3. ValidationReport Tests
# ===========================================================================
class TestValidationReport:
    """Test sanity checks validation report modeling."""

    def test_default_validation_report_is_valid(self) -> None:
        report = ValidationReport()
        assert report.is_valid
        assert report.status == CalculationStatus.VALID
        assert report.error_message is None
        assert report.field_errors == []

    def test_failed_validation_report(self) -> None:
        report = ValidationReport(
            is_valid=False,
            status=CalculationStatus.CALCULATION_FAILED,
            invariants_checked=["NET_PRICE_POSITIVE", "DUAL_CAP_CHECK"],
            error_message="Discount exceeded cap",
            field_errors=[{"field": "total_discount_rate", "error": "EXCEEDED_35_PCT"}],
        )
        assert not report.is_valid
        assert len(report.field_errors) == 1


# ===========================================================================
# 4. RecommendationResult Tests
# ===========================================================================
class TestRecommendationResult:
    """Test scenario recommendation modeling and tie-break reporting."""

    def test_recommendation_result_creation(self) -> None:
        rec = RecommendationResult(
            selected_objective=OptimizationObjective.MIN_NET_PRICE,
            recommended_scenario=ScenarioType.EARLY_95,
            comparison_summary=[
                {"scenario": "PA-NHANH", "net_price": 3_220_000_000},
                {"scenario": "PA-CHUDONG", "net_price": 3_500_000_000},
            ],
            quantitative_rationale="PA-NHANH has lowest net price (3,220,000,000 VND).",
            is_tie_break_applied=False,
        )
        assert rec.selected_objective == OptimizationObjective.MIN_NET_PRICE
        assert rec.recommended_scenario == ScenarioType.EARLY_95
        assert not rec.is_tie_break_applied

    def test_recommendation_result_with_tie_break(self) -> None:
        rec = RecommendationResult(
            selected_objective=OptimizationObjective.MIN_INITIAL_OUTFLOW,
            recommended_scenario=ScenarioType.STANDARD_PROGRESS,
            quantitative_rationale="PA-CHUDONG chosen by Tie-Break Rule TB-RULE-2026-CHUDONG-V1.",
            is_tie_break_applied=True,
            tiebreak_rule_id="TB-RULE-2026-CHUDONG-V1",
            tie_break_reason="Tie on initial cash outflow between PA-CHUDONG and PA-VAY (477,500,000 VND).",
        )
        assert rec.is_tie_break_applied
        assert rec.tiebreak_rule_id == "TB-RULE-2026-CHUDONG-V1"


# ===========================================================================
# 5. PricingCalculationOutput Tests
# ===========================================================================
class TestPricingCalculationOutput:
    """Test top-level calculation output envelope and hash validation."""

    def test_valid_output_envelope(
        self, valid_scenario_result: ScenarioCalculationResult
    ) -> None:
        rec = RecommendationResult(
            selected_objective=OptimizationObjective.MIN_NET_PRICE,
            recommended_scenario=ScenarioType.STANDARD_PROGRESS,
            quantitative_rationale="Optimal progress payment.",
        )
        output = PricingCalculationOutput(
            calculation_timestamp="2026-09-23T14:00:00Z",
            unit_code="A-12-05",
            scenario_results=[valid_scenario_result],
            recommended_result=rec,
            canonical_snapshot_hash="f" * 64,
        )
        assert output.spec_version == "2.6"
        assert output.unit_code == "A-12-05"
        assert len(output.scenario_results) == 1
        assert output.validation_report.is_valid

    def test_recommended_scenario_must_exist_in_scenarios(
        self, valid_scenario_result: ScenarioCalculationResult
    ) -> None:
        """recommended_scenario must be present in scenario_results."""
        rec_non_existent = RecommendationResult(
            selected_objective=OptimizationObjective.MIN_NET_PRICE,
            recommended_scenario=ScenarioType.BANK_LOAN_HTLS,  # Not in scenario_results!
            quantitative_rationale="Non-existent scenario recommendation.",
        )
        with pytest.raises(ValueError, match="không nằm trong danh sách scenario_results"):
            PricingCalculationOutput(
                calculation_timestamp="2026-09-23T14:00:00Z",
                unit_code="A-12-05",
                scenario_results=[valid_scenario_result],  # only STANDARD_PROGRESS
                recommended_result=rec_non_existent,
                canonical_snapshot_hash="f" * 64,
            )

    def test_invalid_snapshot_hash_length_rejected(
        self, valid_scenario_result: ScenarioCalculationResult
    ) -> None:
        """canonical_snapshot_hash must be exactly 64 hex characters."""
        with pytest.raises(ValidationError):
            PricingCalculationOutput(
                calculation_timestamp="2026-09-23T14:00:00Z",
                unit_code="A-12-05",
                scenario_results=[valid_scenario_result],
                canonical_snapshot_hash="tooshort",
            )
