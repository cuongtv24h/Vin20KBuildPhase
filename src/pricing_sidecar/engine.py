"""Deterministic Pricing Engine Core: Additive Discount Model (FCS v2.6 §5).

Step 1: Khấu trừ ưu đãi tiền mặt cố định trực tiếp: Base_1 = P_listed - D_fixed
Step 2: Khấu trừ chiết khấu tỷ lệ % cộng dồn: Sum_Rate = ∑ r_i, P_net = Base_1 - round_vnd(Base_1 * Sum_Rate)
"""

from collections.abc import Sequence
from decimal import Decimal

from pydantic import Field

from src.pricing_sidecar.arithmetic import (
    assert_no_float,
    forbid_float,
    round_vnd,
    to_decimal,
)
from src.pricing_sidecar.contracts import (
    AntiFloatBaseModel,
    BenefitApplicationRule,
    BenefitType,
    ValuationStatus,
)


class AdditiveDiscountResult(AntiFloatBaseModel):
    """Kết quả tính toán Bước 1 & Bước 2 mô hình Additive Discount (FCS v2.6 §5)."""

    listed_price_vnd: int = Field(..., gt=0)
    fixed_discount_vnd: int = Field(default=0, ge=0)
    base_after_fixed_vnd: int = Field(..., ge=0)
    total_discount_rate: Decimal = Field(default=Decimal("0.0000"), ge=0)
    percentage_discount_vnd: int = Field(default=0, ge=0)
    net_price_before_vat: int = Field(..., ge=0)
    total_discount_amount_vnd: int = Field(default=0, ge=0)

    @property
    def total_discount_vnd(self) -> int:
        """Alias for total_discount_amount_vnd."""
        return self.total_discount_amount_vnd

    def __iter__(self):
        """Cho phép unpack: fixed, base, rate, pct_vnd, net = result."""
        yield self.fixed_discount_vnd
        yield self.base_after_fixed_vnd
        yield self.total_discount_rate
        yield self.percentage_discount_vnd
        yield self.net_price_before_vat


@forbid_float
def calculate_fixed_discount(
    listed_price_vnd: int,
    benefits: Sequence[BenefitApplicationRule] | None = None,
) -> tuple[int, int]:
    """Bước 1 FCS §5: Khấu trừ ưu đãi tiền mặt cố định trực tiếp vào giá niêm yết.

    Base_1 = P_listed - D_fixed (0 <= D_fixed <= P_listed)

    Args:
        listed_price_vnd: Giá niêm yết gốc của bất động sản (VNĐ, > 0).
        benefits: Danh sách các quy tắc ưu đãi đã được phê duyệt.

    Returns:
        tuple[int, int]: (fixed_discount_vnd, base_after_fixed_vnd)

    Raises:
        ValueError: Nếu listed_price_vnd <= 0 hoặc D_fixed > listed_price_vnd.
        TypeError: Nếu có bất kỳ tham số nào chứa kiểu float.
    """
    assert_no_float(listed_price_vnd, benefits)

    if listed_price_vnd <= 0:
        raise ValueError(
            f"SANITY_FAIL: listed_price_vnd ({listed_price_vnd:,}đ) phải là số nguyên dương > 0."
        )

    if not benefits:
        return 0, listed_price_vnd

    # Sắp xếp theo application_order để bảo đảm tính tất định
    sorted_benefits = sorted(benefits, key=lambda b: b.application_order)

    total_fixed_discount = 0
    for b in sorted_benefits:
        # Chỉ xét ưu đãi được ủy quyền trừ giá
        if not b.price_deduction_authorized:
            continue

        # Quà hiện vật chỉ được trừ giá khi có chứng thư định giá APPROVED
        if b.benefit_type == BenefitType.IN_KIND:
            if b.valuation_status != ValuationStatus.APPROVED:
                continue

        # Các ưu đãi có số tiền giảm trừ cố định > 0
        if b.fixed_deduction_vnd > 0:
            total_fixed_discount += b.fixed_deduction_vnd

    if total_fixed_discount < 0:
        raise ValueError(
            f"SANITY_FAIL: fixed_discount_vnd ({total_fixed_discount:,}đ) không được âm."
        )

    if total_fixed_discount > listed_price_vnd:
        raise ValueError(
            f"SANITY_FAIL: Tổng chiết khấu tiền mặt cố định ({total_fixed_discount:,}đ) "
            f"vượt quá giá niêm yết gốc ({listed_price_vnd:,}đ)."
        )

    base_after_fixed = listed_price_vnd - total_fixed_discount
    return total_fixed_discount, base_after_fixed


@forbid_float
def calculate_percentage_discount(
    base_after_fixed_vnd: int,
    benefits: Sequence[BenefitApplicationRule] | None = None,
    scenario_discount_rate: Decimal = Decimal("0.0000"),
) -> tuple[Decimal, int, int]:
    """Bước 2 FCS §5: Khấu trừ chiết khấu tỷ lệ % cộng dồn (Additive Discount).

    Sum_Rate = ∑ r_i + scenario_discount_rate
    Discount_Percent_Amount = round_vnd(Base_1 * Sum_Rate)
    P_net = Base_1 - Discount_Percent_Amount

    Args:
        base_after_fixed_vnd: Giá cơ sở sau khi trừ tiền mặt cố định (Base_1, >= 0).
        benefits: Danh sách các quy tắc ưu đãi đã được phê duyệt.
        scenario_discount_rate: Tỷ lệ chiết khấu riêng của kịch bản thanh toán (Decimal).

    Returns:
        tuple[Decimal, int, int]: (total_discount_rate, percentage_discount_vnd, net_price_before_vat)

    Raises:
        ValueError: Nếu base_after_fixed_vnd < 0 hoặc scenario_discount_rate < 0.
        TypeError: Nếu có bất kỳ tham số nào chứa kiểu float.
    """
    assert_no_float(base_after_fixed_vnd, benefits, scenario_discount_rate)

    if base_after_fixed_vnd < 0:
        raise ValueError(
            f"SANITY_FAIL: base_after_fixed_vnd ({base_after_fixed_vnd:,}đ) không được âm."
        )

    scenario_rate = to_decimal(scenario_discount_rate)
    if scenario_rate < Decimal("0.0000"):
        raise ValueError(
            f"SANITY_FAIL: scenario_discount_rate ({scenario_rate}) không được âm."
        )

    sum_rate = scenario_rate

    if benefits:
        sorted_benefits = sorted(benefits, key=lambda b: b.application_order)
        for b in sorted_benefits:
            if not b.price_deduction_authorized:
                continue

            if b.benefit_type == BenefitType.PERCENTAGE and b.discount_rate > Decimal("0.0000"):
                sum_rate += to_decimal(b.discount_rate)

    if sum_rate < Decimal("0.0000"):
        raise ValueError(f"SANITY_FAIL: Tổng tỷ lệ chiết khấu ({sum_rate}) không được âm.")

    discount_percent_amount = round_vnd(to_decimal(base_after_fixed_vnd) * sum_rate)
    net_price_before_vat = base_after_fixed_vnd - discount_percent_amount

    return sum_rate, discount_percent_amount, net_price_before_vat


@forbid_float
def calculate_additive_discount(
    listed_price_vnd: int,
    benefits: Sequence[BenefitApplicationRule] | None = None,
    scenario_discount_rate: Decimal = Decimal("0.0000"),
) -> AdditiveDiscountResult:
    """Tích hợp hoàn chỉnh Bước 1 & Bước 2 mô hình Additive Discount (FCS v2.6 §5).

    Returns:
        AdditiveDiscountResult: Đóng gói đầy đủ kết quả Bước 1 & Bước 2.
    """
    assert_no_float(listed_price_vnd, benefits, scenario_discount_rate)

    fixed_vnd, base_after_fixed_vnd = calculate_fixed_discount(
        listed_price_vnd=listed_price_vnd,
        benefits=benefits,
    )

    total_rate, percentage_vnd, net_price_vnd = calculate_percentage_discount(
        base_after_fixed_vnd=base_after_fixed_vnd,
        benefits=benefits,
        scenario_discount_rate=scenario_discount_rate,
    )

    total_discount_vnd = fixed_vnd + percentage_vnd

    return AdditiveDiscountResult(
        listed_price_vnd=listed_price_vnd,
        fixed_discount_vnd=fixed_vnd,
        base_after_fixed_vnd=base_after_fixed_vnd,
        total_discount_rate=total_rate,
        percentage_discount_vnd=percentage_vnd,
        net_price_before_vat=net_price_vnd,
        total_discount_amount_vnd=total_discount_vnd,
    )


@forbid_float
def calculate_total_benefit_value(
    benefits: Sequence[BenefitApplicationRule] | None = None,
) -> int:
    """Tính tổng giá trị các ưu đãi quà tặng có chứng thư định giá hợp lệ (FCS v2.6 §7.1).

    Chỉ tính các ưu đãi có ValuationStatus == APPROVED.
    """
    assert_no_float(benefits)
    if not benefits:
        return 0

    total_val = 0
    for b in benefits:
        if b.valuation_status == ValuationStatus.APPROVED:
            if b.fixed_deduction_vnd > 0:
                total_val += b.fixed_deduction_vnd
    return total_val
