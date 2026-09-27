"""
SQLAlchemy ORM models mapping to PostgreSQL 16 domain schemas (TD-4.2).
"""

import uuid
from datetime import date, datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from src.db.session import Base

# Sử dụng JSON tương thích cho cả SQLite và PostgreSQL
JsonType = JSON().with_variant(JSONB, "postgresql")


class ProjectModel(Base):
    """Bảng dự án bất động sản."""
    __tablename__ = "projects"

    project_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(64), default="DEFAULT", index=True)
    project_name: Mapped[str] = mapped_column(String(255), nullable=False)
    legal_entity_name: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now())

    units: Mapped[list["UnitModel"]] = relationship("UnitModel", back_populates="project")


class UnitModel(Base):
    """Bảng thông tin căn hộ tồn kho."""
    __tablename__ = "units"

    unit_code: Mapped[str] = mapped_column(String(64), primary_key=True)
    project_id: Mapped[str] = mapped_column(String(64), ForeignKey("projects.project_id"), nullable=False, index=True)
    unit_type: Mapped[str] = mapped_column(String(32), nullable=False)  # STUDIO, 1BR, 2BR, 3BR
    floor_number: Mapped[int] = mapped_column(Integer, nullable=False)
    listed_price_before_tax_vnd: Mapped[int] = mapped_column(BigInteger, nullable=False)
    handover_date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="AVAILABLE", index=True)

    project: Mapped["ProjectModel"] = relationship("ProjectModel", back_populates="units")


class PolicyDocumentModel(Base):
    """Bảng lưu trữ thông tin văn bản chính sách bán hàng."""
    __tablename__ = "policy_documents"

    document_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(64), default="DEFAULT", index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    document_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    effective_from: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    effective_to: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(32), default="ACTIVE", index=True)
    version: Mapped[str] = mapped_column(String(32), default="v1.0")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now())

    chunks: Mapped[list["PolicyChunkModel"]] = relationship("PolicyChunkModel", back_populates="document")
    rules: Mapped[list["PolicyRuleModel"]] = relationship("PolicyRuleModel", back_populates="document")


class PolicyChunkModel(Base):
    """Bảng lưu trữ chunk ngữ nghĩa để tìm kiếm Time-Travel RAG."""
    __tablename__ = "policy_chunks"

    chunk_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    document_id: Mapped[str] = mapped_column(String(64), ForeignKey("policy_documents.document_id"), nullable=False, index=True)
    clause_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    section: Mapped[str | None] = mapped_column(String(128), nullable=True)
    page: Mapped[int] = mapped_column(Integer, nullable=False)
    chunk_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    # Cột vector embedding: Trong môi trường PostgreSQL có extension pgvector, cột này là VECTOR(1536)
    embedding_json: Mapped[dict[str, Any] | None] = mapped_column(JsonType, nullable=True)

    document: Mapped["PolicyDocumentModel"] = relationship("PolicyDocumentModel", back_populates="chunks")


class PolicyRuleModel(Base):
    """Bảng quy tắc chính sách có cấu trúc F9."""
    __tablename__ = "policy_rules"

    rule_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    policy_id: Mapped[str] = mapped_column(String(64), ForeignKey("policy_documents.document_id"), nullable=False, index=True)
    policy_version: Mapped[str] = mapped_column(String(32), nullable=False)
    clause_id: Mapped[str] = mapped_column(String(64), nullable=False)
    rule_type: Mapped[str] = mapped_column(String(64), nullable=False)
    condition_json: Mapped[dict[str, Any]] = mapped_column(JsonType, nullable=False)
    benefit_formula: Mapped[dict[str, Any]] = mapped_column(JsonType, nullable=False)
    priority: Mapped[int] = mapped_column(Integer, default=10)
    status: Mapped[str] = mapped_column(String(32), default="DRAFT", index=True)
    regression_test_pass_rate: Mapped[float] = mapped_column(Float, default=0.0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now())

    document: Mapped["PolicyDocumentModel"] = relationship("PolicyDocumentModel", back_populates="rules")


class PreSalesSessionModel(Base):
    """Bảng lưu trữ phiên chat tư vấn Pre-Sales (C-09)."""
    __tablename__ = "pre_sales_sessions"

    session_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(64), default="DEFAULT", index=True)
    status: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    constraints_json: Mapped[dict[str, Any] | None] = mapped_column(JsonType, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now())
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    consents: Mapped[list["CustomerConsentModel"]] = relationship("CustomerConsentModel", back_populates="session")
    plans: Mapped[list["PreSalesPlanModel"]] = relationship("PreSalesPlanModel", back_populates="session")
    dossiers: Mapped[list["LeadDossierModel"]] = relationship("LeadDossierModel", back_populates="session")


class CustomerConsentModel(Base):
    """Bảng ghi nhận xác nhận đồng thuận chia sẻ thông tin cá nhân (F6)."""
    __tablename__ = "customer_consents"

    consent_id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id: Mapped[str] = mapped_column(String(64), ForeignKey("pre_sales_sessions.session_id"), nullable=False, index=True)
    customer_name: Mapped[str] = mapped_column(String(255), nullable=False)
    customer_phone: Mapped[str] = mapped_column(String(32), nullable=False)
    customer_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    consent_scope: Mapped[str] = mapped_column(String(255), default="PRE_SALES_ADVISORY_AND_SALES_CONTACT")
    ip_address: Mapped[str | None] = mapped_column(String(64), nullable=True)
    granted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now())

    session: Mapped["PreSalesSessionModel"] = relationship("PreSalesSessionModel", back_populates="consents")


class PreSalesPlanModel(Base):
    """Bảng lưu phương án tài chính tham khảo (Pre-Sales Plan)."""
    __tablename__ = "pre_sales_plans"

    plan_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    session_id: Mapped[str] = mapped_column(String(64), ForeignKey("pre_sales_sessions.session_id"), nullable=False, index=True)
    unit_code: Mapped[str] = mapped_column(String(64), nullable=False)
    scenarios_json: Mapped[dict[str, Any]] = mapped_column(JsonType, nullable=False)
    recommended_scenario_code: Mapped[str] = mapped_column(String(32), nullable=False)
    pdf_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now())

    session: Mapped["PreSalesSessionModel"] = relationship("PreSalesSessionModel", back_populates="plans")


class LeadDossierModel(Base):
    """Bảng lưu hồ sơ khách hàng bàn giao sang Sales (C-10)."""
    __tablename__ = "lead_dossiers"

    dossier_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    session_id: Mapped[str] = mapped_column(String(64), ForeignKey("pre_sales_sessions.session_id"), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(32), default="NEW", index=True)
    lead_temperature: Mapped[str] = mapped_column(String(16), default="WARM", index=True)
    customer_name: Mapped[str] = mapped_column(String(255), nullable=False)
    customer_phone_masked: Mapped[str] = mapped_column(String(32), nullable=False)
    assigned_sales_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    sla_expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    quote_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now())

    session: Mapped["PreSalesSessionModel"] = relationship("PreSalesSessionModel", back_populates="dossiers")


class QuoteModel(Base):
    """Bảng Báo giá chính thức (C-01)."""
    __tablename__ = "quotes"

    quote_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(64), default="DEFAULT", index=True)
    quote_version: Mapped[int] = mapped_column(Integer, default=1, index=True)
    status: Mapped[str] = mapped_column(String(32), default="DRAFT", index=True)
    approval_status: Mapped[str] = mapped_column(String(32), default="NOT_REQUIRED", index=True)
    pdf_status: Mapped[str] = mapped_column(String(32), default="NOT_REQUESTED", index=True)
    unit_code: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    total_contract_price_vnd: Mapped[int] = mapped_column(BigInteger, default=0)
    signature: Mapped[str | None] = mapped_column(Text, nullable=True)
    snapshot_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    pdf_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    created_by: Mapped[str] = mapped_column(String(64), nullable=False)
    approved_by: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now(), onupdate=func.now())

    snapshots: Mapped[list["QuoteSnapshotModel"]] = relationship("QuoteSnapshotModel", back_populates="quote")
    audit_events: Mapped[list["QuoteAuditEventModel"]] = relationship("QuoteAuditEventModel", back_populates="quote")


class QuoteSnapshotModel(Base):
    """Bản ghi snapshot trạng thái nghiệp vụ và tài chính bất biến của Báo giá."""
    __tablename__ = "quote_snapshots"

    snapshot_id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: str(uuid.uuid4()))
    quote_id: Mapped[str] = mapped_column(String(64), ForeignKey("quotes.quote_id"), nullable=False, index=True)
    quote_version: Mapped[int] = mapped_column(Integer, nullable=False)
    snapshot_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    payload_json: Mapped[dict[str, Any]] = mapped_column(JsonType, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now())

    quote: Mapped["QuoteModel"] = relationship("QuoteModel", back_populates="snapshots")

    __table_args__ = (
        Index("idx_quote_version", "quote_id", "quote_version", unique=True),
    )


class QuoteAuditEventModel(Base):
    """Bảng lưu vết kiểm toán liên hoàn Anti-Cyclic Hash Chain (C-07)."""
    __tablename__ = "quote_audit_events"

    event_id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: str(uuid.uuid4()))
    quote_id: Mapped[str] = mapped_column(String(64), ForeignKey("quotes.quote_id"), nullable=False, index=True)
    event_seq: Mapped[int] = mapped_column(Integer, nullable=False)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    actor_id: Mapped[str] = mapped_column(String(64), nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now())
    prev_event_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    event_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    payload_json: Mapped[dict[str, Any]] = mapped_column(JsonType, nullable=False)

    quote: Mapped["QuoteModel"] = relationship("QuoteModel", back_populates="audit_events")

    __table_args__ = (
        Index("idx_quote_audit_seq", "quote_id", "event_seq", unique=True),
    )


class TransactionalOutboxModel(Base):
    """Bảng Transactional Outbox bền vững phục vụ worker sinh PDF bất đồng bộ."""
    __tablename__ = "transactional_outbox"

    event_id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: str(uuid.uuid4()))
    aggregate_type: Mapped[str] = mapped_column(String(32), default="QUOTE")
    aggregate_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    payload_json: Mapped[dict[str, Any]] = mapped_column(JsonType, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="PENDING", index=True)
    retry_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now())
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ComplianceCheckModel(Base):
    """Bảng lưu kết quả kiểm duyệt tuân thủ thông điệp F8."""
    __tablename__ = "compliance_checks"

    check_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    message_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    overall_status: Mapped[str] = mapped_column(String(32), nullable=False)
    compliance_tier: Mapped[str] = mapped_column(String(32), nullable=False)
    claims_json: Mapped[list[dict[str, Any]]] = mapped_column(JsonType, nullable=False)
    quote_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    plan_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    can_send: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now())
