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
    StructuredPolicyReference,
    ValuationStatus,
)
from src.pricing_sidecar.engine import (
    AdditiveDiscountResult,
    calculate_additive_discount,
    calculate_fixed_discount,
    calculate_percentage_discount,
    calculate_total_benefit_value,
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
# 5. Anti-Float Guard Enforcement Tests
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
