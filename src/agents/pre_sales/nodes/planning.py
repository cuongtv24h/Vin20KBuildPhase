"""Node dựng phương án tham khảo (F3, F5)."""

from src.agents.pre_sales.state import PreSalesSessionState


async def build_reference_plan_node(state: PreSalesSessionState) -> dict:
    """F3/F5 — Reference Plan.

    Tra chính sách hợp lệ tại ngày hiện tại (time-travel RAG, C-02), gọi
    Math Engine (C-06) tính phương án tham khảo, gắn watermark
    "NOT AN OFFICIAL QUOTE" — bắt buộc theo ranh giới INV-RT-09.
    """
    raise NotImplementedError("C-09/F3+F5: reference plan node")
