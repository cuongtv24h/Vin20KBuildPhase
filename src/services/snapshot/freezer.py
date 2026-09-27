"""
Snapshot Freezer and Time-Travel Freeze Module
Owner: TechLead (cuongtv_02560)
Component: C-02 (Time-Travel & Policy Snapshot Engine)
Zero-Trust Invariant: Snapshot data is strictly immutable; canonical hash guarantees integrity.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.contracts.common import canonical_json_bytes, sha256_hex
from src.contracts.errors import DomainError, ErrorCode
from src.db.models import QuoteSnapshotModel


class SnapshotFreezer:
    """
    Freezes business, policy, and financial calculation context into immutable snapshots.
    """

    @staticmethod
    def compute_snapshot_hash(snapshot_payload: dict[str, Any]) -> str:
        """
        Compute deterministic SHA-256 hash using RFC 8785 canonical JSON bytes.
        """
        canonical_bytes = canonical_json_bytes(snapshot_payload)
        return sha256_hex(canonical_bytes)

    async def freeze_snapshot(
        self,
        db_session: AsyncSession,
        quote_id: str,
        version: int,
        unit_code: str,
        project_id: str,
        policy_rules: list[dict[str, Any]],
        calculation_result: dict[str, Any],
        metadata: dict[str, Any] | None = None,
    ) -> QuoteSnapshotModel:
        """
        Freeze and persist an immutable quote snapshot into the database.
        """
        # Check if snapshot for this quote_id and version already exists
        stmt = (
            select(QuoteSnapshotModel)
            .where(
                QuoteSnapshotModel.quote_id == quote_id,
                QuoteSnapshotModel.quote_version == version,
            )
        )
        existing = (await db_session.execute(stmt)).scalars().first()
        if existing is not None:
            raise DomainError(
                ErrorCode.IMMUTABLE_SNAPSHOT_VIOLATION,
                f"Snapshot for quote '{quote_id}' version {version} is immutable and already exists.",
                details={"quote_id": quote_id, "version": version},
            )

        payload: dict[str, Any] = {
            "quote_id": quote_id,
            "version": version,
            "unit_code": unit_code,
            "project_id": project_id,
            "policy_rules": policy_rules,
            "calculation_result": calculation_result,
            "metadata": metadata or {},
        }

        snapshot_hash = self.compute_snapshot_hash(payload)

        snapshot_record = QuoteSnapshotModel(
            snapshot_id=str(uuid4()),
            quote_id=quote_id,
            quote_version=version,
            payload_json=payload,
            snapshot_hash=snapshot_hash,
            created_at=datetime.now(UTC),
        )

        db_session.add(snapshot_record)
        return snapshot_record

    async def get_and_verify_snapshot(
        self,
        db_session: AsyncSession,
        quote_id: str,
        version: int,
    ) -> QuoteSnapshotModel:
        """
        Retrieve a snapshot and verify its cryptographic hash against current payload.
        """
        stmt = (
            select(QuoteSnapshotModel)
            .where(
                QuoteSnapshotModel.quote_id == quote_id,
                QuoteSnapshotModel.quote_version == version,
            )
        )
        snapshot = (await db_session.execute(stmt)).scalars().first()
        if snapshot is None:
            raise DomainError(
                ErrorCode.NOT_FOUND,
                f"Snapshot for quote '{quote_id}' version {version} not found.",
                details={"quote_id": quote_id, "version": version},
            )

        # Verify hash integrity
        recomputed_hash = self.compute_snapshot_hash(snapshot.payload_json)
        if recomputed_hash != snapshot.snapshot_hash:
            raise DomainError(
                ErrorCode.TAMPER_DETECTED,
                f"Snapshot integrity violation: payload hash '{recomputed_hash}' does not match '{snapshot.snapshot_hash}'.",
                details={"quote_id": quote_id, "version": version},
            )

        return snapshot
