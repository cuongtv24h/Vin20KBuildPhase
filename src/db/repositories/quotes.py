"""
Quote Repository managing Official Quotes, Snapshots, and Atomic Transactions (Async).
Owner: TechLead (cuongtv_02560)
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.contracts.enums import ApprovalStatus, PdfStatus, QuoteWorkflowStatus
from src.db.models import (
    QuoteAuditEventModel,
    QuoteModel,
    QuoteSnapshotModel,
    TransactionalOutboxModel,
)


class QuoteRepository:
    """Async repository handling persistence for Official Quotes, Snapshots, and Outbox."""

    @staticmethod
    async def get_by_id(db: AsyncSession, quote_id: str, tenant_id: str = "DEFAULT") -> QuoteModel | None:
        stmt = select(QuoteModel).where(
            QuoteModel.quote_id == quote_id,
            QuoteModel.tenant_id == tenant_id,
        )
        res = await db.execute(stmt)
        return res.scalar_one_or_none()

    @staticmethod
    async def get_snapshot(
        db: AsyncSession, quote_id: str, quote_version: int
    ) -> QuoteSnapshotModel | None:
        stmt = select(QuoteSnapshotModel).where(
            QuoteSnapshotModel.quote_id == quote_id,
            QuoteSnapshotModel.quote_version == quote_version,
        )
        res = await db.execute(stmt)
        return res.scalar_one_or_none()

    @staticmethod
    async def list_quotes(
        db: AsyncSession,
        tenant_id: str = "DEFAULT",
        status: str | None = None,
        unit_code: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[QuoteModel]:
        stmt = select(QuoteModel).where(QuoteModel.tenant_id == tenant_id)
        if status:
            stmt = stmt.where(QuoteModel.status == status)
        if unit_code:
            stmt = stmt.where(QuoteModel.unit_code == unit_code)
        stmt = stmt.order_by(QuoteModel.created_at.desc()).limit(limit).offset(offset)
        res = await db.execute(stmt)
        return list(res.scalars().all())

    @staticmethod
    async def create_quote(
        db: AsyncSession,
        quote: QuoteModel,
        initial_snapshot: QuoteSnapshotModel | None = None,
    ) -> QuoteModel:
        db.add(quote)
        if initial_snapshot:
            db.add(initial_snapshot)
        await db.commit()
        await db.refresh(quote)
        return quote

    @staticmethod
    async def update_quote(db: AsyncSession, quote: QuoteModel) -> QuoteModel:
        quote.updated_at = datetime.now(UTC)
        db.add(quote)
        await db.commit()
        await db.refresh(quote)
        return quote

    @staticmethod
    async def save_snapshot(db: AsyncSession, snapshot: QuoteSnapshotModel) -> QuoteSnapshotModel:
        stmt = select(QuoteSnapshotModel).where(
            QuoteSnapshotModel.quote_id == snapshot.quote_id,
            QuoteSnapshotModel.quote_version == snapshot.quote_version,
        )
        res = await db.execute(stmt)
        existing = res.scalar_one_or_none()
        if existing:
            existing.snapshot_hash = snapshot.snapshot_hash
            existing.payload_json = snapshot.payload_json
            await db.commit()
            await db.refresh(existing)
            return existing
        else:
            db.add(snapshot)
            await db.commit()
            await db.refresh(snapshot)
            return snapshot

    @staticmethod
    async def supersede_and_create_new_version(
        db: AsyncSession,
        old_quote: QuoteModel,
        new_version_num: int,
        creator_id: str,
    ) -> QuoteModel:
        """
        Implements Revision Loop (N-17):
        Marks old version as SUPERSEDED and creates a new QuoteModel record.
        """
        old_quote.status = QuoteWorkflowStatus.SUPERSEDED.value
        old_quote.updated_at = datetime.now(UTC)
        db.add(old_quote)

        new_quote_id = f"{old_quote.quote_id}-V{new_version_num}"
        new_quote = QuoteModel(
            quote_id=new_quote_id,
            tenant_id=old_quote.tenant_id,
            quote_version=new_version_num,
            status=QuoteWorkflowStatus.CALCULATING.value,
            approval_status=ApprovalStatus.NOT_REQUIRED.value,
            pdf_status=PdfStatus.NOT_REQUESTED.value,
            unit_code=old_quote.unit_code,
            total_contract_price_vnd=old_quote.total_contract_price_vnd,
            created_by=creator_id,
        )
        db.add(new_quote)
        await db.commit()
        await db.refresh(new_quote)
        return new_quote

    @staticmethod
    async def commit_approval_with_outbox(
        db: AsyncSession,
        quote: QuoteModel,
        snapshot: QuoteSnapshotModel,
        audit_event: QuoteAuditEventModel,
        outbox_event: TransactionalOutboxModel,
    ) -> None:
        """
        Atomic Commit-Discard single transaction:
        Updates quote status to APPROVED, records snapshot, appends audit hash event,
        and enqueues outbox event atomically.
        """
        db.add(quote)
        stmt = select(QuoteSnapshotModel).where(
            QuoteSnapshotModel.quote_id == snapshot.quote_id,
            QuoteSnapshotModel.quote_version == snapshot.quote_version,
        )
        res = await db.execute(stmt)
        existing = res.scalar_one_or_none()
        if existing:
            existing.snapshot_hash = snapshot.snapshot_hash
            existing.payload_json = snapshot.payload_json
        else:
            db.add(snapshot)
        db.add(audit_event)
        db.add(outbox_event)
        await db.commit()
        await db.refresh(quote)
