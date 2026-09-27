"""
Unit & Integration Tests for Spike 3: KMS Server Attestation & Atomic Approval
Owner: TechLead (cuongtv_02560)
"""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.contracts.enums import ApprovalStatus, QuoteWorkflowStatus
from src.contracts.errors import DomainError, ErrorCode
from src.db.models import Base, QuoteModel, TransactionalOutboxModel
from src.services.approval.review import QuoteApprovalService
from src.services.approval.signing import KMSServerSigner
from src.services.audit.chain import AuditChainEngine


def test_kms_signer_key_generation_and_verification() -> None:
    """Test Ed25519 signer generates valid key, signs deterministic hash, and verifies."""
    signer = KMSServerSigner()
    pub_b64 = signer.get_public_key_base64()
    assert len(pub_b64) > 0

    snapshot_data = {
        "quote_id": "Q-2026-001",
        "net_price": 5_200_000_000,
        "payment_schedule": [{"installment": 1, "amount": 1_000_000_000}],
    }

    hash1 = signer.calculate_snapshot_hash(snapshot_data)
    # Permuting keys must yield exact same hash (canonical JSON RFC 8785)
    permuted_data = {
        "payment_schedule": [{"installment": 1, "amount": 1_000_000_000}],
        "quote_id": "Q-2026-001",
        "net_price": 5_200_000_000,
    }
    hash2 = signer.calculate_snapshot_hash(permuted_data)
    assert hash1 == hash2

    sig_b64 = signer.sign_snapshot_hash(hash1)
    assert len(sig_b64) > 0

    # Self-verify
    assert signer.verify_signature(hash1, sig_b64) is True

    # Verify using exported public key
    assert signer.verify_signature(hash1, sig_b64, public_key_base64=pub_b64) is True

    # Verify with modified hash must fail
    fake_hash = "f" * 64
    assert signer.verify_signature(fake_hash, sig_b64) is False


def test_sod_violation_enforcement() -> None:
    """Separation of Duties: creator cannot approve their own quote."""
    with pytest.raises(DomainError) as exc_info:
        QuoteApprovalService.validate_separation_of_duties("sales_01", "sales_01")
    assert exc_info.value.code == ErrorCode.SOD_VIOLATION


@pytest.mark.asyncio
async def test_atomic_approval_lifecycle() -> None:
    """
    Test atomic approval:
    1. Quote updated with APPROVED status, signature, snapshot_hash
    2. Audit event added to chain
    3. Transactional outbox event created
    """
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

    async with session_factory() as session:
        # Create quote
        quote = QuoteModel(
            quote_id="Q-TEST-001",
            unit_code="U-101",
            created_by="sales_alice",
            status=QuoteWorkflowStatus.READY_FOR_REVIEW.value,
            approval_status=ApprovalStatus.PENDING.value,
            quote_version=1,
            total_contract_price_vnd=4_800_000_000,
        )
        session.add(quote)
        await session.commit()

        # Service
        signer = KMSServerSigner()
        chain = AuditChainEngine()
        service = QuoteApprovalService(kms_signer=signer, audit_chain=chain)

        snapshot_data = {
            "quote_id": "Q-TEST-001",
            "unit_code": "U-101",
            "final_price": 4_800_000_000,
        }

        # 1. SoD check: sales_alice cannot approve
        with pytest.raises(DomainError) as exc_info:
            await service.execute_atomic_approval(
                db_session=session,
                quote_id="Q-TEST-001",
                approver_id="sales_alice",
                snapshot_data=snapshot_data,
            )
        assert exc_info.value.code == ErrorCode.SOD_VIOLATION

        # 2. Manager Bob approves
        result = await service.execute_atomic_approval(
            db_session=session,
            quote_id="Q-TEST-001",
            approver_id="manager_bob",
            snapshot_data=snapshot_data,
            expected_version=1,
        )
        await session.commit()

        assert result["status"] == ApprovalStatus.APPROVED
        assert result["approved_by"] == "manager_bob"
        assert len(result["signature"]) > 0

        # Verify quote persisted in DB
        db_quote = await session.get(QuoteModel, "Q-TEST-001")
        assert db_quote is not None
        assert db_quote.approval_status == ApprovalStatus.APPROVED.value
        assert db_quote.status == QuoteWorkflowStatus.APPROVED.value
        assert db_quote.signature == result["signature"]
        assert db_quote.snapshot_hash == result["snapshot_hash"]

        # Verify signature validity
        assert signer.verify_signature(db_quote.snapshot_hash, db_quote.signature) is True

        # Verify Outbox event
        outbox_items = (await session.execute(TransactionalOutboxModel.__table__.select())).all()
        assert len(outbox_items) == 1
        assert outbox_items[0].aggregate_id == "Q-TEST-001"
        assert outbox_items[0].event_type == "OFFICIAL_QUOTE_ISSUED"
        assert outbox_items[0].status == "PENDING"
