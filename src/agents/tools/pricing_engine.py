"""Tool gọi Math Engine tất định (C-06) — LLM KHÔNG tự tính số."""

from langchain_core.tools import tool


@tool
def calculate_financial_plan(pricing_input_json: str) -> str:
    """Tính 3 phương án tài chính bằng Deterministic Math Engine (FCS v2.6).

    Toàn bộ phép tính tiền BẮT BUỘC đi qua tool này (Decimal 28 chữ số,
    sai số Δ = 0 VNĐ). LLM chỉ đọc kết quả để giải trình, không được tự cộng
    trừ số tiền trong câu trả lời.

    Args:
        pricing_input_json: JSON serialized `PricingCalculationInput` (N-09)

    Returns:
        JSON serialized `PricingCalculationOutput` (3 phương án + hash)
    """
    raise NotImplementedError("C-06: gọi src.services.pricing.client.PricingSidecarClient")
