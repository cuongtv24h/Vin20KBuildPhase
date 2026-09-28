"""SQLAlchemy ORM Models for PricePolicy Multi-Tier Database."""

from __future__ import annotations

from datetime import date, datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from src.config import get_settings

settings = get_settings()


class Base(DeclarativeBase):
    pass


class PolicyModel(Base):
    """Văn bản chính sách tổng thể."""

    __tablename__ = "policies"

    policy_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    policy_name: Mapped[str] = mapped_column(String(255), nullable=False)
    version: Mapped[str] = mapped_column(String(32), nullable=False, default="v1.0.0")
    effective_from: Mapped[date] = mapped_column(Date, nullable=False)
    effective_to: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="ACTIVE")
    document_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    source_path: Mapped[str | None] = mapped_column(String(255), nullable=True)
    metadata_json: Mapped[dict] = mapped_column(JSONB, default=dict)
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
    customer_tiers: Mapped[list[str]] = mapped_column(ARRAY(String), default=lambda: ["ALL"])
    service_codes: Mapped[list[str]] = mapped_column(ARRAY(String), default=lambda: ["ALL"])
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
    bundle_payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AbstentionCertificateModel(Base):
    """Lưu trữ chứng từ từ chối kết luận AbstentionCertificate."""

    __tablename__ = "abstention_certificates"

    certificate_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    decision_status: Mapped[str] = mapped_column(String(32), nullable=False)  # ABSTAINED
    canonical_certificate_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    query_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    policy_snapshot_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    reason_codes: Mapped[list[str]] = mapped_column(ARRAY(String), nullable=False)
    certificate_payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
