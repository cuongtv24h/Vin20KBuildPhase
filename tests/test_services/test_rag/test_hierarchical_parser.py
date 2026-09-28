"""Unit tests for LegalHierarchicalParser."""

import hashlib

from src.services.rag.ingestion.hierarchical_parser import LegalHierarchicalParser


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


def test_parse_markdown_table_rows():
    """Test parsing markdown tables into serialized row units."""
    doc = """---
policy_id: "POL-10"
policy_name: "Phụ lục điều kiện pháp lý"
---

# Bảng Ma trận Điều kiện Áp dụng Chiết khấu

| Mã Chiết Khấu | Tên Chương Trình | Mức Chiết Khấu | Điều Kiện Bắt Buộc |
|---|---|---|---|
| CK-EARLY-95 | Thanh toán sớm 95% | 8.0% | Ký HĐMB đúng hạn |
| CK-LOYALTY | Khách hàng thân thiết | 1.5% | Sở hữu tối thiểu 01 BĐS |
"""
    parser = LegalHierarchicalParser()
    units = parser.parse_text(doc, default_id="POL-10")

    assert len(units) == 2
    for u in units:
        assert u.atom_type == "TABLE_ROW"
        assert "Mã Chiết Khấu:" in u.verbatim_text
        assert "Mức Chiết Khấu:" in u.verbatim_text
        assert u.policy_id == "POL-10"
        assert u.line_span[0] > 0
        assert len(u.content_sha256) == 64
        assert "Bảng biểu ma trận" in u.full_searchable_text

    assert "CK-EARLY-95" in units[0].verbatim_text
    assert "8.0%" in units[0].verbatim_text
    assert "CK-LOYALTY" in units[1].verbatim_text
    assert "1.5%" in units[1].verbatim_text


def test_parse_footnotes():
    """Test parsing footnotes and special condition notes."""
    doc = """---
policy_id: "POL-FN"
policy_name: "Chính sách có chú thích"
---

# Điều 1: Điều kiện hưởng ưu đãi
1. Khách hàng phải thanh toán đợt 1 trong vòng 7 ngày làm việc.

[*] Ghi chú: Thời gian làm việc không bao gồm Thứ Bảy, Chủ Nhật và ngày Lễ.
(*) Lưu ý: Hóa đơn GTGT sẽ được xuất sau 3 ngày hoàn tất thanh toán.
"""
    parser = LegalHierarchicalParser()
    units = parser.parse_text(doc, default_id="POL-FN")

    assert len(units) == 3
    assert units[0].atom_type == "CLAUSE"
    assert units[1].atom_type == "FOOTNOTE"
    assert units[2].atom_type == "FOOTNOTE"

    assert "Thứ Bảy, Chủ Nhật" in units[1].verbatim_text
    assert "Ghi chú chân trang" in units[1].full_searchable_text
    assert "Hóa đơn GTGT" in units[2].verbatim_text


def test_atomizer_table_and_footnote():
    """Test PolicyAtomizer table serialization and footnote atom generation."""
    from src.models.pec_contracts import PolicyAtomType
    from src.services.rag.compiler.atomizer import PolicyAtomizer

    atomizer = PolicyAtomizer()
    md = """# Điều 1: Khung giá
| Căn hộ | Diện tích | Đơn giá |
|---|---|---|
| A-01 | 75m2 | 45 triệu/m2 |
| B-02 | 90m2 | 48 triệu/m2 |

[*] Ghi chú: Giá trên chưa bao gồm 2% phí bảo trì.
"""
    atoms = atomizer.parse_markdown_to_atoms(
        markdown_text=md,
        policy_metadata={"policy_id": "POL-PRICE", "policy_name": "Bảng giá mẫu"},
    )

    table_atoms = [a for a in atoms if a["atom_type"] == PolicyAtomType.TABLE_ROW.value]
    fn_atoms = [a for a in atoms if a["atom_type"] == PolicyAtomType.FOOTNOTE.value]

    assert len(table_atoms) == 2
    assert len(fn_atoms) == 1
    assert "Căn hộ: A-01 | Diện tích: 75m2 | Đơn giá: 45 triệu/m2" in table_atoms[0]["canonical_text"]
    assert table_atoms[0]["table_coordinates"] == "row_1"
    assert "2% phí bảo trì" in fn_atoms[0]["canonical_text"]
