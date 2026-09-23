"""Unit tests for Pydantic Input Models, 8 Invariant Validators, and Scenario Builders.

FCS v2.6 Reference: Sections 3, 4, 7, 8
TD-4.2 Reference: Section 3.4 (Canonical Payment Scenarios)
"""

from datetime import date
from decimal import Decimal

import pytest
from pydantic import ValidationError

from src.pricing_sidecar.contracts import (
    BenefitApplicationRule,
    BenefitCategory,
    BenefitType,
    CalculationBase,
    InstallmentRule,
    PaymentScenarioConfig,
    PricingCalculationInput,
    ScenarioType,
    StructuredPolicyReference,
    ValuationStatus,
    create_canonical_scenario_config,
    create_pa_chudong_config,
    create_pa_nhanh_config,
    create_pa_vay_config,
)


@pytest.fixture
def sample_policy_ref() -> StructuredPolicyReference:
    """Fixture providing a valid StructuredPolicyReference."""
    return StructuredPolicyReference(
        policy_id="POL-2026-VLF-GEN",
        policy_version="v2.6",
        clause_id="Điều 4.2 Khoản 1",
        page_number=12,
        source_file_sha256="a" * 64,
        effective_from=date(2026, 1, 1),
        effective_to=date(2026, 12, 31),
    )


# ===========================================================================
# 1. Anti-Float Guard in Models
# ===========================================================================
class TestAntiFloatGuardInModels:
    """Ensure any float input to Pydantic models triggers TypeError immediately."""

    def test_installment_rule_rejects_float_ratio(self) -> None:
        with pytest.raises(TypeError, match="FLOAT_PROHIBITED"):
            InstallmentRule(
                installment_number=1,
                milestone_name="Đợt 1",
                days_from_deposit=15,
                customer_equity_ratio=0.15,  # float!
            )

    def test_payment_scenario_config_rejects_float_rate(self) -> None:
        with pytest.raises(TypeError, match="FLOAT_PROHIBITED"):
            PaymentScenarioConfig(
                scenario_type=ScenarioType.STANDARD_PROGRESS,
                scenario_name="Test",
                installment_rules=[],
                bank_financing_rate=0.0,  # float!
            )

    def test_benefit_rule_rejects_float_discount_rate(
        self, sample_policy_ref: StructuredPolicyReference
    ) -> None:
        with pytest.raises(TypeError, match="FLOAT_PROHIBITED"):
            BenefitApplicationRule(
                benefit_id="BEN-01",
                benefit_type=BenefitType.PERCENTAGE,
                category=BenefitCategory.CASH_DISCOUNT,
                discount_rate=0.02,  # float!
                valuation_status=ValuationStatus.APPROVED,
                price_deduction_authorized=True,
                source_policy_clause=sample_policy_ref,
            )

    def test_pricing_input_rejects_float_vat(self) -> None:
        with pytest.raises(TypeError, match="FLOAT_PROHIBITED"):
            PricingCalculationInput(
                unit_code="A-12-05",
                deposit_date=date(2026, 3, 1),
                contract_signing_date=date(2026, 3, 15),
                listed_price_vnd=3_500_000_000,
                resolved_policy_snapshot_id="SNP-001",
                source_policy_hash="b" * 64,
                tax_vat_rate=0.10,  # float!
            )


# ===========================================================================
# 2. StructuredPolicyReference
# ===========================================================================
class TestStructuredPolicyReference:
    """Test policy cryptographic coordinate validation."""

    def test_valid_reference(self, sample_policy_ref: StructuredPolicyReference) -> None:
        assert sample_policy_ref.policy_id == "POL-2026-VLF-GEN"
        assert sample_policy_ref.page_number == 12
        assert len(sample_policy_ref.source_file_sha256) == 64

    def test_invalid_dates_rejected(self) -> None:
        with pytest.raises(ValueError, match="cannot be after effective_to"):
            StructuredPolicyReference(
                policy_id="POL-2026",
                policy_version="v1.0",
                clause_id="Clause 1",
                page_number=1,
                source_file_sha256="c" * 64,
                effective_from=date(2026, 12, 31),
                effective_to=date(2026, 1, 1),
            )

    def test_invalid_sha256_hash_length(self) -> None:
        with pytest.raises(ValidationError):
            StructuredPolicyReference(
                policy_id="POL-2026",
                policy_version="v1.0",
                clause_id="Clause 1",
                page_number=1,
                source_file_sha256="tooshort",
                effective_from=date(2026, 1, 1),
                effective_to=date(2026, 12, 31),
            )


# ===========================================================================
# 3. InstallmentRule
# ===========================================================================
class TestInstallmentRule:
    """Test installment schedule rule modeling."""

    def test_valid_rule_and_payment_ratio_property(self) -> None:
        rule = InstallmentRule(
            installment_number=1,
            milestone_name="Ký HĐMB",
            days_from_deposit=15,
            customer_equity_ratio=Decimal("0.1500"),
            bank_disbursement_ratio=Decimal("0.0000"),
            maintenance_fee_ratio=Decimal("0.0000"),
        )
        assert rule.installment_number == 1
        assert rule.payment_ratio == Decimal("0.1500")
        assert not rule.is_handover
        assert not rule.is_reconciliation

    def test_negative_days_rejected(self) -> None:
        with pytest.raises(ValidationError):
            InstallmentRule(
                installment_number=1,
                milestone_name="Ký HĐMB",
                days_from_deposit=-5,
            )

    def test_invalid_installment_number_bounds(self) -> None:
        with pytest.raises(ValidationError):
            InstallmentRule(
                installment_number=0,  # ge=1
                milestone_name="Mốc 0",
                days_from_deposit=0,
            )
        with pytest.raises(ValidationError):
            InstallmentRule(
                installment_number=31,  # le=30
                milestone_name="Mốc 31",
                days_from_deposit=1000,
            )


# ===========================================================================
# 4. PaymentScenarioConfig: 8 Invariants Validation
# ===========================================================================
class TestPaymentScenarioConfigInvariants:
    """Thoroughly test all 8 financial invariants of PaymentScenarioConfig."""

    def test_invariant_1_funding_rate_sum_must_equal_one(self) -> None:
        """Invariant 1: bank_financing_rate + customer_equity_rate must equal 1.0000."""
        valid_chudong = create_pa_chudong_config()
        with pytest.raises(ValueError, match="phải bằng 1.0000"):
            PaymentScenarioConfig(
                scenario_type=ScenarioType.STANDARD_PROGRESS,
                scenario_name="Invalid Funding",
                installment_rules=valid_chudong.installment_rules,
                bank_financing_rate=Decimal("0.0000"),
                customer_equity_rate=Decimal("0.9000"),  # Sum = 0.9 != 1.0!
            )

    def test_invariant_2_installment_rules_cannot_be_empty(self) -> None:
        """Invariant 2: installment_rules cannot be empty."""
        with pytest.raises(ValueError, match="không được rỗng"):
            PaymentScenarioConfig(
                scenario_type=ScenarioType.STANDARD_PROGRESS,
                scenario_name="Empty Rules",
                installment_rules=[],
                bank_financing_rate=Decimal("0.0000"),
                customer_equity_rate=Decimal("1.0000"),
            )

    def test_invariant_3_reconciliation_must_be_exactly_one(self) -> None:
        """Invariant 3: Exactly 1 reconciliation installment."""
        base_chudong = create_pa_chudong_config()

        # Case A: 0 reconciliation
        rules_no_recon = [
            r.model_copy(update={"is_reconciliation": False})
            for r in base_chudong.installment_rules
        ]
        with pytest.raises(ValueError, match="DUY NHẤT 1 đợt reconciliation"):
            PaymentScenarioConfig(
                scenario_type=ScenarioType.STANDARD_PROGRESS,
                scenario_name="No Recon",
                installment_rules=rules_no_recon,
                bank_financing_rate=Decimal("0.0000"),
                customer_equity_rate=Decimal("1.0000"),
            )

        # Case B: 2 reconciliations
        rules_two_recon = [
            r.model_copy(update={"is_reconciliation": True}) if r.installment_number in (8, 9) else r
            for r in base_chudong.installment_rules
        ]
        with pytest.raises(ValueError, match="DUY NHẤT 1 đợt reconciliation"):
            PaymentScenarioConfig(
                scenario_type=ScenarioType.STANDARD_PROGRESS,
                scenario_name="Two Recon",
                installment_rules=rules_two_recon,
                bank_financing_rate=Decimal("0.0000"),
                customer_equity_rate=Decimal("1.0000"),
            )

    def test_invariant_4_handover_must_be_exactly_one(self) -> None:
        """Invariant 4: Exactly 1 handover installment."""
        base_chudong = create_pa_chudong_config()

        # Case A: 0 handover
        rules_no_handover = [
            r.model_copy(update={"is_handover": False})
            for r in base_chudong.installment_rules
        ]
        with pytest.raises(ValueError, match="DUY NHẤT 1 đợt bàn giao nhà"):
            PaymentScenarioConfig(
                scenario_type=ScenarioType.STANDARD_PROGRESS,
                scenario_name="No Handover",
                installment_rules=rules_no_handover,
                bank_financing_rate=Decimal("0.0000"),
                customer_equity_rate=Decimal("1.0000"),
            )

        # Case B: 2 handovers
        rules_two_handover = [
            r.model_copy(update={"is_handover": True}) if r.installment_number in (7, 8) else r
            for r in base_chudong.installment_rules
        ]
        with pytest.raises(ValueError, match="DUY NHẤT 1 đợt bàn giao nhà"):
            PaymentScenarioConfig(
                scenario_type=ScenarioType.STANDARD_PROGRESS,
                scenario_name="Two Handover",
                installment_rules=rules_two_handover,
                bank_financing_rate=Decimal("0.0000"),
                customer_equity_rate=Decimal("1.0000"),
            )

    def test_invariant_5_consecutive_installment_numbering(self) -> None:
        """Invariant 5: installment_number must be strictly consecutive 1..N."""
        base_chudong = create_pa_chudong_config()
        # Change installment 9 to 10 (gap: [1, 2, 3, 4, 5, 6, 7, 8, 10])
        rules_with_gap = [
            r.model_copy(update={"installment_number": 10}) if r.installment_number == 9 else r
            for r in base_chudong.installment_rules
        ]
        with pytest.raises(ValueError, match="phải liên tục từ 1 đến"):
            PaymentScenarioConfig(
                scenario_type=ScenarioType.STANDARD_PROGRESS,
                scenario_name="Gap in numbering",
                installment_rules=rules_with_gap,
                bank_financing_rate=Decimal("0.0000"),
                customer_equity_rate=Decimal("1.0000"),
            )

    def test_invariant_6_timeline_monotonicity(self) -> None:
        """Invariant 6: days_from_deposit must be monotonic non-decreasing."""
        base_chudong = create_pa_chudong_config()
        # Flip days: đợt 3 (120 ngày) đổi thành 50 ngày (trước đợt 2: 60 ngày)
        rules_non_mono = [
            r.model_copy(update={"days_from_deposit": 50}) if r.installment_number == 3 else r
            for r in base_chudong.installment_rules
        ]
        with pytest.raises(ValueError, match="phải đơn điệu không giảm"):
            PaymentScenarioConfig(
                scenario_type=ScenarioType.STANDARD_PROGRESS,
                scenario_name="Non monotonic timeline",
                installment_rules=rules_non_mono,
                bank_financing_rate=Decimal("0.0000"),
                customer_equity_rate=Decimal("1.0000"),
            )

    def test_invariant_7_total_maintenance_fee_ratio_must_be_one(self) -> None:
        """Invariant 7: sum of maintenance_fee_ratio across all rules must equal 1.0000."""
        base_chudong = create_pa_chudong_config()
        rules_bad_kpbt = [
            r.model_copy(update={"maintenance_fee_ratio": Decimal("0.9800")})
            if r.installment_number == 8
            else r
            for r in base_chudong.installment_rules
        ]
        with pytest.raises(ValueError, match="Tổng maintenance_fee_ratio phải bằng 1.0000"):
            PaymentScenarioConfig(
                scenario_type=ScenarioType.STANDARD_PROGRESS,
                scenario_name="Bad KPBT",
                installment_rules=rules_bad_kpbt,
                bank_financing_rate=Decimal("0.0000"),
                customer_equity_rate=Decimal("1.0000"),
            )

    def test_invariant_8_non_recon_allocations_must_not_exceed_caps(self) -> None:
        """Invariant 8: non-reconciliation equity and bank ratios must not exceed configured caps."""
        base_chudong = create_pa_chudong_config()
        # Raise non-recon equity beyond 1.0000 (e.g. đợt 1 from 0.15 to 0.25 -> total non-recon = 1.05 > 1.00)
        rules_exceed_equity = [
            r.model_copy(update={"customer_equity_ratio": Decimal("0.2500")})
            if r.installment_number == 1
            else r
            for r in base_chudong.installment_rules
        ]
        with pytest.raises(ValueError, match="vượt quá trần cấu hình"):
            PaymentScenarioConfig(
                scenario_type=ScenarioType.STANDARD_PROGRESS,
                scenario_name="Exceed Equity",
                installment_rules=rules_exceed_equity,
                bank_financing_rate=Decimal("0.0000"),
                customer_equity_rate=Decimal("1.0000"),
            )


# ===========================================================================
# 5. BenefitApplicationRule
# ===========================================================================
class TestBenefitApplicationRule:
    """Test commercial policy incentive rules and constraints."""

    def test_valid_fixed_cash_benefit(self, sample_policy_ref: StructuredPolicyReference) -> None:
        rule = BenefitApplicationRule(
            benefit_id="BEN-GOLD",
            benefit_type=BenefitType.FIXED_CASH,
            category=BenefitCategory.CASH_DISCOUNT,
            fixed_deduction_vnd=160_000_000,
            valuation_status=ValuationStatus.APPROVED,
            price_deduction_authorized=True,
            source_policy_clause=sample_policy_ref,
        )
        assert rule.fixed_deduction_vnd == 160_000_000
        assert rule.price_deduction_authorized
        assert rule.calculation_base == CalculationBase.PRICE_AFTER_FIXED

    def test_valid_percentage_benefit(self, sample_policy_ref: StructuredPolicyReference) -> None:
        rule = BenefitApplicationRule(
            benefit_id="BEN-RESIDENT",
            benefit_type=BenefitType.PERCENTAGE,
            category=BenefitCategory.CASH_DISCOUNT,
            discount_rate=Decimal("0.0100"),
            valuation_status=ValuationStatus.APPROVED,
            price_deduction_authorized=True,
            source_policy_clause=sample_policy_ref,
        )
        assert rule.discount_rate == Decimal("0.0100")

    def test_category_type_mismatch_rejected(
        self, sample_policy_ref: StructuredPolicyReference
    ) -> None:
        with pytest.raises(ValueError, match="không tương thích với benefit_type"):
            BenefitApplicationRule(
                benefit_id="BEN-BAD-MAP",
                benefit_type=BenefitType.IN_KIND,  # Mismatch with CASH_DISCOUNT!
                category=BenefitCategory.CASH_DISCOUNT,
                valuation_status=ValuationStatus.APPROVED,
                price_deduction_authorized=False,
                source_policy_clause=sample_policy_ref,
            )

    def test_unauthorized_price_deduction_rejected(
        self, sample_policy_ref: StructuredPolicyReference
    ) -> None:
        with pytest.raises(ValueError, match="price_deduction_authorized=False"):
            BenefitApplicationRule(
                benefit_id="BEN-NO-AUTH",
                benefit_type=BenefitType.FIXED_CASH,
                category=BenefitCategory.CASH_DISCOUNT,
                fixed_deduction_vnd=50_000_000,
                valuation_status=ValuationStatus.APPROVED,
                price_deduction_authorized=False,  # Unauthorized but has amount!
                source_policy_clause=sample_policy_ref,
            )

    def test_fixed_cash_requires_positive_amount(
        self, sample_policy_ref: StructuredPolicyReference
    ) -> None:
        with pytest.raises(ValueError, match="FIXED_CASH yêu cầu fixed_deduction_vnd > 0"):
            BenefitApplicationRule(
                benefit_id="BEN-ZERO-CASH",
                benefit_type=BenefitType.FIXED_CASH,
                category=BenefitCategory.CASH_DISCOUNT,
                fixed_deduction_vnd=0,
                valuation_status=ValuationStatus.APPROVED,
                price_deduction_authorized=True,
                source_policy_clause=sample_policy_ref,
            )

    def test_percentage_requires_positive_rate(
        self, sample_policy_ref: StructuredPolicyReference
    ) -> None:
        with pytest.raises(ValueError, match="PERCENTAGE yêu cầu discount_rate > 0"):
            BenefitApplicationRule(
                benefit_id="BEN-ZERO-RATE",
                benefit_type=BenefitType.PERCENTAGE,
                category=BenefitCategory.CASH_DISCOUNT,
                discount_rate=Decimal("0.0000"),
                valuation_status=ValuationStatus.APPROVED,
                price_deduction_authorized=True,
                source_policy_clause=sample_policy_ref,
            )

    def test_in_kind_price_deduction_requires_approved_valuation(
        self, sample_policy_ref: StructuredPolicyReference
    ) -> None:
        with pytest.raises(ValueError, match="chỉ được trừ giá khi có ValuationStatus.APPROVED"):
            BenefitApplicationRule(
                benefit_id="BEN-PENDING-GIFT",
                benefit_type=BenefitType.IN_KIND,
                category=BenefitCategory.IN_KIND_GIFT,
                valuation_status=ValuationStatus.PENDING,  # PENDING cannot deduct price!
                price_deduction_authorized=True,
                source_policy_clause=sample_policy_ref,
            )


# ===========================================================================
# 6. PricingCalculationInput
# ===========================================================================
class TestPricingCalculationInput:
    """Test full calculation payload validation."""

    def test_valid_pricing_input(self) -> None:
        chudong = create_pa_chudong_config()
        pricing_input = PricingCalculationInput(
            unit_code="A-12-05",
            deposit_date=date(2026, 3, 1),
            contract_signing_date=date(2026, 3, 15),
            listed_price_vnd=3_500_000_000,
            deposit_amount_vnd=100_000_000,
            resolved_policy_snapshot_id="SNP-2026-VLF-01",
            source_policy_hash="e" * 64,
            scenario_configs=[chudong],
        )
        assert pricing_input.unit_code == "A-12-05"
        assert pricing_input.listed_price_vnd == 3_500_000_000
        assert pricing_input.tax_vat_rate == Decimal("0.1000")
        assert pricing_input.maintenance_fee_rate == Decimal("0.0200")
        assert len(pricing_input.scenario_configs) == 1

    def test_contract_date_before_deposit_date_rejected(self) -> None:
        with pytest.raises(ValueError, match="không được sớm hơn ngày đặt cọc"):
            PricingCalculationInput(
                unit_code="A-12-05",
                deposit_date=date(2026, 3, 15),
                contract_signing_date=date(2026, 3, 1),  # earlier than deposit!
                listed_price_vnd=3_500_000_000,
                resolved_policy_snapshot_id="SNP-001",
                source_policy_hash="e" * 64,
            )

    def test_listed_price_must_be_positive(self) -> None:
        with pytest.raises(ValidationError):
            PricingCalculationInput(
                unit_code="A-12-05",
                deposit_date=date(2026, 3, 1),
                contract_signing_date=date(2026, 3, 15),
                listed_price_vnd=0,  # gt=0 required
                resolved_policy_snapshot_id="SNP-001",
                source_policy_hash="e" * 64,
            )


# ===========================================================================
# 7. Canonical Scenario Builders
# ===========================================================================
class TestCanonicalScenarioBuilders:
    """Verify that canonical scenario builder functions produce compliant PaymentScenarioConfigs."""

    def test_create_pa_chudong_config(self) -> None:
        config = create_pa_chudong_config()
        assert config.scenario_type == ScenarioType.STANDARD_PROGRESS
        assert len(config.installment_rules) == 9
        assert config.bank_financing_rate == Decimal("0.0000")
        assert config.customer_equity_rate == Decimal("1.0000")
        # Check handover on milestone 8, reconciliation on milestone 9
        assert config.installment_rules[7].is_handover
        assert config.installment_rules[8].is_reconciliation

    def test_create_pa_nhanh_config(self) -> None:
        config = create_pa_nhanh_config()
        assert config.scenario_type == ScenarioType.EARLY_95
        assert len(config.installment_rules) == 3
        assert config.installment_rules[0].customer_equity_ratio == Decimal("0.9500")
        assert config.installment_rules[1].is_handover
        assert config.installment_rules[2].is_reconciliation

    def test_create_pa_vay_config(self) -> None:
        config = create_pa_vay_config(interest_support_months=24, principal_grace_months=24)
        assert config.scenario_type == ScenarioType.BANK_LOAN_HTLS
        assert len(config.installment_rules) == 6
        assert config.bank_financing_rate == Decimal("0.7000")
        assert config.customer_equity_rate == Decimal("0.3000")
        assert config.interest_support_months == 24
        assert config.principal_grace_months == 24

    def test_create_canonical_scenario_config_factory(self) -> None:
        chudong = create_canonical_scenario_config(ScenarioType.STANDARD_PROGRESS)
        nhanh = create_canonical_scenario_config(ScenarioType.EARLY_95)
        vay = create_canonical_scenario_config(ScenarioType.BANK_LOAN_HTLS)

        assert chudong.scenario_type == ScenarioType.STANDARD_PROGRESS
        assert nhanh.scenario_type == ScenarioType.EARLY_95
        assert vay.scenario_type == ScenarioType.BANK_LOAN_HTLS
