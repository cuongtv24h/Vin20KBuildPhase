"""State schema của Official Quote StateGraph (C-01).

Khóa kiểu mạnh theo TD-4.3: trạng thái vòng đời/duyệt/PDF dùng enum từ
`src.contracts.enums` (Triple Enum Isolation), KHÔNG nhúng mã lỗi vào state.

TODO(TechLead): đối chiếu lại từng trường với §State của TD-4.3 khi dựng edges;
các trường dưới đây tổng hợp từ đầu ra của node N-01 → N-20.
"""

from __future__ import annotations

from typing import Any, TypedDict

from src.contracts.enums import ApprovalStatus, PdfStatus, QuoteWorkflowStatus, SecurityEventType


class OfficialQuoteState(TypedDict, total=False):
    """State đọc/ghi bởi các node N-01 → N-20."""

    # Định danh & vòng đời
    quote_id: str
    quote_version: int
    workflow_status: QuoteWorkflowStatus
    approval_status: ApprovalStatus
    pdf_status: PdfStatus

    # N-01/N-03 — đầu vào & bối cảnh
    transaction_context: dict[str, Any]
    risk_flags: list[str]
    security_event: SecurityEventType | None

    # N-04/N-06/N-07 — chính sách & xung đột
    retrieved_policy_ids: list[str]
    policy_snapshot_hash: str
    policy_clause_evaluations: list[dict[str, Any]]
    conflict_report: dict[str, Any]

    # N-09 → N-12 — tính toán tất định
    pricing_input: dict[str, Any]
    pricing_output: dict[str, Any]
    calculation_output_hash: str
    sanity_validation_passed: bool
    recommendation: dict[str, Any]

    # N-13/N-14 — giải trình có chứng cứ
    dual_explanation: dict[str, Any]
    explanation_validation_passed: bool

    # N-15 → N-20 — HITL, ký số, commit
    approval_package: dict[str, Any]
    human_decision: dict[str, Any]
    exception_record: dict[str, Any]
    approval_intent_id: str
    approval_payload_hash: str
    approval_created_at_frozen: str
    server_attestation_signature: str

    # Dùng chung
    error: str | None
    metadata: dict[str, Any]
