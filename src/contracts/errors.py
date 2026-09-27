"""
Canonical error codes and domain exceptions for PricePolicy AI Agent.
"""

from contextvars import ContextVar
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field

# Request-scoped correlation ID for distributed tracing (M-02)
current_correlation_id: ContextVar[str] = ContextVar("correlation_id", default="trace-unknown")


class ErrorCode(StrEnum):
    """Bảng mã lỗi chuẩn hệ thống (Error Catalog)."""
    INPUT_VALIDATION_ERROR = "INPUT_VALIDATION_ERROR"
    MISSING_TRANSACTION_DATE = "MISSING_TRANSACTION_DATE"
    POLICY_NOT_FOUND = "POLICY_NOT_FOUND"
    POLICY_EXPIRED = "POLICY_EXPIRED"
    POLICY_CONFLICT_UNRESOLVED = "POLICY_CONFLICT_UNRESOLVED"
    FINANCIAL_SANITY_FAILED = "FINANCIAL_SANITY_FAILED"
    STALE_QUOTE_VERSION = "STALE_QUOTE_VERSION"
    INVALID_STATE_TRANSITION = "INVALID_STATE_TRANSITION"
    IDEMPOTENCY_PROCESSING = "IDEMPOTENCY_PROCESSING"
    IDEMPOTENCY_KEY_REUSE_PAYLOAD_MISMATCH = "IDEMPOTENCY_KEY_REUSE_PAYLOAD_MISMATCH"
    EXPLANATION_VALIDATION_FAILED = "EXPLANATION_VALIDATION_FAILED"
    COMPLIANCE_SEND_BLOCKED = "COMPLIANCE_SEND_BLOCKED"
    PDF_NOT_READY = "PDF_NOT_READY"
    SOD_VIOLATION = "SOD_VIOLATION"
    SOD_CREATOR_APPROVER_IDENTICAL = "SOD_CREATOR_APPROVER_IDENTICAL"
    UNAUTHORIZED_ACCESS = "UNAUTHORIZED_ACCESS"
    TAMPER_DETECTED = "TAMPER_DETECTED"
    IMMUTABLE_SNAPSHOT_VIOLATION = "IMMUTABLE_SNAPSHOT_VIOLATION"
    QUOTE_NOT_FOUND = "QUOTE_NOT_FOUND"
    VERSION_CONFLICT = "VERSION_CONFLICT"
    CALCULATION_ENGINE_ERROR = "CALCULATION_ENGINE_ERROR"
    NOT_FOUND = "NOT_FOUND"


class ErrorEnvelope(BaseModel):
    """Cấu trúc phản hồi lỗi chuẩn tắc API."""
    error_code: ErrorCode = Field(..., description="Mã lỗi hệ thống chuẩn")
    message: str = Field(..., description="Mô tả lỗi dễ hiểu cho người dùng")
    correlation_id: str = Field(..., description="Mã truy vết luồng xử lý")
    details: dict[str, Any] = Field(default_factory=dict, description="Chi tiết lỗi bổ sung")


class DomainError(Exception):
    """Ngoại lệ miền nghiệp vụ PricePolicy."""
    def __init__(
        self,
        error_code: ErrorCode,
        message: str,
        correlation_id: str = "trace-unknown",
        http_status: int = 400,
        details: dict[str, Any] | None = None,
    ):
        cid = correlation_id if correlation_id != "trace-unknown" else current_correlation_id.get()
        super().__init__(message)
        self.error_code = error_code
        self.code = error_code
        self.message = message
        self.correlation_id = cid
        self.http_status = http_status
        self.details = details or {}

    def to_envelope(self) -> ErrorEnvelope:
        return ErrorEnvelope(
            error_code=self.error_code,
            message=self.message,
            correlation_id=self.correlation_id,
            details=self.details,
        )
