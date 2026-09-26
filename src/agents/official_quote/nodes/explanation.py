"""Node giải trình hai chiều có chứng cứ (N-13, N-14A, N-14B)."""

from src.agents.official_quote.state import OfficialQuoteState


async def generate_explanation(state: OfficialQuoteState) -> dict:
    """N-13 — LLM Reasoner.

    Biên soạn giải trình Why / Why-not kèm `EvidenceBackedClaim` có tọa độ
    nguồn. Dùng: `src.services.llm` + `src.services.evidence.linker`.
    """
    raise NotImplementedError("C-01/N-13: theo TD-4.3 — dual explanation")


async def security_guardrail_output(state: OfficialQuoteState) -> dict:
    """N-14A — Guardrail.

    Quét rò rỉ system prompt / chỉ thị nội bộ / cam kết pháp lý ngoài chính
    sách. Vi phạm → `BLOCKED`.
    """
    raise NotImplementedError("C-01/N-14A: theo TD-4.3 — output guardrail")


async def validate_explanation(state: OfficialQuoteState) -> dict:
    """N-14B — Guardrail Gate (kiểm chứng cấp Claim).

    (1) Clause ID tồn tại; (2) policy version active; (3) tọa độ nguồn đầy đủ;
    (4) số tiền khớp 100% với Math Engine; (5) gắn cờ `UNSUPPORTED` nếu thiếu
    chứng cứ. Lỗi → `ABSTAINED`. Dùng: `src.services.evidence.linker`.
    """
    raise NotImplementedError("C-01/N-14B: theo TD-4.3 — claim-level validation")
