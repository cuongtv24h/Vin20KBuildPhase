"""
Unit & Integration Tests for SnapshotFreezer (C-02)
Owner: TechLead (cuongtv_02560)
"""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.contracts.errors import DomainError, ErrorCode
from src.db.models import Base
from src.services.snapshot.freezer import SnapshotFreezer


@pytest.mark.asyncio
async def test_snapshot_freezer_lifecycle_and_tamper_detection() -> None:
    """Test freeze snapshot, retrieve snapshot, immutability check, and tamper detection."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

    async with session_factory() as session:
        freezer = SnapshotFreezer()

        quote_id = "Q-SNAP-001"
        version = 1

        # 1. Freeze snapshot
        snap = await freezer.freeze_snapshot(
            db_session=session,
            quote_id=quote_id,
            version=version,
            unit_code="U-501",
            project_id="P-01",
            policy_rules=[{"rule_id": "R1", "discount": 0.05}],
            calculation_result={"net_price": 4_500_000_000},
            metadata={"source": "test"},
        )
        await session.commit()

        assert snap.quote_id == quote_id
        assert snap.quote_version == version
        assert len(snap.snapshot_hash) == 64

        # 2. Immutability: Attempting to freeze again for same quote_id and version must raise error
        with pytest.raises(DomainError) as exc_info:
            await freezer.freeze_snapshot(
                db_session=session,
                quote_id=quote_id,
                version=version,
                unit_code="U-501",
                project_id="P-01",
                policy_rules=[],
                calculation_result={},
            )
        assert exc_info.value.code == ErrorCode.IMMUTABLE_SNAPSHOT_VIOLATION

        # 3. Retrieve and verify snapshot
        verified_snap = await freezer.get_and_verify_snapshot(session, quote_id, version)
        assert verified_snap.snapshot_hash == snap.snapshot_hash
        assert verified_snap.payload_json["unit_code"] == "U-501"

        # 4. Tamper detection: modify payload_json in place
        verified_snap.payload_json["calculation_result"]["net_price"] = 1_000_000_000
        await session.commit()

        with pytest.raises(DomainError) as exc_info:
            await freezer.get_and_verify_snapshot(session, quote_id, version)
        assert exc_info.value.code == ErrorCode.TAMPER_DETECTED
