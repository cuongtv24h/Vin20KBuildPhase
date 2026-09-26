"""Node bàn giao lead (F6, F7)."""

from src.agents.pre_sales.state import PreSalesSessionState


async def consent_and_handoff_node(state: PreSalesSessionState) -> dict:
    """F6/F7 — Consent & Handoff.

    Xin đồng ý chia sẻ thông tin → tạo Lead Dossier có cấu trúc (C-10) cho
    Sale tiếp nhận, kèm SLA countdown và 1-click convert-to-quote.
    """
    raise NotImplementedError("C-09/F6+F7: consent & handoff node")
