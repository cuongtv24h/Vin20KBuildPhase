"""Mã lỗi chuẩn hóa toàn hệ thống — nguồn: bảng lỗi TD-4.4.

Mỗi mã lỗi là một hằng số tách biệt khỏi trạng thái (Triple Enum Isolation).
TODO: đồng bộ đầy đủ danh sách mã lỗi khi implement từng endpoint theo TD-4.4.
"""

from enum import StrEnum


class ErrorCode(StrEnum):
    INPUT_VALIDATION_ERROR = "INPUT_VALIDATION_ERROR"  # 400
    PRECONDITION_FAILED = "PRECONDITION_FAILED"  # 412 — If-Match lệch ETag
    STALE_QUOTE_VERSION = "STALE_QUOTE_VERSION"  # 409 — duyệt version cũ
    IDEMPOTENCY_REPLAY = "IDEMPOTENCY_REPLAY"  # 409 — trùng Idempotency-Key
    CONFLICT_UNRESOLVED = "CONFLICT_UNRESOLVED"  # Safe Abstention N-08
    NOT_IMPLEMENTED = "NOT_IMPLEMENTED"  # 501 — scaffolding chưa implement


class DomainError(Exception):
    """Lỗi nghiệp vụ mang mã chuẩn — API layer quy đổi sang HTTP response."""

    def __init__(self, code: ErrorCode, message: str, http_status: int = 400, retryable: bool = False):
        super().__init__(message)
        self.code = code
        self.message = message
        self.http_status = http_status
        self.retryable = retryable
