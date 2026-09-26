"""Node thẩm định điều khoản & phát hiện xung đột (N-06, N-07, N-08)."""

from src.agents.official_quote.state import OfficialQuoteState


async def evaluate_policy_clauses(state: OfficialQuoteState) -> dict:
    """N-06 — Deterministic / Reasoner.

    Đánh giá từng điều khoản theo 5 trạng thái `PolicyEvaluationStatus`,
    trích dẫn nguyên văn + `source_chunk_hash` cho F4.
    Output: `policy_clause_evaluations`.
    """
    raise NotImplementedError("C-01/N-06: theo TD-4.3 — clause evaluation")


async def detect_policy_conflicts(state: OfficialQuoteState) -> dict:
    """N-07 — Pure Logic.

    Tra ma trận loại trừ (`mydoc/dataset/canonical/mutual_exclusions.json`),
    phân loại xung đột 3 cấp, kiểm tra `precedence_rule` hợp lệ.
    Output: `ConflictReport`.
    """
    raise NotImplementedError("C-01/N-07: theo TD-4.3 — conflict detection")


async def safe_decision_gate(state: OfficialQuoteState) -> dict:
    """N-08 — Guardrail Gate (INTERRUPT BOUNDARY 1: Safe Abstention).

    Bất kỳ điều khoản `AMBIGUOUS`/`EXPIRED` hoặc xung đột cấp 1 không có
    precedence → ngắt sang `ABSTAINED`, không suy đoán.
    """
    raise NotImplementedError("C-01/N-08: theo TD-4.3 — safe abstention gate")
