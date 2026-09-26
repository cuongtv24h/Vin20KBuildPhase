"""DTO biên giao tiếp với Pricing Sidecar — C-06 (Dev 2).

Hợp đồng UDS giữa LangGraph Orchestrator và Math Engine độc lập.
Nguồn: TD-4.2 (FCS v2.6), TD-4.4 (tool contract), node N-09/N-10B.

Model cần định nghĩa khi implement:
- `PricingCalculationInput`  — N-09 đóng gói: giá niêm yết, tổng % chiết khấu,
  chiết khấu cố định, VAT, KPBT, tiebreak_rule_id
- `PricingCalculationOutput` — 3 phương án dòng tiền + hash đầu ra (N-10B)
- `ScenarioBreakdown`        — chi tiết 1 phương án (các đợt thanh toán)
"""

from enum import StrEnum


class ScenarioCode(StrEnum):
    """3 phương án dòng tiền chuẩn mô phỏng đồng thời (FCS v2.6)."""

    CHUDONG = "PA-CHUDONG"  # Thanh toán theo tiến độ chuẩn
    NHANH = "PA-NHANH"  # Thanh toán sớm 95% nhận chiết khấu cao
    VAY = "PA-VAY"  # Vay ngân hàng kèm HTLS 0%
