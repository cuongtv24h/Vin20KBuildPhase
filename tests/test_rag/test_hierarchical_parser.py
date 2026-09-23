"""Unit tests for LegalHierarchicalParser."""

import hashlib

from src.rag.ingestion.hierarchical_parser import LegalHierarchicalParser


def test_parse_articles_and_clauses():
    doc = """---
policy_id: "POL-TEST-01"
policy_name: "Chính sách kiểm thử"
effective_from: "2026-01-01"
effective_to: "2026-12-31"
---

# Điều 1: Quy định chung
1. Văn bản này áp dụng cho toàn bộ dự án.
2. Giá bán căn hộ chưa bao gồm thuế GTGT.

# Điều 2: Đặt cọc
Khách hàng đặt cọc 50,000,000 VNĐ khi đăng ký giữ chỗ.
"""
    parser = LegalHierarchicalParser()
    units = parser.parse_text(doc, default_id="POL-TEST-01")

    assert len(units) == 3
    # Check clause 1 of Điều 1
    assert units[0].article == "Điều 1: Quy định chung"
    assert units[0].clause == "Khoản 1"
    assert "toàn bộ dự án" in units[0].verbatim_text
    assert units[0].policy_id == "POL-TEST-01"
    assert units[0].content_sha256 == hashlib.sha256(units[0].verbatim_text.encode("utf-8")).hexdigest()

    # Check clause 2 of Điều 1
    assert units[1].article == "Điều 1: Quy định chung"
    assert units[1].clause == "Khoản 2"
    assert "chưa bao gồm thuế GTGT" in units[1].verbatim_text

    # Check Điều 2 (un-numbered paragraph becomes Khoản 1)
    assert units[2].article == "Điều 2: Đặt cọc"
    assert units[2].clause == "Khoản 1"
    assert "50,000,000 VNĐ" in units[2].verbatim_text


def test_line_spans_and_sha256():
    doc = """---
policy_id: "POL-TEST-02"
---

# Điều 1: Tiêu đề
1. Dòng 1 nội dung.
"""
    parser = LegalHierarchicalParser()
    units = parser.parse_text(doc)

    assert len(units) == 1
    unit = units[0]
    assert unit.line_span[0] > 0
    assert unit.line_span[1] >= unit.line_span[0]
    assert len(unit.content_sha256) == 64
