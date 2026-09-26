"""Node bối cảnh giao dịch (N-03)."""

from src.agents.official_quote.state import OfficialQuoteState


async def load_transaction_context(state: OfficialQuoteState) -> dict:
    """N-03 — Pure Lookup.

    Đọc thông tin căn hộ từ In-Memory Cache (< 0.1ms): giá niêm yết, diện tích
    thông thủy, tầng, trạng thái căn (`AVAILABLE`).
    Nguồn dữ liệu seed: `mydoc/dataset/canonical/units.json`.
    """
    raise NotImplementedError("C-01/N-03: theo TD-4.3 — transaction context lookup")
