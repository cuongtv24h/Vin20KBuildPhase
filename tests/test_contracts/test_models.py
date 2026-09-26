"""Test hợp đồng models dùng chung."""

import pytest
from pydantic import ValidationError

from src.contracts.common import TransactionContext, canonical_json_bytes, sha256_hex
from src.contracts.errors import DomainError, ErrorCode


def test_transaction_context_rejects_non_positive_price():
    with pytest.raises(ValidationError):
        TransactionContext(
            unit_code="R-02.02",
            customer_id="CUS-001",
            project_id="PROJECT-VLF-001",
            sales_channel="WEB",
            transaction_date="2026-03-10",
            listed_price_before_tax_vnd=0,
        )


def test_canonical_json_is_stable_across_key_order():
    a = canonical_json_bytes({"b": 1, "a": "x"})
    b = canonical_json_bytes({"a": "x", "b": 1})
    assert a == b
    assert sha256_hex(a) == sha256_hex(b)


def test_domain_error_carries_code_and_retryable():
    err = DomainError(ErrorCode.STALE_QUOTE_VERSION, "version đã superseded", http_status=409, retryable=False)
    assert err.code == ErrorCode.STALE_QUOTE_VERSION
    assert err.http_status == 409
    assert err.retryable is False
