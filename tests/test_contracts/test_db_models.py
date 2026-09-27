"""
Test suite for SQLAlchemy ORM models mapping and metadata integrity.
"""

from src.db.models import (
    Base,
    ProjectModel,
    UnitModel,
)


def test_table_metadata_registration():
    """Đảm bảo tất cả 13 bảng nghiệp vụ đã đăng ký thành công vào Base.metadata."""
    table_names = set(Base.metadata.tables.keys())
    expected_tables = {
        "projects",
        "units",
        "policy_documents",
        "policy_chunks",
        "policy_rules",
        "pre_sales_sessions",
        "customer_consents",
        "pre_sales_plans",
        "lead_dossiers",
        "quotes",
        "quote_snapshots",
        "quote_audit_events",
        "transactional_outbox",
        "compliance_checks",
    }
    assert expected_tables.issubset(table_names)


def test_model_instantiation():
    """Kiểm tra khởi tạo thực thể ORM không bị lỗi cú pháp."""
    project = ProjectModel(
        project_id="BEVERLY",
        tenant_id="DEFAULT",
        project_name="The Beverly Solari",
        legal_entity_name="Vingroup JSC",
    )
    assert project.project_id == "BEVERLY"

    unit = UnitModel(
        unit_code="BEV-12.04",
        project_id="BEVERLY",
        unit_type="2BR",
        floor_number=12,
        listed_price_before_tax_vnd=4500000000,
        handover_date="2026-12-31",
    )
    assert unit.listed_price_before_tax_vnd == 4500000000
