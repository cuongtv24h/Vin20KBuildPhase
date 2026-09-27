"""
Phase 5 — E2E Full-Funnel Integration Test (5 chặng).
Owner: Phase 5 — mydoc/Excute.md TASK-P5-01.

Luồng: Pre-Sales chat (C-09) → Lead Dossier (C-10) → Official Quote (C-01,
23 nodes, revision loop, KMS attestation) → F8 Compliance Send Gate (C-11).

Chạy 100% offline: SQLite in-memory + MemorySaver + PricingClient fallback
Decimal 28. Không cần OpenAI key, không cần Postgres, không cần sidecar.
"""

from __future__ import annotations

import pytest
from langgraph.checkpoint.memory import MemorySaver
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.agents.official_quote.graph import build_official_quote_graph
from src.agents.official_quote.state import OfficialQuoteState
from src.agents.pre_sales.graph import PreSalesSessionRunner
from src.contracts.enums import ApprovalStatus, QuoteWorkflowStatus
from src.contracts.errors import DomainError
from src.db.models import Base
from src.services.approval import KMSServerSigner
from src.services.compliance.gate import ComplianceGateService
from src.services.dossier.service import PreSalesDossierService

# ---------------------------------------------------------------------------
# Fixtures & helpers
# ---------------------------------------------------------------------------

VALID_CONSENT = {
    "consent_granted": True,
    "customer_name": "Nguyen Van A",
    "customer_phone": "0912345678",
    "customer_email": None,
    "privacy_terms_acknowledged": True,
}


@pytest.fixture()
def quote_graph():
    """Official Quote graph có interrupt tại await_manager_approval."""
    return build_official_quote_graph(checkpointer=MemorySaver(), interrupt_on_review=True)


def _make_db_factory():
    """Tạo (factory, engine) SQLite in-memory với schema 14 bảng."""

    async def _make():
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
        return factory, engine

    return _make


def base_quote_input(quote_id: str = "Q-E2E-001") -> OfficialQuoteState:
    return {
        "quote_id": quote_id,
        "quote_version": 1,
        "tenant_id": "vland",
        "project_id": "BEVERLY",
        "unit_code": "BEV-12.04",
        "transaction_date": "2026-09-26",
        "listed_price_before_tax_vnd": 3_000_000_000,
        "own_funds_vnd": 1_500_000_000,
        "monthly_capacity_vnd": 40_000_000,
        "objective": "MIN_INITIAL_CASH",
        "creator_id": "SALES-001",
        "manager_id": "MGR-002",
    }


def quote_config(quote_id: str) -> dict:
    return {
        "configurable": {
            "thread_id": f"quote:vland:{quote_id}",
            "checkpoint_ns": "DEFAULT",
        }
    }


# ---------------------------------------------------------------------------
# CHẶNG 1-2: Pre-Sales chat → Lead Dossier (C-09 → C-10)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_leg_1_2_presales_to_dossier():
    """Chặng 1-2: Chat Pre-Sales 3 interrupts → handoff tạo LeadDossier SLA 15m."""
    runner = PreSalesSessionRunner()
    tenant, session = "vland", "e2e-ps-001"

    state = await runner.start_session(tenant, session, initial_message=None)
    assert state["_interrupt_gate"] == "WAITING_FOR_CUSTOMER_INPUT"

    state = await runner.submit_message(
        tenant, session, "Tôi quan tâm 2BR, vốn tự có 1.5 tỷ, trả góp 40 triệu/tháng"
    )
    assert state["_interrupt_gate"] == "WAITING_FOR_CONSTRAINT_CONFIRMATION"

    state = await runner.confirm_constraints(tenant, session, {"confirmed": True})
    assert state["status"] == "PLAN_READY"
    assert state["plan_id"] and state["plan_id"].startswith("PLAN-")
    assert state["watermark_text"].startswith("BẢN ƯỚC TÍNH THAM KHẢO")

    state = await runner.provide_consent(tenant, session, dict(VALID_CONSENT))
    assert state["decision"] == "HANDOFF_CREATE_DOSSIER"

    # Persist LeadDossier theo đúng flow của endpoint consent:
    # tạo session row trước (runner chạy trên MemorySaver, không persist DB)
    make_db = _make_db_factory()
    factory, engine = await make_db()
    async with factory() as db:
        service = PreSalesDossierService()
        await service.create_session(db, tenant_id=tenant, initial_message="Tôi quan tâm 2BR")
        # đồng bộ session_id với thread LangGraph
        from sqlalchemy import update

        from src.db.models import PreSalesSessionModel

        row = (
            await db.execute(select(PreSalesSessionModel).limit(1))
        ).scalars().first()
        await db.execute(
            update(PreSalesSessionModel)
            .where(PreSalesSessionModel.session_id == row.session_id)
            .values(session_id=session)
        )
        await db.flush()

        await service.record_consent(
            db,
            session_id=session,
            customer_name=VALID_CONSENT["customer_name"],
            customer_phone=VALID_CONSENT["customer_phone"],
        )
        dossier = await service.create_dossier(
            db,
            session_id=session,
            customer_name=VALID_CONSENT["customer_name"],
            customer_phone=VALID_CONSENT["customer_phone"],
            constraints=state.get("customer_constraints"),
            plan_id=state.get("plan_id"),
        )
        await db.commit()
        assert dossier.status == "NEW"
        sla_seconds = (dossier.sla_expires_at - dossier.created_at).total_seconds()
        assert abs(sla_seconds - 900) < 5, "SLA 15 phút"

    await engine.dispose()


# ---------------------------------------------------------------------------
# CHẶNG 3: Official Quote graph 23 nodes → READY_FOR_REVIEW (C-01)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_leg_3_official_quote_to_ready_for_review(quote_graph):
    """Chặng 3: chạy 23 nodes → dừng HITL ở N-16 READY_FOR_REVIEW."""
    config = quote_config("Q-E2E-001")
    result = await quote_graph.ainvoke(base_quote_input(), config=config)
    assert result["workflow_status"] == QuoteWorkflowStatus.READY_FOR_REVIEW
    assert result["approval_package"]["quote_id"] == "Q-E2E-001"
    assert result["pricing_result"]["sanity_passed"] is True


# ---------------------------------------------------------------------------
# CHẶNG 4: Manager approval → KMS attestation → commit (C-05)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_leg_4_kms_attestation_and_commit(quote_graph):
    """Chặng 4: manager APPROVE → N-19A/B → N-20 commit APPROVED, signature verify ok."""
    config = quote_config("Q-E2E-001")
    await quote_graph.ainvoke(
        base_quote_input() | {"manager_decision": "APPROVE"}, config=config
    )

    result = await quote_graph.ainvoke(None, config=config)
    assert result["workflow_status"] == QuoteWorkflowStatus.APPROVED
    assert result["approval_status"] == ApprovalStatus.APPROVED
    assert result["committed"] is True

    # Verify chữ ký Ed25519 bằng public key trả về trong state
    signer = KMSServerSigner()
    is_valid = signer.verify_signature(
        result["frozen_snapshot_hash"],
        result["server_attestation_signature"],
        public_key_base64=result["public_key_b64"],
    )
    assert is_valid is True, "Chữ ký Ed25519 phải verify thành công bằng public key state"


@pytest.mark.asyncio
async def test_leg_4b_revision_loop_bumps_version(quote_graph):
    """Chặng 4b: REQUEST_REVISION → quote_version +1 → quay lại N-09 tính lại."""
    config = quote_config("Q-REV-001")
    await quote_graph.ainvoke(
        base_quote_input(quote_id="Q-REV-001") | {"manager_decision": "REQUEST_REVISION"},
        config=config,
    )

    result = await quote_graph.ainvoke(None, config=config)
    assert result["quote_version"] == 2, "Revision loop phải tăng version"
    assert result["revision_count"] == 1
    # Sau khi tính lại, workflow quay lại điểm ngắt N-16 chờ duyệt lần 2
    assert result["workflow_status"] == QuoteWorkflowStatus.READY_FOR_REVIEW
    assert result["pricing_result"]["sanity_passed"] is True


# ---------------------------------------------------------------------------
# CHẶNG 5: F8 Compliance Send Gate (C-11)
# ---------------------------------------------------------------------------

GOOD_MESSAGE = "Căn này giá 5 tỷ, chiết khấu 8% theo [POL-BEVERLY-STANDARD-2026]"
BAD_MESSAGE = "Cam kết sinh lời 20% mỗi năm cho anh!"


@pytest.mark.asyncio
async def test_leg_5_f8_gate_allows_compliant_and_blocks_violation():
    """Chặng 5: tin nhắn có dẫn chứng gửi được; cam kết sinh lời bị chặn 403."""
    make_db = _make_db_factory()
    factory, engine = await make_db()
    async with factory() as db:
        gate = ComplianceGateService()

        # GREEN: claim có dẫn chứng điều khoản
        ok = await gate.check_message(db, GOOD_MESSAGE, quote_id="Q-E2E-001")
        assert ok.compliance_tier == "TIER_1_GREEN" and ok.can_send is True
        result = await gate.enforce_send(
            db, ok.message_hash, GOOD_MESSAGE, recipient_phone="0912345678"
        )
        assert result["sent"] is True

        # BLACK: cam kết sinh lời → chặn 403
        blocked = await gate.check_message(db, BAD_MESSAGE, quote_id="Q-E2E-001")
        assert blocked.compliance_tier == "TIER_4_BLACK" and blocked.can_send is False
        with pytest.raises(DomainError) as exc_info:
            await gate.enforce_send(
                db, blocked.message_hash, BAD_MESSAGE, recipient_phone="0912345678"
            )
        assert exc_info.value.error_code == "COMPLIANCE_SEND_BLOCKED"
        assert exc_info.value.http_status == 403

    await engine.dispose()


# ---------------------------------------------------------------------------
# SoD (Invariant #10) trên đường attestation
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_sod_blocks_creator_self_approval(quote_graph):
    """Invariant #10: creator tự phê duyệt → BLOCKED, không commit, không chữ ký."""
    config = quote_config("Q-SOD-001")
    await quote_graph.ainvoke(
        base_quote_input(quote_id="Q-SOD-001")
        | {"manager_decision": "APPROVE", "manager_id": "SALES-001", "creator_id": "SALES-001"},
        config=config,
    )
    result = await quote_graph.ainvoke(None, config=config)
    assert result["workflow_status"] == QuoteWorkflowStatus.BLOCKED
    assert result["is_blocked"] is True
    assert result.get("committed") is not True
