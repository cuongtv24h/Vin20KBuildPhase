"""Deterministic calculator — trái tim của C-06 (FCS v2.6).

Mọi phép toán qua `decimal.Decimal` với Context 28 chữ số; cấm float tràn vào
từ bất kỳ đường nào (parse từ JSON string, không qua float).
"""

import decimal

DECIMAL_PRECISION = 28

# Bất biến golden (xác thực bởi tests/benchmarks/test_golden_scenarios.py):
#   discount = listed * discount_pct
#   net      = listed - discount
#   vat      = net * 10%           (POL-01)
#   contract = net + vat
#   kpbt     = net * 2%            (phí bảo trì bộ phận, POL-01)
#   outflow  = contract + kpbt


class DeterministicPricingEngine:
    """Mô phỏng 3 phương án PA-CHUDONG / PA-NHANH / PA-VAY (FCS v2.6)."""

    def __init__(self) -> None:
        self.context = decimal.Context(prec=DECIMAL_PRECISION)

    def simulate(self, pricing_input: dict) -> dict:
        """Nhập `PricingCalculationInput` → xuất Output 3 phương án, Δ = 0 VNĐ.

        TODO(Dev 2 — Spike 1): implement theo `mydoc/0.2.financial-calculation-spec.md`,
        đối soát bằng golden cases trước khi nối UDS server.
        """
        raise NotImplementedError("C-06: FCS v2.6 simulation")
