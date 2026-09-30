"""Unit tests for src.pricing_sidecar.arithmetic module."""

from decimal import Decimal, getcontext

import pytest

from src.pricing_sidecar.arithmetic import (
    PRECISION,
    ROUNDING_RULE,
    assert_no_float,
    forbid_float,
    format_vnd,
    round_vnd,
    safe_rate_amount,
    sum_rates,
    to_decimal,
)


class TestArithmeticConfiguration:
    """Verify precision and global decimal settings."""

    def test_precision_is_at_least_28(self):
        assert PRECISION >= 28
        assert getcontext().prec >= 28

    def test_rounding_rule_is_round_half_up(self):
        assert str(ROUNDING_RULE) == "ROUND_HALF_UP"
        assert str(getcontext().rounding) == "ROUND_HALF_UP"


class TestRoundVnd:
    """Verify Vietnam accounting standard round_vnd implementation."""

    def test_round_half_up_integers(self):
        assert round_vnd(Decimal("0.4")) == 0
        assert round_vnd(Decimal("0.5")) == 1
        assert round_vnd(Decimal("0.6")) == 1
        assert round_vnd(Decimal("1.4")) == 1
        assert round_vnd(Decimal("1.5")) == 2
        assert round_vnd(Decimal("2.5")) == 3

    def test_round_half_up_negative(self):
        assert round_vnd(Decimal("-0.4")) == 0
        assert round_vnd(Decimal("-0.5")) == -1
        assert round_vnd(Decimal("-1.5")) == -2

    def test_round_large_property_values(self):
        base = Decimal("3500000000")
        assert round_vnd(base + Decimal("0.4999999999999999")) == 3500000000
        assert round_vnd(base + Decimal("0.5000000000000000")) == 3500000001
        assert round_vnd(base + Decimal("0.5000000000000001")) == 3500000001

    def test_round_from_int_and_str(self):
        assert round_vnd(100) == 100
        assert round_vnd("3500000000.5") == 3500000001
        assert round_vnd("3500000000.4") == 3500000000

    def test_round_rejects_unsupported_types(self):
        with pytest.raises(TypeError):
            round_vnd(None)  # type: ignore[arg-type]


class TestAntiFloatGuard:
    """Verify strict prohibition of float types in calculation path."""

    def test_assert_no_float_rejects_direct_float(self):
        with pytest.raises(TypeError, match="FLOAT_PROHIBITED"):
            assert_no_float(1.23)

    def test_assert_no_float_rejects_nested_in_list(self):
        with pytest.raises(TypeError, match="FLOAT_PROHIBITED"):
            assert_no_float([Decimal("1"), [Decimal("2"), 3.14]])

    def test_assert_no_float_rejects_nested_in_dict(self):
        with pytest.raises(TypeError, match="FLOAT_PROHIBITED"):
            assert_no_float({"amount": Decimal("100"), "rate": 0.08})

    def test_assert_no_float_rejects_in_kwargs(self):
        with pytest.raises(TypeError, match="FLOAT_PROHIBITED"):
            assert_no_float(valid=Decimal("100"), bad_rate=0.05)

    def test_round_vnd_rejects_float(self):
        with pytest.raises(TypeError, match="FLOAT_PROHIBITED"):
            round_vnd(100.5)

    def test_to_decimal_rejects_float(self):
        with pytest.raises(TypeError, match="FLOAT_PROHIBITED"):
            to_decimal(0.08)

    def test_safe_rate_amount_rejects_float(self):
        with pytest.raises(TypeError, match="FLOAT_PROHIBITED"):
            safe_rate_amount(3500000000, 0.08)

        with pytest.raises(TypeError, match="FLOAT_PROHIBITED"):
            safe_rate_amount(3500000000.0, Decimal("0.08"))

    def test_sum_rates_rejects_float(self):
        with pytest.raises(TypeError, match="FLOAT_PROHIBITED"):
            sum_rates([Decimal("0.08"), 0.01])


class TestForbidFloatDecorator:
    """Verify function decoration with @forbid_float."""

    def test_decorator_rejects_float_inputs(self):
        @forbid_float
        def calculate(a: Decimal, b: Decimal) -> Decimal:
            return a + b

        with pytest.raises(TypeError, match="FLOAT_PROHIBITED"):
            calculate(Decimal("1"), 2.0)  # type: ignore[arg-type]

    def test_decorator_rejects_float_return_value(self):
        @forbid_float
        def bad_calc(a: Decimal) -> float:
            return float(a)

        with pytest.raises(TypeError, match="FLOAT_PROHIBITED"):
            bad_calc(Decimal("10"))

    def test_decorator_allows_valid_types(self):
        @forbid_float
        def good_calc(a: Decimal, b: Decimal) -> Decimal:
            return a + b

        result = good_calc(Decimal("10.5"), Decimal("20.5"))
        assert result == Decimal("31.0")


class TestCalculationHelpers:
    """Verify rate calculations, rate sums, and formatting."""

    def test_safe_rate_amount(self):
        base = 3500000000
        # 10% VAT
        assert safe_rate_amount(base, Decimal("0.1000")) == 350000000
        # 2% KPBT
        assert safe_rate_amount(base, Decimal("0.0200")) == 70000000
        # 8% Early Discount
        assert safe_rate_amount(base, Decimal("0.0800")) == 280000000

    def test_sum_rates(self):
        rates = [Decimal("0.0800"), Decimal("0.0100")]
        assert sum_rates(rates) == Decimal("0.0900")

    def test_format_vnd(self):
        assert format_vnd(3500000000) == "3,500,000,000 VNĐ"
        assert format_vnd(Decimal("423200000")) == "423,200,000 VNĐ"
        assert format_vnd(0) == "0 VNĐ"

        with pytest.raises(TypeError, match="FLOAT_PROHIBITED"):
            format_vnd(1234.5)  # type: ignore[arg-type]
