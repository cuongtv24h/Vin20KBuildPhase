"""
Unit & Integration Tests for Spike 4: Anti-Cyclic Hash Chain & Genesis Verification
Owner: TechLead (cuongtv_02560)
"""

import pytest
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.contracts.errors import DomainError, ErrorCode
from src.db.models import Base, QuoteAuditEventModel
from src.services.audit.chain import AuditChainEngine
from src.services.audit.verifier import AuditChainVerifier


@pytest.mark.asyncio
async def test_audit_chain_sequential_append_and_verification() -> None:
    """Test appending multiple events forms an unbroken, verifiable hash chain."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

    async with session_factory() as session:
        chain_engine = AuditChainEngine()
        verifier = AuditChainVerifier(chain_engine=chain_engine)

        quote_id = "Q-TEST-CHAIN-001"

        # 1. Empty chain check
        is_valid, msg = await verifier.verify_chain_integrity(session, quote_id)
        assert is_valid is True
        assert msg == "EMPTY_CHAIN"

        # 2. Append Event 1: Genesis event
        ev1 = await chain_engine.append_event(
            db_session=session,
            quote_id=quote_id,
            event_type="QUOTE_DRAFT_CREATED",
            actor_id="sales_alice",
            payload={"initial_price": 5_000_000_000},
        )
        await session.commit()

        assert ev1.event_seq == 1
        assert ev1.prev_event_hash == chain_engine.GENESIS_PREV_HASH
        assert len(ev1.event_hash) == 64

        # 3. Append Event 2: Calculation completed
        ev2 = await chain_engine.append_event(
            db_session=session,
            quote_id=quote_id,
            event_type="PRICING_CALCULATED",
            actor_id="system_engine",
            payload={"scenario": "PA-CHUDONG", "discount": 200_000_000},
        )
        await session.commit()

        assert ev2.event_seq == 2
        assert ev2.prev_event_hash == ev1.event_hash

        # 4. Append Event 3: Quote approved
        ev3 = await chain_engine.append_event(
            db_session=session,
            quote_id=quote_id,
            event_type="QUOTE_APPROVED",
            actor_id="manager_bob",
            payload={"approved": True, "signature": "sig_xyz_123"},
        )
        await session.commit()

        assert ev3.event_seq == 3
        assert ev3.prev_event_hash == ev2.event_hash

        # 5. Verify whole chain from Genesis to Leaf
        is_valid, msg = await verifier.verify_chain_integrity(session, quote_id)
        assert is_valid is True
        assert msg == "CHAIN_INTEGRITY_VERIFIED_100%"


@pytest.mark.asyncio
async def test_tamper_detection_on_payload_modification() -> None:
    """Modifying event payload in DB must trigger tamper detection error."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

    async with session_factory() as session:
        chain_engine = AuditChainEngine()
        verifier = AuditChainVerifier(chain_engine=chain_engine)
        quote_id = "Q-TEST-TAMPER-001"

        await chain_engine.append_event(
            session, quote_id, "EVENT_1", "user_1", {"amount": 100}
        )
        ev2 = await chain_engine.append_event(
            session, quote_id, "EVENT_2", "user_1", {"amount": 200}
        )
        await session.commit()

        # Malicious modification: tamper with EVENT_2 payload directly in DB
        await session.execute(
            update(QuoteAuditEventModel)
            .where(QuoteAuditEventModel.event_id == ev2.event_id)
            .values(payload_json={"amount": 999_999_999})
        )
        await session.commit()

        # Verification must detect tamper
        is_valid, msg = await verifier.verify_chain_integrity(session, quote_id)
        assert is_valid is False
        assert "TAMPER_DETECTED" in msg

        # With raise_on_error=True
        with pytest.raises(DomainError) as exc_info:
            await verifier.verify_chain_integrity(session, quote_id, raise_on_error=True)
        assert exc_info.value.code == ErrorCode.TAMPER_DETECTED


@pytest.mark.asyncio
async def test_tamper_detection_on_broken_prev_hash() -> None:
    """Tampering with prev_event_hash must be caught as broken link."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

    async with session_factory() as session:
        chain_engine = AuditChainEngine()
        verifier = AuditChainVerifier(chain_engine=chain_engine)
        quote_id = "Q-TEST-BROKEN-001"

        await chain_engine.append_event(
            session, quote_id, "EV_1", "u1", {"step": 1}
        )
        ev2 = await chain_engine.append_event(
            session, quote_id, "EV_2", "u1", {"step": 2}
        )
        await session.commit()

        # Corrupt prev_event_hash of ev2
        await session.execute(
            update(QuoteAuditEventModel)
            .where(QuoteAuditEventModel.event_id == ev2.event_id)
            .values(prev_event_hash="0" * 64)
        )
        await session.commit()

        is_valid, msg = await verifier.verify_chain_integrity(session, quote_id)
        assert is_valid is False
        assert "BROKEN_LINK" in msg
