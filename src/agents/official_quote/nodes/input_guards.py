"""Node cổng vào: validate input & guardrail bảo mật (N-01, N-02)."""

from src.agents.official_quote.state import OfficialQuoteState


async def validate_input(state: OfficialQuoteState) -> dict:
    """N-01 — Pure (Deterministic).

    Kiểm tra trường bắt buộc (`unit_code`, `transaction_date`, `customer_id`).
    Thiếu ngày giao dịch → dừng tại `NEEDS_INPUT`.
    Output: `TransactionContext`, `workflow_status`.
    """
    raise NotImplementedError("C-01/N-01: theo TD-4.3 — input validation")


async def security_guardrail_input(state: OfficialQuoteState) -> dict:
    """N-02 — Guardrail.

    Quét prompt injection trong ghi chú tư vấn; xác thực quyền hạn
    (SoD: Sales không được tự duyệt). Vi phạm → `BLOCKED` + `security_event`.
    """
    raise NotImplementedError("C-01/N-02: theo TD-4.3 — input guardrail")
