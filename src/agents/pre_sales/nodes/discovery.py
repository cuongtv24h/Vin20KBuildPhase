"""Node hội thoại khám phá nhu cầu (F1)."""

from src.agents.pre_sales.state import PreSalesSessionState


async def discovery_node(state: PreSalesSessionState) -> dict:
    """F1 — Discovery chat.

    Dẫn dắt khách khai thác nhu cầu: ngân sách, nhu cầu diện tích, khả năng
    tài chính, tiến độ thanh toán mong muốn. LLM phải bám văn bản phát ngôn
    POL-08; không cam kết giá/ưu đãi (ranh giới pre-sales).
    """
    raise NotImplementedError("C-09/F1: discovery node")
