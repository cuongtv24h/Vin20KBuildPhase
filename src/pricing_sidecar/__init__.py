"""Pricing Engine Sidecar package.

Pure deterministic financial math engine conforming to FCS v2.6.
"""

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

__all__ = [
    "PRECISION",
    "ROUNDING_RULE",
    "assert_no_float",
    "forbid_float",
    "format_vnd",
    "round_vnd",
    "safe_rate_amount",
    "sum_rates",
    "to_decimal",
]
