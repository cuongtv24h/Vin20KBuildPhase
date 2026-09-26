"""Kế hoạch thanh toán — tiến độ chuẩn 9 đợt (POL-04) & phương án nhanh 95%."""

STANDARD_INSTALLMENTS = 9  # tiến độ chuẩn theo POL-04


def build_schedule(scenario_code: str, contract_price_vnd: str, deposit_vnd: str) -> list[dict]:
    """Sinh các đợt thanh toán; đợt 1 cấn trừ cọc đã đặt (Sanity Check #6).

    TODO(Dev 2): ma trận tiến độ theo POL-04 + phương án PA-NHANH 95%.
    """
    raise NotImplementedError("C-06: payment schedules")
