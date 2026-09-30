"""RAG Domain Schemas and Evidence Contracts for PricePolicy AI Agent.

These schemas define the cryptographic evidence coordinates, time-travel filters,
and structured policy evidence output required for zero-hallucination verification
in downstream LangGraph reasoning nodes.
"""

from __future__ import annotations

import hashlib
from datetime import date
from typing import Any

from pydantic import BaseModel, Field, computed_field


class EvidenceCoordinate(BaseModel):
    """Pinpoint cryptographic coordinate of an exact legal clause inside a policy document."""

    policy_id: str = Field(
        ...,
        description="Unique identifier of the policy document (e.g. 'QD-2024-01-VTB')",
    )
    chapter: str | None = Field(
        default=None,
        description="Chapter identifier if present (e.g. 'Chương II')",
    )
    article: str = Field(
        ...,
        description="Article title / number (e.g. 'Điều 4')",
    )
    clause: str = Field(
        ...,
        description="Clause identifier (e.g. 'Khoản 2')",
    )
    point: str | None = Field(
        default=None,
        description="Point identifier if present (e.g. 'Điểm a')",
    )
    line_span: tuple[int, int] | None = Field(
        default=None,
        description="Tuple of (start_line, end_line) in the source policy file",
    )
    content_sha256: str = Field(
        ...,
        description="SHA-256 hash of the exact clause text for cryptographic anti-tamper verification",
    )

    @computed_field
    @property
    def citation_path(self) -> str:
        """Formatted human-readable citation path: [policy_id] Điều X > Khoản Y > Điểm Z."""
        parts = [self.policy_id]
        if self.chapter:
            parts.append(self.chapter)
        parts.append(self.article)
        parts.append(self.clause)
        if self.point:
            parts.append(self.point)
        return " > ".join(parts)


class TimeTravelFilter(BaseModel):
    """Temporal and contextual metadata filter for SQL/pgvector pre-filtering."""

    transaction_date: date = Field(
        ...,
        description="Date when the transaction occurred or the policy is being evaluated against",
    )
    customer_tier: str | None = Field(
        default=None,
        description="Customer tier (e.g., 'STANDARD', 'VIP', 'PRIORITY', 'SME')",
    )
    service_code: str | None = Field(
        default=None,
        description="Financial service/product code (e.g., 'TRANSFER_IB', 'LOAN_MORTGAGE', 'SAVINGS')",
    )
    channel: str | None = Field(
        default=None,
        description="Transaction channel (e.g., 'INTERNET_BANKING', 'MOBILE', 'COUNTER')",
    )
    currency: str | None = Field(
        default="VND",
        description="Currency ISO code",
    )


class AttributedPolicyEvidence(BaseModel):
    """Complete, verified policy clause evidence passed to downstream reasoning nodes.

    Guarantees that every assertion made by the financial explanation node can be
    traced back to an exact legal coordinate with 100% fidelity.
    """

    coordinate: EvidenceCoordinate = Field(
        ...,
        description="Cryptographic coordinate identifying the source policy",
    )
    policy_title: str = Field(
        ...,
        description="Full title of the legal decision or policy document",
    )
    verbatim_text: str = Field(
        ...,
        description="Untouched verbatim text of the retrieved clause",
    )
    valid_from: date = Field(
        ...,
        description="Date the policy became effective",
    )
    valid_to: date = Field(
        ...,
        description="Date the policy expired (or 9999-12-31 if currently active)",
    )
    applicability_conditions: dict[str, Any] = Field(
        default_factory=dict,
        description="Extracted structured criteria (e.g., min_balance, customer_types, limits)",
    )
    similarity_score: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Vector or hybrid retrieval relevance score",
    )
    is_superseded: bool = Field(
        default=False,
        description="Flag indicating if this clause was superseded by a newer policy",
    )
    exclusion_group: str | None = Field(
        default=None,
        description="Identifier of any mutual exclusion group this clause belongs to",
    )

    def verify_integrity(self) -> bool:
        """Verify that the verbatim_text matches the SHA-256 hash in coordinate."""
        computed_hash = hashlib.sha256(self.verbatim_text.strip().encode("utf-8")).hexdigest()
        return computed_hash == self.coordinate.content_sha256


class RetrievedClause(BaseModel):
    """Intermediate candidate clause before mutual exclusion pruning and final binding."""

    node_id: str
    policy_id: str
    policy_title: str
    chapter: str | None = None
    article: str
    clause: str
    point: str | None = None
    text: str
    valid_from: date
    valid_to: date
    customer_tiers: list[str] = Field(default_factory=list)
    service_codes: list[str] = Field(default_factory=list)
    exclusion_group: str | None = None
    priority: int = Field(default=0, description="Higher number means higher precedence in conflicts")
    score: float = 0.0
    metadata: dict[str, Any] = Field(default_factory=dict)
