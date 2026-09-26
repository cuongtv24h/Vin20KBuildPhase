"""Builder đồ thị Pre-Sales Advisory (C-09).

Luồng đích (theo flowchart MVP `mydoc/ImplementPlan.md` — giai đoạn 1):
    discovery (F1) → extract_constraints (F2) → conflict? → safe halt
    → build_reference_plan (F3/F5, RAG time-travel) → confirm_constraints
    → consent_and_handoff (F6/F7) → tạo Lead Dossier (C-10)

TODO(TechLead + Dev 3): dựng edges, checkpointing + TTL phiên (Spike 5).
"""

from src.agents.pre_sales.nodes import PRE_SALES_NODE_REGISTRY


def build_pre_sales_graph():
    """Compile StateGraph pre-sales — chưa implement, xem docstring module."""
    raise NotImplementedError(
        f"C-09: dựng StateGraph pre-sales — {len(PRE_SALES_NODE_REGISTRY)} node đã đăng ký"
    )
