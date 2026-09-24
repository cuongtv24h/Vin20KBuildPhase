"""Unit tests for Deterministic Pricing Engine: Step 1 & Step 2 Additive Discount.

FCS v2.6 Reference: Section 5 (Additive Discount Model & Formula)
Golden Scenario Reference: TC-01, TC-02, TC-04, TC-05, TC-06
"""

from datetime import date
from decimal import Decimal

import pytest

from src.pricing_sidecar.contracts import (
    BenefitApplicationRule,
    BenefitCategory,
    BenefitType,
    CalculationBase,
    ScenarioType,
    StructuredPolicyReference,
    ValuationStatus,
)
from src.pricing_sidecar.engine import (
    AdditiveDiscountResult,
    ContractPricingSummary,
    calculate_additive_discount,
    calculate_canonical_scenario,
    calculate_contract_pricing,
    calculate_final_contract_price,
    calculate_fixed_discount,
    calculate_maintenance_fee_amount,
    calculate_pa_chudong,
    calculate_pa_nhanh,
    calculate_pa_vay,
    calculate_percentage_discount,
    calculate_total_benefit_value,
    calculate_vat_amount,
    resolve_scenario_type,
    validate_dual_discount_cap,
)


@pytest.fixture
def sample_policy_ref() -> StructuredPolicyReference:
    """Fixture providing a valid policy coordinate reference."""
    return StructuredPolicyReference(
        policy_id="POL-2026-VLF-GEN",
        policy_version="v2.6",
        clause_id="Điều 4 Khoản 1",
        page_number=10,
        source_file_sha256="c" * 64,
        effective_from=date(2026, 1, 1),
        effective_to=date(2026, 12, 31),
    )


@pytest.fixture
def voucher_50m_rule(sample_policy_ref: StructuredPolicyReference) -> BenefitApplicationRule:
    """Fixture providing 50M VND interior voucher (TC-05 CTQT-Q1)."""
    return BenefitApplicationRule(
        benefit_id="BEN-VOUCHER-50M",
        benefit_type=BenefitType.FIXED_CASH,
        category=BenefitCategory.CASH_DISCOUNT,
        fixed_deduction_vnd=50_000_000,
        discount_rate=Decimal("0.0000"),
        calculation_base=CalculationBase.PRICE_AFTER_FIXED,
        application_order=1,
        valuation_status=ValuationStatus.APPROVED,
        price_deduction_authorized=True,
        source_policy_clause=sample_policy_ref,
    )


@pytest.fixture
def gold_160m_rule(sample_policy_ref: StructuredPolicyReference) -> BenefitApplicationRule:
    """Fixture providing 160M VND 2 SJC gold ounces (TC-06 CTQT-Q2)."""
    return BenefitApplicationRule(
        benefit_id="BEN-GOLD-160M",
        benefit_type=BenefitType.IN_KIND,
        category=BenefitCategory.IN_KIND_GIFT,
        fixed_deduction_vnd=160_000_000,
        discount_rate=Decimal("0.0000"),
        calculation_base=CalculationBase.PRICE_AFTER_FIXED,
        application_order=1,
        valuation_status=ValuationStatus.APPROVED,
        price_deduction_authorized=True,
        source_policy_clause=sample_policy_ref,
    )


@pytest.fixture
def resident_1pct_rule(sample_policy_ref: StructuredPolicyReference) -> BenefitApplicationRule:
    """Fixture providing 1% resident discount (TC-04 CSBH-VIP01)."""
    return BenefitApplicationRule(
        benefit_id="BEN-RESIDENT-1PCT",
        benefit_type=BenefitType.PERCENTAGE,
        category=BenefitCategory.CASH_DISCOUNT,
        fixed_deduction_vnd=0,
        discount_rate=Decimal("0.0100"),
        calculation_base=CalculationBase.PRICE_AFTER_FIXED,
        application_order=2,
        valuation_status=ValuationStatus.APPROVED,
        price_deduction_authorized=True,
        source_policy_clause=sample_policy_ref,
    )


# ===========================================================================
# 1. Step 1: Fixed Discount Tests
# ===========================================================================
class TestCalculateFixedDiscount:
    """Test Step 1: Khấu trừ tiền mặt cố định Base_1 = P_listed - D_fixed."""

    def test_fixed_discount_no_benefits(self) -> None:
        """TC-01 Baseline: No benefits -> D_fixed = 0, Base_1 = 3.5B."""
        fixed, base = calculate_fixed_discount(3_500_000_000, [])
        assert fixed == 0
        assert base == 3_500_000_000

    def test_fixed_discount_none_benefits(self) -> None:
        fixed, base = calculate_fixed_discount(3_500_000_000, None)
        assert fixed == 0
        assert base == 3_500_000_000

    def test_fixed_discount_voucher_50m(
        self, voucher_50m_rule: BenefitApplicationRule
    ) -> None:
        """TC-05: 50M voucher -> D_fixed = 50M, Base_1 = 3.45B."""
        fixed, base = calculate_fixed_discount(3_500_000_000, [voucher_50m_rule])
        assert fixed == 50_000_000
        assert base == 3_450_000_000

    def test_fixed_discount_in_kind_approved(
        self, gold_160m_rule: BenefitApplicationRule
    ) -> None:
        """TC-06: 160M SJC gold approved -> D_fixed = 160M, Base_1 = 3.34B."""
        fixed, base = calculate_fixed_discount(3_500_000_000, [gold_160m_rule])
        assert fixed == 160_000_000
        assert base == 3_340_000_000

    def test_fixed_discount_multiple_fixed(
        self,
        voucher_50m_rule: BenefitApplicationRule,
        gold_160m_rule: BenefitApplicationRule,
    ) -> None:
        """50M + 160M = 210M fixed discount."""
        fixed, base = calculate_fixed_discount(
            3_500_000_000, [voucher_50m_rule, gold_160m_rule]
        )
        assert fixed == 210_000_000
        assert base == 3_290_000_000

    def test_fixed_discount_in_kind_pending_ignored(
        self, sample_policy_ref: StructuredPolicyReference
    ) -> None:
        """In-kind gift without valuation certificate (PENDING) must NOT be deducted."""
        # Create un-authorized in-kind gift
        pending_gift = BenefitApplicationRule(
            benefit_id="BEN-GIFT-PENDING",
            benefit_type=BenefitType.IN_KIND,
            category=BenefitCategory.IN_KIND_GIFT,
            fixed_deduction_vnd=0,
            discount_rate=Decimal("0.0000"),
            valuation_status=ValuationStatus.PENDING,
            price_deduction_authorized=False,
            source_policy_clause=sample_policy_ref,
        )
        fixed, base = calculate_fixed_discount(3_500_000_000, [pending_gift])
        assert fixed == 0
        assert base == 3_500_000_000

    def test_fixed_discount_percentage_rule_ignored_in_step_1(
        self, resident_1pct_rule: BenefitApplicationRule
    ) -> None:
        """PERCENTAGE rules must not affect Step 1 fixed discount."""
        fixed, base = calculate_fixed_discount(3_500_000_000, [resident_1pct_rule])
        assert fixed == 0
        assert base == 3_500_000_000

    def test_fixed_discount_exceeds_listed_price_raises_error(
        self, sample_policy_ref: StructuredPolicyReference
    ) -> None:
        """D_fixed > listed_price must raise ValueError."""
        huge_rule = BenefitApplicationRule(
            benefit_id="BEN-HUGE",
            benefit_type=BenefitType.FIXED_CASH,
            category=BenefitCategory.CASH_DISCOUNT,
            fixed_deduction_vnd=4_000_000_000,
            valuation_status=ValuationStatus.APPROVED,
            price_deduction_authorized=True,
            source_policy_clause=sample_policy_ref,
        )
        with pytest.raises(ValueError, match="vượt quá giá niêm yết gốc"):
            calculate_fixed_discount(3_500_000_000, [huge_rule])

    def test_fixed_discount_invalid_listed_price_raises_error(self) -> None:
        """listed_price <= 0 must raise ValueError."""
        with pytest.raises(ValueError, match="phải là số nguyên dương"):
            calculate_fixed_discount(0, [])
        with pytest.raises(ValueError, match="phải là số nguyên dương"):
            calculate_fixed_discount(-100_000, [])


# ===========================================================================
# 2. Step 2: Percentage Discount Tests
# ===========================================================================
class TestCalculatePercentageDiscount:
    """Test Step 2: Khấu trừ chiết khấu tỷ lệ % cộng dồn (Additive)."""

    def test_percentage_discount_no_benefits_no_scenario_rate(self) -> None:
        """TC-01: 0% rate -> rate = 0, pct_vnd = 0, Net = Base_1 = 3.5B."""
        rate, pct_vnd, net = calculate_percentage_discount(
            base_after_fixed_vnd=3_500_000_000,
            benefits=[],
            scenario_discount_rate=Decimal("0.0000"),
        )
        assert rate == Decimal("0.0000")
        assert pct_vnd == 0
        assert net == 3_500_000_000

    def test_percentage_discount_tc02_early_95_8pct(self) -> None:
        """TC-02: PA-NHANH 8% on 3.5B -> pct_vnd = 280M, Net = 3.22B."""
        rate, pct_vnd, net = calculate_percentage_discount(
            base_after_fixed_vnd=3_500_000_000,
            benefits=[],
            scenario_discount_rate=Decimal("0.0800"),
        )
        assert rate == Decimal("0.0800")
        assert pct_vnd == 280_000_000
        assert net == 3_220_000_000

    def test_percentage_discount_tc04_additive_8pct_plus_1pct(
        self, resident_1pct_rule: BenefitApplicationRule
    ) -> None:
        """TC-04: PA-NHANH 8% + Cư dân 1% = 9% on 3.5B -> pct_vnd = 315M, Net = 3.185B."""
        rate, pct_vnd, net = calculate_percentage_discount(
            base_after_fixed_vnd=3_500_000_000,
            benefits=[resident_1pct_rule],
            scenario_discount_rate=Decimal("0.0800"),
        )
        assert rate == Decimal("0.0900")
        assert pct_vnd == 315_000_000
        assert net == 3_185_000_000

    def test_percentage_discount_on_base_after_fixed_tc05(self) -> None:
        """TC-05: 8% applied on Base_1 = 3.45B -> pct_vnd = 276M, Net = 3.174B."""
        rate, pct_vnd, net = calculate_percentage_discount(
            base_after_fixed_vnd=3_450_000_000,
            benefits=[],
            scenario_discount_rate=Decimal("0.0800"),
        )
        assert rate == Decimal("0.0800")
        assert pct_vnd == 276_000_000
        assert net == 3_174_000_000

    def test_percentage_discount_on_base_after_fixed_tc06(self) -> None:
        """TC-06: 6% applied on Base_1 = 3.34B -> pct_vnd = 200.4M, Net = 3.1396B."""
        rate, pct_vnd, net = calculate_percentage_discount(
            base_after_fixed_vnd=3_340_000_000,
            benefits=[],
            scenario_discount_rate=Decimal("0.0600"),
        )
        assert rate == Decimal("0.0600")
        assert pct_vnd == 200_400_000
        assert net == 3_139_600_000

    def test_percentage_discount_negative_base_raises_error(self) -> None:
        with pytest.raises(ValueError, match="không được âm"):
            calculate_percentage_discount(-1, [])

    def test_percentage_discount_negative_rate_raises_error(self) -> None:
        with pytest.raises(ValueError, match="không được âm"):
            calculate_percentage_discount(
                3_500_000_000, scenario_discount_rate=Decimal("-0.01")
            )


# ===========================================================================
# 3. Additive Discount Integration & Unpacking Tests
# ===========================================================================
class TestCalculateAdditiveDiscount:
    """Test full integration of Step 1 & Step 2 (calculate_additive_discount)."""

    def test_tc01_clean(self) -> None:
        """TC-01: Zero discount baseline."""
        res = calculate_additive_discount(
            listed_price_vnd=3_500_000_000,
            benefits=[],
            scenario_discount_rate=Decimal("0.0000"),
        )
        assert res.listed_price_vnd == 3_500_000_000
        assert res.fixed_discount_vnd == 0
        assert res.base_after_fixed_vnd == 3_500_000_000
        assert res.total_discount_rate == Decimal("0.0000")
        assert res.percentage_discount_vnd == 0
        assert res.net_price_before_vat == 3_500_000_000
        assert res.total_discount_amount_vnd == 0

    def test_tc05_interior_voucher_plus_early_95(
        self, voucher_50m_rule: BenefitApplicationRule
    ) -> None:
        """TC-05: 50M voucher + 8% early payment.

        Base_1 = 3.5B - 50M = 3.45B
        pct_vnd = 3.45B * 8% = 276M
        Net = 3.45B - 276M = 3.174B
        Total discount = 50M + 276M = 326M
        """
        res = calculate_additive_discount(
            listed_price_vnd=3_500_000_000,
            benefits=[voucher_50m_rule],
            scenario_discount_rate=Decimal("0.0800"),
        )
        assert res.fixed_discount_vnd == 50_000_000
        assert res.base_after_fixed_vnd == 3_450_000_000
        assert res.total_discount_rate == Decimal("0.0800")
        assert res.percentage_discount_vnd == 276_000_000
        assert res.net_price_before_vat == 3_174_000_000
        assert res.total_discount_amount_vnd == 326_000_000
        assert res.total_discount_vnd == 326_000_000

    def test_tc06_gold_sjc_plus_early_6pct(
        self, gold_160m_rule: BenefitApplicationRule
    ) -> None:
        """TC-06: 160M gold + 6% early payment.

        Base_1 = 3.5B - 160M = 3.34B
        pct_vnd = 3.34B * 6% = 200.4M
        Net = 3.34B - 200.4M = 3.1396B
        Total discount = 160M + 200.4M = 360.4M
        """
        res = calculate_additive_discount(
            listed_price_vnd=3_500_000_000,
            benefits=[gold_160m_rule],
            scenario_discount_rate=Decimal("0.0600"),
        )
        assert res.fixed_discount_vnd == 160_000_000
        assert res.base_after_fixed_vnd == 3_340_000_000
        assert res.total_discount_rate == Decimal("0.0600")
        assert res.percentage_discount_vnd == 200_400_000
        assert res.net_price_before_vat == 3_139_600_000
        assert res.total_discount_amount_vnd == 360_400_000

    def test_tuple_unpacking(self, voucher_50m_rule: BenefitApplicationRule) -> None:
        """Verify tuple unpacking format: fixed, base, rate, pct_vnd, net."""
        fixed, base, rate, pct_vnd, net = calculate_additive_discount(
            listed_price_vnd=3_500_000_000,
            benefits=[voucher_50m_rule],
            scenario_discount_rate=Decimal("0.0800"),
        )
        assert fixed == 50_000_000
        assert base == 3_450_000_000
        assert rate == Decimal("0.0800")
        assert pct_vnd == 276_000_000
        assert net == 3_174_000_000


# ===========================================================================
# 4. Total Benefit Value Helper Tests
# ===========================================================================
class TestCalculateTotalBenefitValue:
    """Test calculate_total_benefit_value (FCS §7.1)."""

    def test_total_benefit_value_approved_only(
        self,
        voucher_50m_rule: BenefitApplicationRule,
        gold_160m_rule: BenefitApplicationRule,
    ) -> None:
        val = calculate_total_benefit_value([voucher_50m_rule, gold_160m_rule])
        assert val == 210_000_000

    def test_total_benefit_value_empty(self) -> None:
        assert calculate_total_benefit_value([]) == 0
        assert calculate_total_benefit_value(None) == 0


# ===========================================================================
# 5. Dual Discount Cap Enforcement Tests (FCS v2.6 §5 & §9)
# ===========================================================================
class TestDualDiscountCap:
    """Test Percentage Cap (<= 35%) and Total Amount Cap (<= 40%)."""

    def test_within_caps_tc01_baseline(self) -> None:
        """TC-01: 0% and 0 VND discount is strictly within caps."""
        validate_dual_discount_cap(
            listed_price_vnd=3_500_000_000,
            total_discount_rate=Decimal("0.0000"),
            total_discount_amount_vnd=0,
        )

    def test_within_caps_tc05_and_tc06(self) -> None:
        """TC-05 (~9.3%) and TC-06 (~10.3%) are strictly within caps."""
        validate_dual_discount_cap(
            listed_price_vnd=3_500_000_000,
            total_discount_rate=Decimal("0.0800"),
            total_discount_amount_vnd=326_000_000,
        )
        validate_dual_discount_cap(
            listed_price_vnd=3_500_000_000,
            total_discount_rate=Decimal("0.0600"),
            total_discount_amount_vnd=360_400_000,
        )

    def test_exact_percentage_cap_boundary_passes(self) -> None:
        """Exactly 35.00% discount rate must pass (Sum_Rate <= max_discount_rate)."""
        validate_dual_discount_cap(
            listed_price_vnd=3_500_000_000,
            total_discount_rate=Decimal("0.3500"),
            total_discount_amount_vnd=1_225_000_000,
        )

    def test_exact_total_amount_cap_boundary_passes(self) -> None:
        """Exactly 40.00% total amount (1,400,000,000 VND) must pass."""
        validate_dual_discount_cap(
            listed_price_vnd=3_500_000_000,
            total_discount_rate=Decimal("0.2000"),
            total_discount_amount_vnd=1_400_000_000,
        )

    def test_percentage_cap_exceeded_raises_error(self) -> None:
        """Rate 35.01% > 35.00% must raise ValueError with DUAL_CAP_EXCEEDED."""
        with pytest.raises(ValueError, match="DUAL_CAP_EXCEEDED.*Tỷ lệ chiết khấu"):
            validate_dual_discount_cap(
                listed_price_vnd=3_500_000_000,
                total_discount_rate=Decimal("0.3501"),
                total_discount_amount_vnd=1_225_350_000,
            )

    def test_percentage_cap_exceeded_36pct_raises_error(self) -> None:
        """Rate 36.00% > 35.00% must raise ValueError."""
        with pytest.raises(ValueError, match="DUAL_CAP_EXCEEDED.*Tỷ lệ chiết khấu"):
            validate_dual_discount_cap(
                listed_price_vnd=3_500_000_000,
                total_discount_rate=Decimal("0.3600"),
                total_discount_amount_vnd=1_260_000_000,
            )

    def test_total_amount_cap_exceeded_raises_error(self) -> None:
        """Total 1,400,000,001 VND > 1,400,000,000 VND (40%) must raise ValueError."""
        with pytest.raises(ValueError, match="DUAL_CAP_EXCEEDED.*Tổng chiết khấu"):
            validate_dual_discount_cap(
                listed_price_vnd=3_500_000_000,
                total_discount_rate=Decimal("0.2000"),
                total_discount_amount_vnd=1_400_000_001,
            )

    def test_custom_dynamic_caps(self) -> None:
        """Custom caps configured from policy (e.g. VIP max 20% rate, 25% total amount)."""
        # Within custom caps: 15% and 700M (< 875M = 25% of 3.5B)
        validate_dual_discount_cap(
            listed_price_vnd=3_500_000_000,
            total_discount_rate=Decimal("0.1500"),
            total_discount_amount_vnd=700_000_000,
            max_discount_rate=Decimal("0.2000"),
            max_total_discount_cap_rate=Decimal("0.2500"),
        )
        # Exceeds custom rate cap (22% > 20%)
        with pytest.raises(ValueError, match="DUAL_CAP_EXCEEDED.*Tỷ lệ chiết khấu"):
            validate_dual_discount_cap(
                listed_price_vnd=3_500_000_000,
                total_discount_rate=Decimal("0.2200"),
                total_discount_amount_vnd=700_000_000,
                max_discount_rate=Decimal("0.2000"),
                max_total_discount_cap_rate=Decimal("0.2500"),
            )

    def test_calculate_additive_discount_enforces_caps_by_default(self) -> None:
        """calculate_additive_discount automatically blocks scenarios exceeding Dual Cap."""
        with pytest.raises(ValueError, match="DUAL_CAP_EXCEEDED.*Tỷ lệ chiết khấu"):
            calculate_additive_discount(
                listed_price_vnd=3_500_000_000,
                benefits=[],
                scenario_discount_rate=Decimal("0.4000"),  # 40% > 35% cap
            )

    def test_calculate_additive_discount_bypass_when_enforce_false(self) -> None:
        """calculate_additive_discount allows inspection when enforce_caps=False."""
        res = calculate_additive_discount(
            listed_price_vnd=3_500_000_000,
            benefits=[],
            scenario_discount_rate=Decimal("0.4000"),
            enforce_caps=False,
        )
        assert res.total_discount_rate == Decimal("0.4000")
        assert not res.is_within_caps
        assert res.max_total_discount_vnd == 1_400_000_000


# ===========================================================================
# 6. Contract Pricing & Taxes Tests (Step 3 & Step 4 FCS §5)
# ===========================================================================
class TestContractPricingAndTaxes:
    """Test VAT 10%, Maintenance Fee 2%, and Contract Price balance."""

    def test_pricing_tc01_baseline(self) -> None:
        """TC-01 / TC-03: Net 3.5B -> VAT 350M, KPBT 70M, Contract 3.92B."""
        summary = calculate_contract_pricing(3_500_000_000)
        assert summary.net_price_before_vat == 3_500_000_000
        assert summary.vat_amount == 350_000_000
        assert summary.maintenance_fee_amount == 70_000_000
        assert summary.final_contract_price == 3_920_000_000

    def test_pricing_tc02_early_95(self) -> None:
        """TC-02 / TC-10: Net 3.22B -> VAT 322M, KPBT 64.4M, Contract 3.6064B."""
        summary = calculate_contract_pricing(3_220_000_000)
        assert summary.net_price_before_vat == 3_220_000_000
        assert summary.vat_amount == 322_000_000
        assert summary.maintenance_fee_amount == 64_400_000
        assert summary.final_contract_price == 3_606_400_000

    def test_pricing_tc04_resident_additive(self) -> None:
        """TC-04: Net 3.185B -> VAT 318.5M, KPBT 63.7M, Contract 3.5672B."""
        summary = calculate_contract_pricing(3_185_000_000)
        assert summary.vat_amount == 318_500_000
        assert summary.maintenance_fee_amount == 63_700_000
        assert summary.final_contract_price == 3_567_200_000

    def test_pricing_tc05_interior_voucher(self) -> None:
        """TC-05: Net 3.174B -> VAT 317.4M, KPBT 63.48M, Contract 3.55488B."""
        summary = calculate_contract_pricing(3_174_000_000)
        assert summary.vat_amount == 317_400_000
        assert summary.maintenance_fee_amount == 63_480_000
        assert summary.final_contract_price == 3_554_880_000

    def test_pricing_tc06_gold_sjc(self) -> None:
        """TC-06: Net 3.1396B -> VAT 313.96M, KPBT 62.792M, Contract 3.516352B."""
        summary = calculate_contract_pricing(3_139_600_000)
        assert summary.vat_amount == 313_960_000
        assert summary.maintenance_fee_amount == 62_792_000
        assert summary.final_contract_price == 3_516_352_000

    def test_pricing_tc11_time_travel_v2(self) -> None:
        """TC-11: Net 3.29B -> VAT 329M, KPBT 65.8M, Contract 3.6848B."""
        summary = calculate_contract_pricing(3_290_000_000)
        assert summary.vat_amount == 329_000_000
        assert summary.maintenance_fee_amount == 65_800_000
        assert summary.final_contract_price == 3_684_800_000

    def test_pricing_tuple_unpacking(self) -> None:
        """Verify summary unpacking: vat_amount, kpbt_amount, contract_price."""
        vat, kpbt, contract = calculate_contract_pricing(3_500_000_000)
        assert vat == 350_000_000
        assert kpbt == 70_000_000
        assert contract == 3_920_000_000

    def test_odd_net_price_rounding_half_up(self) -> None:
        """Test accounting rounding ROUND_HALF_UP on non-round net price."""
        # 3,123,456,789 * 10% = 312,345,678.9 -> 312,345,679
        # 3,123,456,789 * 2% = 62,469,135.78 -> 62,469,136
        summary = calculate_contract_pricing(3_123_456_789)
        assert summary.vat_amount == 312_345_679
        assert summary.maintenance_fee_amount == 62_469_136
        expected_contract = 3_123_456_789 + 312_345_679 + 62_469_136
        assert summary.final_contract_price == expected_contract

    def test_negative_net_price_raises_error(self) -> None:
        with pytest.raises(ValueError, match="không được âm"):
            calculate_vat_amount(-1)
        with pytest.raises(ValueError, match="không được âm"):
            calculate_maintenance_fee_amount(-1)
        with pytest.raises(ValueError, match="không được âm"):
            calculate_final_contract_price(-1, 0, 0)

    def test_negative_rates_raises_error(self) -> None:
        with pytest.raises(ValueError, match="không được âm"):
            calculate_vat_amount(3_500_000_000, vat_rate=Decimal("-0.01"))
        with pytest.raises(ValueError, match="không được âm"):
            calculate_maintenance_fee_amount(
                3_500_000_000, maintenance_fee_rate=Decimal("-0.01")
            )


# ===========================================================================
# 7. Anti-Float Guard Enforcement Tests
# ===========================================================================
class TestAntiFloatGuardInEngine:
    """Ensure engine functions immediately reject float arguments."""

    def test_calculate_fixed_discount_rejects_float_price(self) -> None:
        with pytest.raises(TypeError, match="FLOAT_PROHIBITED"):
            calculate_fixed_discount(3500000000.0, [])  # float price!

    def test_calculate_percentage_discount_rejects_float_base(self) -> None:
        with pytest.raises(TypeError, match="FLOAT_PROHIBITED"):
            calculate_percentage_discount(3500000000.0, [])  # float base!

    def test_calculate_percentage_discount_rejects_float_scenario_rate(self) -> None:
        with pytest.raises(TypeError, match="FLOAT_PROHIBITED"):
            calculate_percentage_discount(
                3_500_000_000, [], scenario_discount_rate=0.08  # float rate!
            )

    def test_calculate_additive_discount_rejects_float_price(self) -> None:
        with pytest.raises(TypeError, match="FLOAT_PROHIBITED"):
            calculate_additive_discount(3500000000.0)

    def test_calculate_additive_discount_rejects_float_cap(self) -> None:
        with pytest.raises(TypeError, match="FLOAT_PROHIBITED"):
            calculate_additive_discount(
                3_500_000_000, max_discount_rate=0.35  # float cap!
            )

    def test_validate_dual_discount_cap_rejects_float_rate(self) -> None:
        with pytest.raises(TypeError, match="FLOAT_PROHIBITED"):
            validate_dual_discount_cap(
                listed_price_vnd=3_500_000_000,
                total_discount_rate=0.08,  # float!
                total_discount_amount_vnd=280_000_000,
            )

    def test_validate_dual_discount_cap_rejects_float_cap(self) -> None:
        with pytest.raises(TypeError, match="FLOAT_PROHIBITED"):
            validate_dual_discount_cap(
                listed_price_vnd=3_500_000_000,
                total_discount_rate=Decimal("0.0800"),
                total_discount_amount_vnd=280_000_000,
                max_discount_rate=0.35,  # float!
            )

    def test_calculate_vat_amount_rejects_float(self) -> None:
        with pytest.raises(TypeError, match="FLOAT_PROHIBITED"):
            calculate_vat_amount(3500000000.0)
        with pytest.raises(TypeError, match="FLOAT_PROHIBITED"):
            calculate_vat_amount(3_500_000_000, vat_rate=0.10)

    def test_calculate_maintenance_fee_amount_rejects_float(self) -> None:
        with pytest.raises(TypeError, match="FLOAT_PROHIBITED"):
            calculate_maintenance_fee_amount(3500000000.0)
        with pytest.raises(TypeError, match="FLOAT_PROHIBITED"):
            calculate_maintenance_fee_amount(
                3_500_000_000, maintenance_fee_rate=0.02
            )

    def test_calculate_final_contract_price_rejects_float(self) -> None:
        with pytest.raises(TypeError, match="FLOAT_PROHIBITED"):
            calculate_final_contract_price(3500000000.0, 350000000, 70000000)

    def test_contract_pricing_summary_rejects_float(self) -> None:
        with pytest.raises(TypeError, match="FLOAT_PROHIBITED"):
            ContractPricingSummary(
                net_price_before_vat=3_500_000_000,
                vat_rate=0.10,  # float!
                vat_amount=350_000_000,
                maintenance_fee_rate=Decimal("0.0200"),
                maintenance_fee_amount=70_000_000,
                final_contract_price=3_920_000_000,
            )

    def test_additive_discount_result_rejects_float(self) -> None:
        with pytest.raises(TypeError, match="FLOAT_PROHIBITED"):
            AdditiveDiscountResult(
                listed_price_vnd=3_500_000_000,
                fixed_discount_vnd=0,
                base_after_fixed_vnd=3_500_000_000,
                total_discount_rate=0.08,  # float!
                percentage_discount_vnd=280_000_000,
                net_price_before_vat=3_220_000_000,
                total_discount_amount_vnd=280_000_000,
            )

    def test_canonical_scenarios_reject_float(self) -> None:
        with pytest.raises(TypeError, match="FLOAT_PROHIBITED"):
            calculate_pa_chudong(3500000000.0)
        with pytest.raises(TypeError, match="FLOAT_PROHIBITED"):
            calculate_pa_nhanh(3_500_000_000, early_discount_rate=0.08)
        with pytest.raises(TypeError, match="FLOAT_PROHIBITED"):
            calculate_pa_vay(3_500_000_000, deposit_amount_vnd=100000000.0)
        with pytest.raises(TypeError, match="FLOAT_PROHIBITED"):
            calculate_canonical_scenario("PA-CHUDONG", 3500000000.0)


# ===========================================================================
# 8. Canonical Scenarios Tests (Task 2.4 / FCS §5, §6, §10)
# ===========================================================================
class TestCanonicalScenarios:
    """Test PA-CHUDONG, PA-NHANH, PA-VAY, and canonical dispatcher."""

    def test_pa_chudong_tc01_baseline(self) -> None:
        """TC-01: PA-CHUDONG baseline for A-12-05."""
        res = calculate_pa_chudong(3_500_000_000)
        assert res.scenario_type == ScenarioType.STANDARD_PROGRESS
        assert res.scenario_name == "Phương án Tiến độ Chuẩn (9 Đợt)"
        assert res.listed_price_vnd == 3_500_000_000
        assert res.fixed_discount_vnd == 0
        assert res.base_after_fixed_vnd == 3_500_000_000
        assert res.total_discount_rate == Decimal("0.0000")
        assert res.percentage_discount_vnd == 0
        assert res.net_price_before_vat == 3_500_000_000
        assert res.vat_rate == Decimal("0.1000")
        assert res.vat_amount == 350_000_000
        assert res.maintenance_fee_rate == Decimal("0.0200")
        assert res.maintenance_fee_amount == 70_000_000
        assert res.final_contract_price == 3_920_000_000
        assert res.initial_gross_obligation_vnd == 577_500_000
        assert res.initial_cash_outflow_vnd == 577_500_000
        assert res.customer_cash_outflow_until_handover == 3_727_500_000
        assert res.total_benefit_value_vnd == 0

    def test_pa_nhanh_tc02_baseline(self) -> None:
        """TC-02 / TC-10: PA-NHANH with early discount 8%."""
        res = calculate_pa_nhanh(
            3_500_000_000, early_discount_rate=Decimal("0.0800")
        )
        assert res.scenario_type == ScenarioType.EARLY_95
        assert res.scenario_name == "Phương án Thanh toán Sớm 95%"
        assert res.listed_price_vnd == 3_500_000_000
        assert res.fixed_discount_vnd == 0
        assert res.base_after_fixed_vnd == 3_500_000_000
        assert res.total_discount_rate == Decimal("0.0800")
        assert res.percentage_discount_vnd == 280_000_000
        assert res.net_price_before_vat == 3_220_000_000
        assert res.vat_amount == 322_000_000
        assert res.maintenance_fee_amount == 64_400_000
        assert res.final_contract_price == 3_606_400_000
        assert res.initial_gross_obligation_vnd == 3_364_900_000
        assert res.initial_cash_outflow_vnd == 3_364_900_000
        assert res.customer_cash_outflow_until_handover == 3_429_300_000
        assert res.total_benefit_value_vnd == 0

    def test_pa_vay_tc03_baseline(self) -> None:
        """TC-03: PA-VAY with HTLS 0% 24 months, customer equity 30%."""
        res = calculate_pa_vay(3_500_000_000)
        assert res.scenario_type == ScenarioType.BANK_LOAN_HTLS
        assert (
            res.scenario_name
            == "Phương án Hỗ trợ Lãi suất Ngân hàng (HTLS 70%)"
        )
        assert res.listed_price_vnd == 3_500_000_000
        assert res.fixed_discount_vnd == 0
        assert res.base_after_fixed_vnd == 3_500_000_000
        assert res.total_discount_rate == Decimal("0.0000")
        assert res.percentage_discount_vnd == 0
        assert res.net_price_before_vat == 3_500_000_000
        assert res.vat_amount == 350_000_000
        assert res.maintenance_fee_amount == 70_000_000
        assert res.final_contract_price == 3_920_000_000
        assert res.initial_gross_obligation_vnd == 577_500_000
        assert res.initial_cash_outflow_vnd == 577_500_000
        assert res.customer_cash_outflow_until_handover == 1_032_500_000
        assert res.total_benefit_value_vnd == 0

    def test_pa_nhanh_resident_additive_tc04(
        self, resident_1pct_rule: BenefitApplicationRule
    ) -> None:
        """TC-04: PA-NHANH + VIP resident discount 1% -> 9% total discount."""
        res = calculate_pa_nhanh(
            3_500_000_000,
            approved_benefits=[resident_1pct_rule],
            early_discount_rate=Decimal("0.0800"),
        )
        assert res.total_discount_rate == Decimal("0.0900")
        assert res.percentage_discount_vnd == 315_000_000
        assert res.net_price_before_vat == 3_185_000_000
        assert res.vat_amount == 318_500_000
        assert res.maintenance_fee_amount == 63_700_000
        assert res.final_contract_price == 3_567_200_000
        assert res.initial_gross_obligation_vnd == 3_328_325_000
        assert res.initial_cash_outflow_vnd == 3_328_325_000

    def test_pa_nhanh_interior_voucher_tc05(
        self, voucher_50m_rule: BenefitApplicationRule
    ) -> None:
        """TC-05: PA-NHANH + 50M furniture voucher fixed deduction."""
        res = calculate_pa_nhanh(
            3_500_000_000,
            approved_benefits=[voucher_50m_rule],
            early_discount_rate=Decimal("0.0800"),
        )
        assert res.fixed_discount_vnd == 50_000_000
        assert res.base_after_fixed_vnd == 3_450_000_000
        assert res.percentage_discount_vnd == 276_000_000
        assert res.net_price_before_vat == 3_174_000_000
        assert res.vat_amount == 317_400_000
        assert res.maintenance_fee_amount == 63_480_000
        assert res.final_contract_price == 3_554_880_000
        assert res.initial_gross_obligation_vnd == 3_316_830_000
        assert res.initial_cash_outflow_vnd == 3_316_830_000
        assert res.total_benefit_value_vnd == 50_000_000

    def test_pa_nhanh_gold_sjc_tc06(
        self, gold_160m_rule: BenefitApplicationRule
    ) -> None:
        """TC-06: PA-NHANH + 160M gold SJC fixed deduction + 6% early discount."""
        res = calculate_pa_nhanh(
            3_500_000_000,
            approved_benefits=[gold_160m_rule],
            early_discount_rate=Decimal("0.0600"),
        )
        assert res.fixed_discount_vnd == 160_000_000
        assert res.base_after_fixed_vnd == 3_340_000_000
        assert res.percentage_discount_vnd == 200_400_000
        assert res.net_price_before_vat == 3_139_600_000
        assert res.vat_amount == 313_960_000
        assert res.maintenance_fee_amount == 62_792_000
        assert res.final_contract_price == 3_516_352_000
        assert res.initial_gross_obligation_vnd == 3_280_882_000
        assert res.initial_cash_outflow_vnd == 3_280_882_000
        assert res.total_benefit_value_vnd == 160_000_000

    def test_pa_nhanh_time_travel_v2_tc11(self) -> None:
        """TC-11: PA-NHANH in July 2026 with 6% early discount."""
        res = calculate_pa_nhanh(
            3_500_000_000, early_discount_rate=Decimal("0.0600")
        )
        assert res.total_discount_rate == Decimal("0.0600")
        assert res.net_price_before_vat == 3_290_000_000
        assert res.vat_amount == 329_000_000
        assert res.maintenance_fee_amount == 65_800_000
        assert res.final_contract_price == 3_684_800_000
        assert res.initial_gross_obligation_vnd == 3_438_050_000
        assert res.initial_cash_outflow_vnd == 3_438_050_000

    def test_resolve_scenario_type(self) -> None:
        """Verify scenario alias and enum normalization."""
        assert (
            resolve_scenario_type(ScenarioType.STANDARD_PROGRESS)
            == ScenarioType.STANDARD_PROGRESS
        )
        assert (
            resolve_scenario_type("PA-CHUDONG")
            == ScenarioType.STANDARD_PROGRESS
        )
        assert (
            resolve_scenario_type("STANDARD_PROGRESS")
            == ScenarioType.STANDARD_PROGRESS
        )
        assert (
            resolve_scenario_type("chudong")
            == ScenarioType.STANDARD_PROGRESS
        )

        assert (
            resolve_scenario_type(ScenarioType.EARLY_95)
            == ScenarioType.EARLY_95
        )
        assert resolve_scenario_type("PA-NHANH") == ScenarioType.EARLY_95
        assert resolve_scenario_type("EARLY_95") == ScenarioType.EARLY_95
        assert resolve_scenario_type("nhanh") == ScenarioType.EARLY_95

        assert (
            resolve_scenario_type(ScenarioType.BANK_LOAN_HTLS)
            == ScenarioType.BANK_LOAN_HTLS
        )
        assert (
            resolve_scenario_type("PA-VAY") == ScenarioType.BANK_LOAN_HTLS
        )
        assert (
            resolve_scenario_type("BANK_LOAN_HTLS")
            == ScenarioType.BANK_LOAN_HTLS
        )
        assert resolve_scenario_type("vay") == ScenarioType.BANK_LOAN_HTLS

        with pytest.raises(ValueError, match="UNSUPPORTED_SCENARIO"):
            resolve_scenario_type("UNKNOWN_SCENARIO")

        with pytest.raises(TypeError, match="FLOAT_PROHIBITED"):
            resolve_scenario_type(123.45)  # type: ignore[arg-type]

    def test_calculate_canonical_scenario_dispatcher(self) -> None:
        """Verify calculate_canonical_scenario dispatches correctly to all 3 scenarios."""
        res_chudong = calculate_canonical_scenario(
            "PA-CHUDONG", 3_500_000_000
        )
        assert res_chudong.scenario_type == ScenarioType.STANDARD_PROGRESS
        assert res_chudong.final_contract_price == 3_920_000_000

        res_nhanh = calculate_canonical_scenario("PA-NHANH", 3_500_000_000)
        assert res_nhanh.scenario_type == ScenarioType.EARLY_95
        assert res_nhanh.final_contract_price == 3_606_400_000

        res_vay = calculate_canonical_scenario("PA-VAY", 3_500_000_000)
        assert res_vay.scenario_type == ScenarioType.BANK_LOAN_HTLS
        assert res_vay.final_contract_price == 3_920_000_000

    def test_deposit_greater_than_initial_gross_edge_case(self) -> None:
        """If deposit > initial gross, deposit_credited is clamped to eq_1."""
        res = calculate_pa_chudong(
            3_500_000_000, deposit_amount_vnd=600_000_000
        )
        assert res.initial_gross_obligation_vnd == 577_500_000
        assert res.initial_cash_outflow_vnd == 600_000_000

    def test_negative_deposit_raises_error(self) -> None:
        with pytest.raises(ValueError, match=r"không được âm|greater_than_equal"):
            calculate_pa_chudong(3_500_000_000, deposit_amount_vnd=-100_000)

    def test_dual_cap_violation_in_scenario_raises_error(
        self, sample_policy_ref: StructuredPolicyReference
    ) -> None:
        """Exceeding 35% discount in scenario raises DUAL_CAP_EXCEEDED."""
        huge_benefit = BenefitApplicationRule(
            benefit_id="HUGE-01",
            benefit_type=BenefitType.PERCENTAGE,
            category=BenefitCategory.CASH_DISCOUNT,
            discount_rate=Decimal("0.3000"),
            calculation_base=CalculationBase.PRICE_AFTER_FIXED,
            application_order=1,
            valuation_status=ValuationStatus.APPROVED,
            price_deduction_authorized=True,
            source_policy_clause=sample_policy_ref,
        )
        # 30% + 8% early = 38% > 35% cap
        with pytest.raises(ValueError, match="DUAL_CAP_EXCEEDED"):
            calculate_pa_nhanh(
                3_500_000_000,
                approved_benefits=[huge_benefit],
                early_discount_rate=Decimal("0.0800"),
            )



