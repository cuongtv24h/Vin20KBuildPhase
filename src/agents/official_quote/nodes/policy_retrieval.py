"""Node truy xuất chính sách (N-04, N-05)."""

from src.agents.official_quote.state import OfficialQuoteState


async def retrieve_active_policies(state: OfficialQuoteState) -> dict:
    """N-04 — Pure Lookup (Time-Travel).

    Truy vấn Policy Registry + pgvector theo `transaction_date` + `project_id`
    (Time-Travel SQL Join), lấy Policy Chunks kèm metadata tọa độ nguồn.
    Output: `retrieved_policy_ids`, `policy_snapshot_hash`, chunks.
    Dùng: `src.services.rag.retrieval`, `src.services.snapshot.freezer`.
    """
    raise NotImplementedError("C-01/N-04: theo TD-4.3 — time-travel policy retrieval")


async def security_guardrail_content(state: OfficialQuoteState) -> dict:
    """N-05 — Guardrail.

    Quét chống Indirect Prompt Injection trong chunk chính sách.
    Phát hiện lệnh bypass → `BLOCKED`.
    """
    raise NotImplementedError("C-01/N-05: theo TD-4.3 — content guardrail")
