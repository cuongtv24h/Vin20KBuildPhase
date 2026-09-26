"""Khóa bất biến lõi Math Engine (C-06) ngay từ scaffold."""

import pytest

from src.pricing_sidecar.engine.calculator import DECIMAL_PRECISION, DeterministicPricingEngine
from src.pricing_sidecar.engine.schedules import STANDARD_INSTALLMENTS


def test_decimal_precision_is_28():
    assert DECIMAL_PRECISION == 28


def test_standard_schedule_is_nine_installments():
    assert STANDARD_INSTALLMENTS == 9


def test_engine_rejects_until_fcs_implemented():
    with pytest.raises(NotImplementedError):
        DeterministicPricingEngine().simulate({"unit_code": "R-02.02"})
