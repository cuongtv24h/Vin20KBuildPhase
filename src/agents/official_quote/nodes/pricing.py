"""Node tính toán tất định (N-09, N-10A, N-10B, N-11)."""

from src.agents.official_quote.state import OfficialQuoteState


async def build_pricing_input(state: OfficialQuoteState) -> dict:
    """N-09 — Pure Logic.

    Đóng gói `PricingCalculationInput`: giá niêm yết, tổng % chiết khấu,
    chiết khấu cố định, VAT, KPBT, `tiebreak_rule_id`.
    """
    raise NotImplementedError("C-01/N-09: theo TD-4.3 — pricing input builder")


async def security_guardrail_tool(state: OfficialQuoteState) -> dict:
    """N-10A — Guardrail.

    Kiểm tool allowlist + thẩm định argument bounds (chống SQLi / command
    injection khi gọi Math Engine).
    """
    raise NotImplementedError("C-01/N-10A: theo TD-4.3 — tool guardrail")


async def calculate_scenarios(state: OfficialQuoteState) -> dict:
    """N-10B — Pure (Deterministic).

    Gọi Math Worker (UDS sidecar, C-06) mô phỏng đồng thời 3 phương án
    PA-CHUDONG / PA-NHANH / PA-VAY theo FCS v2.6.
    Output: `PricingCalculationOutput`, `calculation_output_hash`.
    Dùng: `src.services.pricing.client`.
    """
    raise NotImplementedError("C-01/N-10B: theo TD-4.3 — sidecar calculation call")


async def validate_calculation(state: OfficialQuoteState) -> dict:
    """N-11 — Sanity Guard.

    Chạy 6 Sanity Check kế toán (danh sách khóa tại
    `src.services.pricing.validation.SANITY_CHECKS`). Fail → `CALCULATION_FAILED`.
    """
    raise NotImplementedError("C-01/N-11: theo TD-4.3 — sanity validation")
