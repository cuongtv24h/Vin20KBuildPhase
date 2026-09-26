"""Builder đồ thị Official Quote (C-01) — Owner: TechLead.

Topology đích theo TD-4.3:
    N-01 → N-02 → N-03 → N-04 → N-05 → N-06 → N-07 → N-08
      → (ABSTAINED | BLOCKED) hoặc tiếp N-09 → N-10A → N-10B → N-11 → N-12
      → N-13 → N-14A → N-14B → N-15 → N-16 (INTERRUPT: human review)
      → [approve: N-19A → N-19B → N-20 → END]
      → [revision: N-17 → quay lại N-01, version + 1, version cũ SUPERSEDED]
      → [exception: N-18 → quay lại N-06 với ExceptionApprovalRecord]

3 ranh giới ngắt (interrupt boundary): Safe Abstention (N-08), Human Review
(N-16), Exception Input (N-18) — checkpoint qua AsyncPostgresSaver (Spike 2).

TODO(TechLead): dựng edges theo topology trên với các node trong
`src.agents.official_quote.nodes.NODE_REGISTRY`, sau đó thay thế graph mẫu
`src/agents/graph.py` ở tầng API.
"""

from src.agents.official_quote.nodes import NODE_REGISTRY


def build_official_quote_graph():
    """Compile StateGraph 20 bước với checkpointing + interrupt.

    Chưa implement: chỉ trả về NotImplemented boundary để test cấu trúc biết
    rõ trạng thái. Dựng theo TD-4.3 trước khi bật endpoint /quotes.
    """
    raise NotImplementedError(
        f"C-01: dựng StateGraph theo TD-4.3 — NODE_REGISTRY đã sẵn {len(NODE_REGISTRY)} node"
    )
