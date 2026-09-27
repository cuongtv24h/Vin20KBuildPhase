"""
Transactional Outbox Repository for Asynchronous Task Processing (Async).
Owner: TechLead (cuongtv_02560)
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import TransactionalOutboxModel


class OutboxRepository:
    """Async repository handling enqueue and processing for Transactional Outbox."""

    @staticmethod
    async def enqueue_event(db: AsyncSession, event: TransactionalOutboxModel) -> TransactionalOutboxModel:
        db.add(event)
        await db.commit()
        await db.refresh(event)
        return event

    @staticmethod
    async def poll_pending(db: AsyncSession, limit: int = 10) -> list[TransactionalOutboxModel]:
        stmt = (
            select(TransactionalOutboxModel)
            .where(TransactionalOutboxModel.status == "PENDING")
            .order_by(TransactionalOutboxModel.created_at.asc())
            .limit(limit)
        )
        res = await db.execute(stmt)
        return list(res.scalars().all())

    @staticmethod
    async def mark_processed(db: AsyncSession, event_id: str) -> None:
        stmt = select(TransactionalOutboxModel).where(TransactionalOutboxModel.event_id == event_id)
        res = await db.execute(stmt)
        item = res.scalar_one_or_none()
        if item:
            item.status = "PROCESSED"
            item.processed_at = datetime.now(UTC)
            await db.commit()

    @staticmethod
    async def mark_failed(db: AsyncSession, event_id: str, retry_count: int) -> None:
        stmt = select(TransactionalOutboxModel).where(TransactionalOutboxModel.event_id == event_id)
        res = await db.execute(stmt)
        item = res.scalar_one_or_none()
        if item:
            item.status = "FAILED" if retry_count >= 3 else "RETRY"
            item.retry_count = retry_count
            await db.commit()
