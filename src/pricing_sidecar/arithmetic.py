"""Arithmetic Contract and Precision Enforcement Module.

FCS v2.6 Reference: Section 2 (Arithmetic Contract)
TD-4.1 Reference: INV-RT-01 (Hardened Arithmetic Precision)

Rules:
1. Pure deterministic math.
2. Context precision >= 28 significant digits.
3. Vietnam accounting rounding: quantize(Decimal('1'), ROUND_HALF_UP).
4. Zero fractional VND (no hao / xu).
5. Strictly NO float allowed in any calculation path.
"""

from collections.abc import Callable, Iterable
from decimal import ROUND_HALF_UP, Decimal, getcontext
from functools import wraps
from typing import Any, TypeVar

# ---------------------------------------------------------------------------
# Global Precision Configuration
# ---------------------------------------------------------------------------
PRECISION: int = 28
ROUNDING_RULE = ROUND_HALF_UP
VND_STEP: Decimal = Decimal("1")

# Configure active process decimal context
getcontext().prec = PRECISION
getcontext().rounding = ROUNDING_RULE

F = TypeVar("F", bound=Callable[..., Any])


# ---------------------------------------------------------------------------
# Anti-Float Guard
# ---------------------------------------------------------------------------
def assert_no_float(*args: Any, **kwargs: Any) -> None:
    """Recursively inspect all arguments and ensure no float type is present.

    Raises:
        TypeError: If any float instance is encountered anywhere in the inputs.
    """

    def _check(val: Any, path: str = "") -> None:
        if isinstance(val, float):
            target = f" at '{path}'" if path else ""
            raise TypeError(
                f"FLOAT_PROHIBITED: Float value {val!r}{target} is strictly forbidden "
                "in financial calculation path. Use decimal.Decimal or int instead."
            )
        if isinstance(val, (list, tuple, set)):
            for i, item in enumerate(val):
                _check(item, f"{path}[{i}]" if path else f"[{i}]")
        elif isinstance(val, dict):
            for k, v in val.items():
                _check(k, f"{path}.key({k})" if path else f"key({k})")
                _check(v, f"{path}.{k}" if path else str(k))

    for idx, arg in enumerate(args):
        _check(arg, f"arg[{idx}]")
    for key, kwarg in kwargs.items():
        _check(kwarg, f"kwarg['{key}']")


def forbid_float(func: F) -> F:
    """Decorator to enforce strict anti-float guard on function inputs and output."""

    @wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        assert_no_float(*args, **kwargs)
        result = func(*args, **kwargs)
        assert_no_float(result)
        return result

    return wrapper  # type: ignore[return-value]


# ---------------------------------------------------------------------------
# Core Currency and Rate Conversion Functions
# ---------------------------------------------------------------------------
@forbid_float
def to_decimal(val: Decimal | int | str) -> Decimal:
    """Safely convert an integer, Decimal, or string to Decimal.

    Raises:
        TypeError: If val is float or unsupported type.
    """
    assert_no_float(val)
    if isinstance(val, Decimal):
        return val
    if isinstance(val, (int, str)):
        return Decimal(str(val))
    raise TypeError(
        f"Cannot convert type '{type(val).__name__}' to Decimal. "
        "Expected Decimal, int, or str."
    )


@forbid_float
def round_vnd(amount: Decimal | int | str) -> int:
    """Round a monetary amount to exact integer VNĐ using ROUND_HALF_UP.

    Conforms to Vietnamese accounting standard:
    - 0.5 rounds up to 1.
    - 0.4 rounds down to 0.
    - Returns exact native integer (0 fractional digits).
    """
    assert_no_float(amount)
    dec = to_decimal(amount)
    quantized = dec.quantize(VND_STEP, rounding=ROUND_HALF_UP)
    return int(quantized)


@forbid_float
def safe_rate_amount(base_amount: Decimal | int | str, rate: Decimal | str) -> int:
    """Calculate an amount from a base and a percentage rate, rounded to VNĐ."""
    assert_no_float(base_amount, rate)
    base_dec = to_decimal(base_amount)
    rate_dec = to_decimal(rate)
    return round_vnd(base_dec * rate_dec)


@forbid_float
def sum_rates(rates: Iterable[Decimal | str]) -> Decimal:
    """Sum multiple discount or interest rates with exact Decimal precision."""
    assert_no_float(rates)
    total = Decimal("0")
    for r in rates:
        total += to_decimal(r)
    return total


def format_vnd(amount: int | Decimal) -> str:
    """Format an integer or Decimal monetary amount into standard VNĐ string."""
    assert_no_float(amount)
    int_amount = int(amount)
    return f"{int_amount:,} VNĐ"
