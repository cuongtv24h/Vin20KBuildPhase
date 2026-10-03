"""
SQLAlchemy ORM models mapping to PostgreSQL 16 domain schemas (TD-4.2) and PEC-RAG.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Any

from pgvector.sqlalchemy import Vector
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
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from src.config import get_settings
from src.db.session import Base

settings = get_settings()

# Sử dụng JSON tương thích cho cả SQLite và PostgreSQL
JsonType = JSON().with_variant(JSONB, "postgresql")
ArrayType = JSON().with_variant(ARRAY(String), "postgresql")


# ==============================================================================
# 1. PEC-RAG & POLICY ATOM MODELS
# ==============================================================================


class PolicyModel(Base):
    """Văn bản chính sách tổng thể (PEC-RAG)."""

    __tablename__ = "policies"

    policy_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    policy_name: Mapped[str] = mapped_column(String(255), nullable=False)
    version: Mapped[str] = mapped_column(String(32), nullable=False, default="v1.0.0")
    effective_from: Mapped[date] = mapped_column(Date, nullable=False)
    effective_to: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="ACTIVE")
    document_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    source_path: Mapped[str | None] = mapped_column(String(255), nullable=True)
    metadata_json: Mapped[dict] = mapped_column(JsonType, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    atoms: Mapped[list[PolicyAtomModel]] = relationship(
        "PolicyAtomModel", back_populates="policy", cascade="all, delete-orphan"
    )


class PolicyAtomModel(Base):
    """Nguyên tử chính sách & Vector Store."""

    __tablename__ = "policy_atoms"

    atom_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    policy_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("policies.policy_id", ondelete="CASCADE"), nullable=False
    )
    atom_type: Mapped[str] = mapped_column(String(32), nullable=False)  # CLAUSE, TABLE_ROW, FOOTNOTE, DEFINITION

    chapter: Mapped[str | None] = mapped_column(String(128), nullable=True)
    article: Mapped[str | None] = mapped_column(String(128), nullable=True)
    clause: Mapped[str | None] = mapped_column(String(128), nullable=True)
    point: Mapped[str | None] = mapped_column(String(64), nullable=True)

    # Provenance
    parent_atom_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    page_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    section_path: Mapped[str | None] = mapped_column(String(255), nullable=True)
    table_coordinates: Mapped[str | None] = mapped_column(String(64), nullable=True)
    line_start: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    line_end: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    # Text contents
    canonical_text: Mapped[str] = mapped_column(Text, nullable=False)
    retrieval_text: Mapped[str] = mapped_column(Text, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)

    # Validity & Scope
    valid_from: Mapped[date] = mapped_column(Date, nullable=False)
    valid_to: Mapped[date] = mapped_column(Date, nullable=False)
    customer_tiers: Mapped[list[str]] = mapped_column(ArrayType, default=lambda: ["ALL"])
    service_codes: Mapped[list[str]] = mapped_column(ArrayType, default=lambda: ["ALL"])
    channel: Mapped[str] = mapped_column(String(32), default="ALL")

    # Vector Embedding
    embedding = mapped_column(Vector(settings.embedding_dim), nullable=True)
    embedding_model_id: Mapped[str] = mapped_column(String(64), default=settings.embedding_model_id)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    policy: Mapped[PolicyModel] = relationship("PolicyModel", back_populates="atoms")


class PolicyEdgeModel(Base):
    """Đồ thị quan hệ quy tắc chính sách phục vụ TDEC Closure."""

    __tablename__ = "policy_edges"

    edge_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    source_atom_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("policy_atoms.atom_id", ondelete="CASCADE"), nullable=False
    )
    target_atom_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("policy_atoms.atom_id", ondelete="CASCADE"), nullable=False
    )
    edge_type: Mapped[str] = mapped_column(
        String(32), nullable=False
    )  # REQUIRES, EXCLUDES, SUPERSEDES, REFERENCES, TABLE_HAS_FOOTNOTE
    source_authority: Mapped[str] = mapped_column(String(64), nullable=False, default="CANONICAL_RULE")
    validation_status: Mapped[str] = mapped_column(String(32), nullable=False, default="APPROVED_FOR_USE")
    reviewed_by: Mapped[str | None] = mapped_column(String(64), nullable=True)
    edge_version: Mapped[str] = mapped_column(String(32), nullable=False, default="v1")
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class EvidenceBundleModel(Base):
    """Lưu trữ chứng từ mật mã EvidenceBundle phục vụ Pricing Engine & Audit."""

    __tablename__ = "evidence_bundles"

    bundle_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    decision_status: Mapped[str] = mapped_column(String(32), nullable=False)  # VERIFIED
    canonical_bundle_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    query_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    transaction_context_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    policy_snapshot_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    bundle_payload: Mapped[dict] = mapped_column(JsonType, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AbstentionCertificateModel(Base):
    """Lưu trữ chứng từ từ chối kết luận AbstentionCertificate."""

    __tablename__ = "abstention_certificates"

    certificate_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    decision_status: Mapped[str] = mapped_column(String(32), nullable=False)  # ABSTAINED
    canonical_certificate_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    query_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    policy_snapshot_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    reason_codes: Mapped[list[str]] = mapped_column(ArrayType, nullable=False)
    certificate_payload: Mapped[dict] = mapped_column(JsonType, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


# ==============================================================================
# 2. UPSTREAM DOMAIN MODELS (TD-4.2)
# ==============================================================================


class ProjectModel(Base):
    """Bảng dự án bất động sản."""

    __tablename__ = "projects"

    project_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(64), default="DEFAULT", index=True)
    project_name: Mapped[str] = mapped_column(String(255), nullable=False)
    legal_entity_name: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now())

    units: Mapped[list[UnitModel]] = relationship("UnitModel", back_populates="project")


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
    #: Diện tích thông thuỷ (m²). Chốt đợt 20: DB vận hành thiếu cột này nên mọi câu trả lời phải in "—"
    #: hoặc suy diễn theo loại căn. Nay là dữ liệu thật của căn (script `migrate_units_area_view.py` sinh
    #: giá trị ban đầu cho các căn cũ, sau đó cập nhật trực tiếp khi có số chính thức).
    area_m2: Mapped[float | None] = mapped_column(Float, nullable=True)
    #: Hướng nhìn / view của căn. Tên cột `view` theo chốt đợt 20 — khớp trường `view` của dữ liệu canonical.
    view: Mapped[str | None] = mapped_column(String(128), nullable=True)

    project: Mapped[ProjectModel] = relationship("ProjectModel", back_populates="units")


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

    chunks: Mapped[list[PolicyChunkModel]] = relationship("PolicyChunkModel", back_populates="document")
    rules: Mapped[list[PolicyRuleModel]] = relationship("PolicyRuleModel", back_populates="document")


class PolicyChunkModel(Base):
    """Bảng lưu trữ chunk ngữ nghĩa để tìm kiếm Time-Travel RAG."""

    __tablename__ = "policy_chunks"

    chunk_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    document_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("policy_documents.document_id"), nullable=False, index=True
    )
    clause_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    section: Mapped[str | None] = mapped_column(String(128), nullable=True)
    page: Mapped[int] = mapped_column(Integer, nullable=False)
    chunk_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    embedding_json: Mapped[dict[str, Any] | None] = mapped_column(JsonType, nullable=True)

    document: Mapped[PolicyDocumentModel] = relationship("PolicyDocumentModel", back_populates="chunks")


class PolicyRuleModel(Base):
    """Bảng quy tắc chính sách có cấu trúc F9."""

    __tablename__ = "policy_rules"

    rule_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    policy_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("policy_documents.document_id"), nullable=False, index=True
    )
    policy_version: Mapped[str] = mapped_column(String(32), nullable=False)
    clause_id: Mapped[str] = mapped_column(String(64), nullable=False)
    rule_type: Mapped[str] = mapped_column(String(64), nullable=False)
    condition_json: Mapped[dict[str, Any]] = mapped_column(JsonType, nullable=False)
    benefit_formula: Mapped[dict[str, Any]] = mapped_column(JsonType, nullable=False)
    priority: Mapped[int] = mapped_column(Integer, default=10)
    status: Mapped[str] = mapped_column(String(32), default="DRAFT", index=True)
    regression_test_pass_rate: Mapped[float] = mapped_column(Float, default=0.0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now())

    document: Mapped[PolicyDocumentModel] = relationship("PolicyDocumentModel", back_populates="rules")


class PreSalesSessionModel(Base):
    """Bảng lưu trữ phiên chat tư vấn Pre-Sales (C-09)."""

    __tablename__ = "pre_sales_sessions"

    session_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(64), default="DEFAULT", index=True)
    status: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    constraints_json: Mapped[dict[str, Any] | None] = mapped_column(JsonType, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now())
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    consents: Mapped[list[CustomerConsentModel]] = relationship(
        "CustomerConsentModel", back_populates="session", cascade="all, delete-orphan"
    )
    plans: Mapped[list[PreSalesPlanModel]] = relationship(
        "PreSalesPlanModel", back_populates="session", cascade="all, delete-orphan"
    )
    dossiers: Mapped[list[LeadDossierModel]] = relationship(
        "LeadDossierModel", back_populates="session", cascade="all, delete-orphan"
    )


class CustomerConsentModel(Base):
    """Bảng ghi nhận xác nhận đồng thuận chia sẻ thông tin cá nhân (F6)."""

    __tablename__ = "customer_consents"

    consent_id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("pre_sales_sessions.session_id"), nullable=False, index=True
    )
    customer_name: Mapped[str] = mapped_column(String(255), nullable=False)
    customer_phone: Mapped[str] = mapped_column(String(32), nullable=False)
    customer_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    consent_scope: Mapped[str] = mapped_column(String(255), default="PRE_SALES_ADVISORY_AND_SALES_CONTACT")
    ip_address: Mapped[str | None] = mapped_column(String(64), nullable=True)
    granted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now())

    session: Mapped[PreSalesSessionModel] = relationship("PreSalesSessionModel", back_populates="consents")


class PreSalesPlanModel(Base):
    """Bảng lưu phương án tài chính tham khảo (Pre-Sales Plan)."""

    __tablename__ = "pre_sales_plans"

    plan_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    session_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("pre_sales_sessions.session_id"), nullable=False, index=True
    )
    unit_code: Mapped[str] = mapped_column(String(64), nullable=False)
    scenarios_json: Mapped[dict[str, Any]] = mapped_column(JsonType, nullable=False)
    recommended_scenario_code: Mapped[str] = mapped_column(String(32), nullable=False)
    pdf_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now())

    session: Mapped[PreSalesSessionModel] = relationship("PreSalesSessionModel", back_populates="plans")


class LeadDossierModel(Base):
    """Bảng lưu hồ sơ khách hàng bàn giao sang Sales (C-10)."""

    __tablename__ = "lead_dossiers"

    dossier_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    session_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("pre_sales_sessions.session_id"), nullable=False, index=True
    )
    status: Mapped[str] = mapped_column(String(32), default="NEW", index=True)
    lead_temperature: Mapped[str] = mapped_column(String(16), default="WARM", index=True)
    customer_name: Mapped[str] = mapped_column(String(255), nullable=False)
    customer_phone_masked: Mapped[str] = mapped_column(String(32), nullable=False)
    assigned_sales_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    sla_expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    quote_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now())

    session: Mapped[PreSalesSessionModel] = relationship("PreSalesSessionModel", back_populates="dossiers")


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
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), onupdate=func.now()
    )

    snapshots: Mapped[list[QuoteSnapshotModel]] = relationship(
        "QuoteSnapshotModel", back_populates="quote", cascade="all, delete-orphan"
    )
    audit_events: Mapped[list[QuoteAuditEventModel]] = relationship(
        "QuoteAuditEventModel", back_populates="quote", cascade="all, delete-orphan"
    )

    def __init__(self, **kwargs: Any) -> None:
        if "version" in kwargs and "quote_version" not in kwargs:
            kwargs["quote_version"] = kwargs.pop("version")
        super().__init__(**kwargs)

    @property
    def version(self) -> int:
        return self.quote_version

    @version.setter
    def version(self, val: int) -> None:
        self.quote_version = val


class QuoteSnapshotModel(Base):
    """Bản ghi snapshot trạng thái nghiệp vụ và tài chính bất biến của Báo giá."""

    __tablename__ = "quote_snapshots"

    snapshot_id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: str(uuid.uuid4()))
    quote_id: Mapped[str] = mapped_column(String(64), ForeignKey("quotes.quote_id"), nullable=False, index=True)
    quote_version: Mapped[int] = mapped_column(Integer, nullable=False)
    snapshot_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    payload_json: Mapped[dict[str, Any]] = mapped_column(JsonType, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now())

    quote: Mapped[QuoteModel] = relationship("QuoteModel", back_populates="snapshots")

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

    quote: Mapped[QuoteModel] = relationship("QuoteModel", back_populates="audit_events")

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


# ==============================================================================
# 5. USER & AUTH MODELS
# ==============================================================================


class UserModel(Base):
    """Bảng người dùng nội bộ: user | password | email | phone (role phân quyền)."""

    __tablename__ = "users"

    user: Mapped[str] = mapped_column("user", String(64), primary_key=True)
    password: Mapped[str] = mapped_column("password", String(64), nullable=False)
    email: Mapped[str] = mapped_column("email", String(255), unique=True, index=True, nullable=False)
    phone: Mapped[str | None] = mapped_column("phone", String(32), nullable=True)
    role: Mapped[str] = mapped_column("role", String(32), default="SALE", nullable=False)

    @property
    def user_id(self) -> str:
        return self.user

    @property
    def password_hash(self) -> str:
        return self.password

    @property
    def full_name(self) -> str:
        return self.user

    @property
    def is_active(self) -> bool:
        return True


class TTSSettingsModel(Base):
    """Thiết lập đọc câu trả lời Copilot (Text-to-Speech) — Admin đặt mặc định, Sale ghi đè riêng.

    Vì sao có bảng này thay vì hằng số trong code: 20k Sale cần đổi giọng/tốc độ đọc mà không cần
    deploy; ngược lại không thể để mỗi người âm thầm đổi giọng cho toàn hệ thống. Nên `scope` là
    khoá chính: `default` (toàn hệ thống, ghi bởi ADMIN/MANAGER) hoặc `user:<user_id>` (sở thích
    riêng của từng nhân viên). Khi đọc, hệ thống lấy hồ sơ người dùng trước, không có thì lấy mặc định.

    `provider` trỏ tới danh mục trong `src/services/tts_providers.py` (`browser` là miễn phí và luôn
    sẵn sàng). Khoá API của nhà cung cấp TTS **không** lưu ở đây.
    """

    __tablename__ = "tts_settings"

    scope: Mapped[str] = mapped_column(String(64), primary_key=True, default="default")
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    auto_speak: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    provider: Mapped[str] = mapped_column(String(32), nullable=False, default="browser")
    model: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    voice: Mapped[str] = mapped_column(String(64), nullable=False, default="vi-VN")
    speed: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    max_chars_per_turn: Mapped[int] = mapped_column(Integer, nullable=False, default=600)
    updated_by: Mapped[str | None] = mapped_column(String(64), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class TTSFeedbackModel(Base):
    """Phản hồi về giọng đọc (nghe ổn hay không) — vòng lặp để chọn giọng phù hợp thực tế.

    Không đo "hay/dở" bằng cảm tính người viết code: ghi lại lượt nghe, giọng nào, ai nghe, khen/chê
    và lý do (đã cắt bớt, bỏ ký tự điều khiển) để báo cáo chọn giọng dựa trên dữ liệu.
    """

    __tablename__ = "tts_feedback"

    feedback_id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: f"TTSFB-{uuid.uuid4().hex[:10]}")
    user_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    conversation_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    voice: Mapped[str] = mapped_column(String(64), nullable=False)
    #: 1 = nghe ổn, -1 = nghe chưa ổn.
    rating: Mapped[int] = mapped_column(Integer, nullable=False)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class TTSProviderModel(Base):
    """Nhà cung cấp Text-to-Speech do Admin khai báo trong giao diện (không phải sửa `.env`).

    Cùng cơ chế với `LLMProviderModel` (chốt đợt 22 — người dùng yêu cầu "dùng sẵn cơ chế cũ đã có"):

    - Khoá API lưu **đã mã hoá** (Fernet, `src/services/llm_secrets.py`), API chỉ trả dạng che `sk-…abcd`.
    - Ưu tiên **DB → ENV**; ENV chỉ dùng khi DB chưa có khoá cho nhà cung cấp đó.
    - Một bản ghi có thể là **bản ghi đè** của nhà cung cấp dựng sẵn trong danh mục (ví dụ sửa đơn giá
      Viettel, nhập khoá cho Azure) **hoặc** một nhà cung cấp **mới hoàn toàn** (self-host, gateway nội bộ,
      nhà cung cấp khác ngoài danh mục) — đúng yêu cầu "cho phép thêm mới nhà cung cấp ngoài các nhà cung
      cấp sẵn".
    """

    __tablename__ = "tts_providers"

    provider_id: Mapped[str] = mapped_column(
        String(64), primary_key=True, default=lambda: f"TTS-{uuid.uuid4().hex[:10]}"
    )
    #: Mã nhà cung cấp (slug) — trùng mã trong danh mục nghĩa là bản ghi ĐÈ; mã lạ nghĩa là nhà cung cấp MỚI.
    provider: Mapped[str] = mapped_column(String(48), nullable=False)
    label: Mapped[str] = mapped_column(String(128), nullable=False)
    #: `browser` (đọc tại máy, 0 đồng) hoặc `api` (gọi qua backend, cần khoá).
    mode: Mapped[str] = mapped_column(String(16), nullable=False, default="api")
    base_url: Mapped[str | None] = mapped_column(String(255), nullable=True)
    default_model: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    env_key: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    #: Đơn giá theo 1 triệu ký tự (đơn vị ở `currency`) — cùng công thức với danh mục dựng sẵn.
    price_per_1m_chars: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    currency: Mapped[str] = mapped_column(String(8), nullable=False, default="USD")
    price_note: Mapped[str] = mapped_column(Text, nullable=False, default="")
    verified_at: Mapped[str] = mapped_column(String(16), nullable=False, default="")
    note: Mapped[str] = mapped_column(Text, nullable=False, default="")
    #: Danh sách giọng dạng JSON: `[{"code": "...", "label": "...", "gender": "female"}]`.
    voices_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    supports_streaming: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    voice_cloning: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    api_key_encrypted: Mapped[str] = mapped_column(Text, nullable=False, default="")
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=50)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    last_test_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    last_test_latency_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    last_tested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class LLMProviderModel(Base):
    """Nhà cung cấp LLM do Admin khai báo trong giao diện (không phải sửa .env).

    Thứ tự ưu tiên: bản ghi trong DB (theo `priority` tăng dần) được dùng trước; **nếu DB chưa có
    bản ghi nào đang bật** thì hệ thống mới rơi về cấu hình ENV. Nhờ vậy Admin tự thêm/đổi khoá
    ngay trên UI, không cần deploy lại.

    `api_key_encrypted` lưu khoá đã mã hoá (Fernet, xem `src/services/llm/secrets.py`); API trả về
    chỉ hiển thị dạng che `sk-…abcd`. `input_price_per_1m` / `output_price_per_1m` là **đơn giá**
    để quy ra chi phí mỗi lượt gọi (đo độ tiêu tốn).
    """

    __tablename__ = "llm_providers"

    provider_id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: f"LLM-{uuid.uuid4().hex[:10]}")
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    provider: Mapped[str] = mapped_column(String(32), nullable=False, default="openai")
    base_url: Mapped[str | None] = mapped_column(String(255), nullable=True)
    model_name: Mapped[str] = mapped_column(String(128), nullable=False, default="gpt-4o-mini")
    api_key_encrypted: Mapped[str] = mapped_column(Text, nullable=False, default="")
    #: Đơn giá theo 1 triệu token (đơn vị ở `currency`) — dùng để tính chi phí đo độ tiêu tốn.
    input_price_per_1m: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    output_price_per_1m: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    currency: Mapped[str] = mapped_column(String(8), nullable=False, default="USD")
    temperature: Mapped[float] = mapped_column(Float, nullable=False, default=0.2)
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=10)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    last_test_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    last_test_latency_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    last_tested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

