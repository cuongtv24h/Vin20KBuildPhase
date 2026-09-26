"""Models dùng chung cho mọi hợp đồng (TD-4.3 §2 — Context & Input Models)."""

from datetime import date

from pydantic import BaseModel, Field

from src.contracts.enums import OptimizationObjective, PolicyEvaluationStatus


class TransactionContext(BaseModel):
    """Bối cảnh giao dịch đầu vào của báo giá (khóa từ TD-4.3)."""

    unit_code: str
    customer_id: str
    customer_segment: str = "STANDARD"
    project_id: str
    sales_channel: str
    transaction_date: date
    contract_signing_date: date | None = None
    listed_price_before_tax_vnd: int = Field(gt=0, description="Giá niêm yết căn hộ trước thuế (VNĐ)")
    optimization_objective: OptimizationObjective = OptimizationObjective.MIN_NET_PRICE
    is_simulation: bool = False


class PolicyClauseEvaluation(BaseModel):
    """Kết quả thẩm định một điều khoản chính sách (node N-06).

    Mỗi evaluation bắt buộc kèm trích dẫn nguyên văn (`evidence_quote`) và
    hash chunk nguồn để phục vụ Claim-Level Evidence Linking (F4 / C-04).
    TODO: mở rộng tọa độ nguồn (doc_id, page, section) khi implement C-04.
    """

    clause_id: str
    policy_id: str
    policy_version: str
    policy_name: str
    clause_title: str
    status: PolicyEvaluationStatus
    evidence_quote: str
    source_chunk_hash: str


def canonical_json_bytes(payload: dict) -> bytes:
    """Mã hóa JSON canonical (sort key, không whitespace) — dùng cho hash payload.

    Được N-19A (freeze approval_payload_hash) và C-07 (audit hash chain) dùng
    chung để đảm bảo hash bất biến giữa các module.
    """
    import json

    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def sha256_hex(data: bytes) -> str:
    """SHA-256 hex digest — helper dùng chung cho hash chain & snapshot."""
    import hashlib

    return hashlib.sha256(data).hexdigest()
