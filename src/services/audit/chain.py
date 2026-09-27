"""
Anti-Cyclic Hash Chain Engine (Spike 4)
Owner: TechLead (cuongtv_02560)
Zero-Trust Invariant: Append-Only Tamper-Evident Audit Trail for each Quote.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from sqlalchemy import desc, select
from sqlalchemy.exc import CompileError, IntegrityError, OperationalError
from sqlalchemy.ext.asyncio import AsyncSession

from src.contracts.common import canonical_json_bytes, sha256_hex
from src.db.models import QuoteAuditEventModel


class AuditChainEngine:
    """
    Engine managing the deterministic, anti-cyclic cryptographic hash chain
    for quote audit events.
    """

    GENESIS_PREV_HASH: str = "0000000000000000000000000000000000000000000000000000000000000000"

    @classmethod
    def format_timestamp_iso(cls, dt_or_str: datetime | str) -> str:
        """
        Normalize datetime or string to ISO 8601 UTC string format:
        YYYY-MM-DDTHH:MM:SS.ffffff+00:00 (guaranteeing exact deterministic hashing).
        """
        if isinstance(dt_or_str, str):
            normalized_str = dt_or_str.strip().replace(" ", "T")
            try:
                dt = datetime.fromisoformat(normalized_str)
            except Exception:
                return normalized_str
        else:
            dt = dt_or_str

        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=UTC)
        return dt.astimezone(UTC).isoformat()

    @classmethod
    def compute_event_hash(
        cls,
        prev_hash: str,
        quote_id: str,
        event_type: str,
        actor_id: str,
        occurred_at_iso: str,
        payload: dict[str, Any],
    ) -> str:
        """
        Compute deterministic SHA-256 hash for an event:
        H_i = SHA256(prev_hash | quote_id | event_type | actor_id | occurred_at_iso | canonical_payload)
        """
        canonical_payload_str = canonical_json_bytes(payload).decode("utf-8")
        norm_ts = cls.format_timestamp_iso(occurred_at_iso)
        seed_string = (
            f"{prev_hash}|{quote_id}|{event_type}|{actor_id}|"
            f"{norm_ts}|{canonical_payload_str}"
        )
        return sha256_hex(seed_string.encode("utf-8"))

    async def append_event(
        self,
        db_session: AsyncSession,
        quote_id: str,
        event_type: str,
        actor_id: str,
        payload: dict[str, Any],
        max_retries: int = 3,
    ) -> QuoteAuditEventModel:
        """
        Append an audit event to the quote's hash chain in the database.
        Uses retry loop to handle concurrent event_seq collisions
        (guarded by unique index idx_quote_audit_seq).
        """

        last_error: Exception | None = None

        for attempt in range(max_retries):
            stmt = (
                select(QuoteAuditEventModel)
                .where(QuoteAuditEventModel.quote_id == quote_id)
                .order_by(desc(QuoteAuditEventModel.event_seq))
                .limit(1)
            )

            # In PostgreSQL we can use with_for_update, in SQLite it's ignored or unsupported
            bind = db_session.get_bind()
            dialect_name = bind.dialect.name if bind else ""
            if dialect_name == "sqlite":
                res = await db_session.execute(stmt)
            else:
                try:
                    stmt_locked = stmt.with_for_update()
                    res = await db_session.execute(stmt_locked)
                except (CompileError, OperationalError):
                    # Fallback if dialect does not support with_for_update
                    res = await db_session.execute(stmt)

            latest_event = res.scalars().first()

            if latest_event is None:
                prev_hash = self.GENESIS_PREV_HASH
                new_seq = 1
            else:
                prev_hash = latest_event.event_hash
                new_seq = latest_event.event_seq + 1

            now_dt = datetime.now(UTC)
            occurred_at_iso = self.format_timestamp_iso(now_dt)

            event_hash = self.compute_event_hash(
                prev_hash=prev_hash,
                quote_id=quote_id,
                event_type=event_type,
                actor_id=actor_id,
                occurred_at_iso=occurred_at_iso,
                payload=payload,
            )

            audit_record = QuoteAuditEventModel(
                event_id=str(uuid4()),
                quote_id=quote_id,
                event_seq=new_seq,
                event_type=event_type,
                actor_id=actor_id,
                occurred_at=now_dt,
                prev_event_hash=prev_hash,
                event_hash=event_hash,
                payload_json=payload,
            )

            try:
                async with db_session.begin_nested():
                    db_session.add(audit_record)
                    await db_session.flush()
                return audit_record
            except IntegrityError:
                # Concurrent append produced same event_seq → savepoint automatically rolled back, retry
                last_error = IntegrityError(
                    f"Concurrent event_seq collision for quote {quote_id}, "
                    f"attempt {attempt + 1}/{max_retries}",
                    params=None,
                    orig=None,
                )
                continue

        # All retries exhausted
        raise last_error or RuntimeError(  # type: ignore[misc]
            f"Failed to append audit event for quote {quote_id} after {max_retries} retries"
        )
