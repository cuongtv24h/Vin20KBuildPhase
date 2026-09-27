"""
Test suite for canonical serialization, hashing, and DTO validation.
"""

from datetime import date

import pytest
from pydantic import ValidationError

from src.contracts.common import (
    SourceCoordinate,
    TransactionContext,
    canonical_json_bytes,
    sha256_hex,
)
from src.contracts.errors import DomainError, ErrorCode


def test_canonical_json_stability():
    """Đảm bảo chuỗi JSON canonical không phụ thuộc vào thứ tự key khai báo."""
    dict_a = {"b": 2, "a": 1, "nested": {"z": 9, "y": 8}}
    dict_b = {"a": 1, "b": 2, "nested": {"y": 8, "z": 9}}

    bytes_a = canonical_json_bytes(dict_a)
    bytes_b = canonical_json_bytes(dict_b)

    assert bytes_a == bytes_b
    assert sha256_hex(bytes_a) == sha256_hex(bytes_b)
    # Không có khoảng trắng sau dấu hai chấm và dấu phẩy
    assert b'{"a":1,"b":2,"nested":{"y":8,"z":9}}' == bytes_a


def test_transaction_context_validation():
    """Kiểm tra validation của TransactionContext."""
    # Hợp lệ
    ctx = TransactionContext(
        project_id="BEVERLY",
        unit_code="BEV-12.04",
        listed_price_before_tax_vnd=4500000000,
        transaction_date=date(2026, 9, 26),
    )
    assert ctx.listed_price_before_tax_vnd == 4500000000
    assert ctx.customer_segment == "STANDARD"

    # Giá niêm yết <= 0 phải báo lỗi
    with pytest.raises(ValidationError):
        TransactionContext(
            project_id="BEVERLY",
            unit_code="BEV-12.04",
            listed_price_before_tax_vnd=0,
            transaction_date=date(2026, 9, 26),
        )


def test_source_coordinate_validation():
    """Tọa độ mỏ neo F4 phải có số trang >= 1."""
    coord = SourceCoordinate(
        document_id="DOC-POL-04",
        document_version="v3.1",
        document_hash="sha256:abc1234567890",
        page=12,
        clause_id="CLAUSE-4.2.1",
    )
    assert coord.page == 12

    with pytest.raises(ValidationError):
        SourceCoordinate(
            document_id="DOC-POL-04",
            document_version="v3.1",
            document_hash="sha256:abc",
            page=0,  # Invalid
            clause_id="CLAUSE-1",
        )


def test_domain_error_envelope():
    """Kiểm tra chuyển đổi DomainError sang ErrorEnvelope."""
    err = DomainError(
        error_code=ErrorCode.STALE_QUOTE_VERSION,
        message="Báo giá đã bị thay đổi bởi người khác",
        correlation_id="trace-12345",
        http_status=412,
        details={"current_version": 2, "provided_version": 1},
    )
    env = err.to_envelope()
    assert env.error_code == ErrorCode.STALE_QUOTE_VERSION
    assert env.correlation_id == "trace-12345"
    assert env.details["current_version"] == 2
