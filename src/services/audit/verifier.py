"""
Genesis Audit Chain Verifier Module (Spike 4)
Owner: TechLead (cuongtv_02560)
Zero-Trust Invariant: Verify cryptographic integrity from Genesis to Leaf.
"""

from __future__ import annotations

from sqlalchemy import asc, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.contracts.errors import DomainError, ErrorCode
from src.db.models import QuoteAuditEventModel
from src.services.audit.chain import AuditChainEngine


class AuditChainVerifier:
    """
    Cryptographic auditor verifying the append-only hash chain of quote events.
    """

    def __init__(self, chain_engine: AuditChainEngine | None = None) -> None:
        self.chain_engine = chain_engine or AuditChainEngine()

    async def verify_chain_integrity(
        self,
        db_session: AsyncSession,
        quote_id: str,
        raise_on_error: bool = False,
        events: list[QuoteAuditEventModel] | None = None,
    ) -> tuple[bool, str]:
        """
        Traverse the audit chain for quote_id from Genesis to Leaf.
        Returns (is_valid, message). If raise_on_error=True, raises DomainError on tamper.
        """
        if events is None:
            stmt = (
                select(QuoteAuditEventModel)
                .where(QuoteAuditEventModel.quote_id == quote_id)
                .order_by(asc(QuoteAuditEventModel.event_seq))
            )
            result = await db_session.execute(stmt)
            events = list(result.scalars().all())

        if not events:
            return True, "EMPTY_CHAIN"

        expected_prev_hash = self.chain_engine.GENESIS_PREV_HASH

        for record in events:
            seq = record.event_seq
            ev_type = record.event_type
            actor = record.actor_id
            occurred_at = record.occurred_at
            recorded_prev_hash = record.prev_event_hash
            recorded_event_hash = record.event_hash
            payload = record.payload_json

            occurred_at_iso = self.chain_engine.format_timestamp_iso(occurred_at)

            # 1. Check link continuity
            if recorded_prev_hash != expected_prev_hash:
                msg = (
                    f"BROKEN_LINK_AT_SEQ_{seq}: expected prev_hash "
                    f"'{expected_prev_hash}', got '{recorded_prev_hash}'"
                )
                if raise_on_error:
                    raise DomainError(ErrorCode.TAMPER_DETECTED, msg, {"seq": seq, "quote_id": quote_id})
                return False, msg

            # 2. Recalculate deterministic hash
            recomputed_hash = self.chain_engine.compute_event_hash(
                prev_hash=recorded_prev_hash,
                quote_id=quote_id,
                event_type=ev_type,
                actor_id=actor,
                occurred_at_iso=occurred_at_iso,
                payload=payload,
            )

            if recomputed_hash != recorded_event_hash:
                msg = (
                    f"TAMPER_DETECTED_AT_SEQ_{seq}: data payload was modified! "
                    f"Expected hash '{recomputed_hash}', got recorded '{recorded_event_hash}'"
                )
                if raise_on_error:
                    raise DomainError(ErrorCode.TAMPER_DETECTED, msg, {"seq": seq, "quote_id": quote_id})
                return False, msg

            expected_prev_hash = recorded_event_hash

        return True, "CHAIN_INTEGRITY_VERIFIED_100%"
