"""
Audit Repository for Quote Audit Events (Anti-Cyclic Hash Chain C-07 - Async).
Owner: TechLead (cuongtv_02560)
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import QuoteAuditEventModel


class AuditRepository:
    """Async repository managing append-only Quote Audit Events."""

    @staticmethod
    async def append_event(db: AsyncSession, event: QuoteAuditEventModel) -> QuoteAuditEventModel:
        db.add(event)
        await db.commit()
        await db.refresh(event)
        return event

    @staticmethod
    async def get_events_by_quote_id(db: AsyncSession, quote_id: str) -> list[QuoteAuditEventModel]:
        stmt = (
            select(QuoteAuditEventModel)
            .where(QuoteAuditEventModel.quote_id == quote_id)
            .order_by(QuoteAuditEventModel.event_seq.asc())
        )
        res = await db.execute(stmt)
        return list(res.scalars().all())

    @staticmethod
    async def get_latest_event(db: AsyncSession, quote_id: str) -> QuoteAuditEventModel | None:
        stmt = (
            select(QuoteAuditEventModel)
            .where(QuoteAuditEventModel.quote_id == quote_id)
            .order_by(QuoteAuditEventModel.event_seq.desc())
            .limit(1)
        )
        res = await db.execute(stmt)
        return res.scalar_one_or_none()
