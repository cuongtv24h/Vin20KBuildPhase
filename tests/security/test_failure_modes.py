"""
Phase 5 — Failure Injection Test Suite (FAIL-01 → FAIL-05).
Owner: Phase 5 — mydoc/Excute.md TASK-P5-02.

5 kịch bản lỗi biên bắt buộc vượt qua:
- FAIL-01: Pricing Sidecar crash giữa lúc tính → CALCULATION_FAILED, không sập.
- FAIL-02: DB crash sau khi KMS ký → Atomic Commit-Discard, không chữ ký mồ côi.
- FAIL-03: Chính sách hết hạn mid-flight → ABSTAINED + cảnh báo.
- FAIL-04: Race 2 manager trên 1 version → OCC từ chối (VERSION_CONFLICT → 412 ở tầng API).
- FAIL-05: Bypass F8 gửi tin trực tiếp → COMPLIANCE_SEND_BLOCKED (403).

Chạy 100% offline (SQLite + MemorySaver + PricingClient fallback).
"""

from __future__ import annotations

import pytest
from langgraph.checkpoint.memory import MemorySaver
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.agents.official_quote.graph import build_official_quote_graph
from src.agents.official_quote.state import OfficialQuoteState
from src.contracts.enums import QuoteWorkflowStatus
from src.contracts.errors import DomainError, ErrorCode
from src.db.models import Base, QuoteModel, TransactionalOutboxModel
from src.services.approval.review import QuoteApprovalService
from src.services.compliance.gate import ComplianceGateService


def base_quote_input(quote_id: str = "Q-FAIL-001") -> OfficialQuoteState:
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
        "manager_decision": "APPROVE",
    }


def quote_config(quote_id: str) -> dict:
    return {
        "configurable": {
            "thread_id": f"quote:vland:{quote_id}",
            "checkpoint_ns": "DEFAULT",
        }
    }


# ---------------------------------------------------------------------------
# FAIL-01: Pricing Sidecar Crash giữa lúc tính
# ---------------------------------------------------------------------------

class _CrashedSidecarClient:
    """Mô phỏng sidecar chết: trả kết quả hỏng (sanity fail) hoặc raise timeout."""

    def __init__(self, mode: str = "garbage") -> None:
        self.mode = mode

    async def calculate(self, pricing_input):  # noqa: ANN001
        if self.mode == "raise":
            from src.services.pricing.client import PricingCalculationError

            raise PricingCalculationError("Sidecar timeout after 3s (simulated crash)")
        from src.contracts.pricing import ScenarioCode, ScenarioDetail

        # Kết quả hỏng: total contract price lệch khỏi Net+VAT+KPBT (Check 2 fail)
        detail = ScenarioDetail(
            scenario_code=ScenarioCode.PA_CHUDONG,
            scenario_name="Corrupted",
            net_price_vnd=3_000_000_000,
            vat_vnd=300_000_000,
            kpbt_vnd=60_000_000,
            total_contract_price_vnd=3_500_000_000,  # lệch 140.000.000 VNĐ
            initial_cash_outflow_vnd=500_000_000,
            monthly_burden_vnd=100_000_000,
            total_cash_outflow_vnd=3_500_000_000,
            benefit_value_vnd=0,
            payment_schedule=[],
            is_feasible=True,
        )
        from src.contracts.pricing import PricingResult

        return PricingResult(
            calculation_hash="0" * 64,
            scenarios={ScenarioCode.PA_CHUDONG.value: detail},
            recommended_scenario_code=ScenarioCode.PA_CHUDONG,
            sanity_passed=True,  # sidecar chết nói dối: tự claiming pass
            sanity_errors=[],
        )


@pytest.mark.asyncio
async def test_fail_01_sidecar_garbage_results_lead_to_calculation_failed(monkeypatch):
    """Sidecar trả dữ liệu hỏng → N-11 bắt được → CALCULATION_FAILED, graph kết thúc an toàn."""
    import src.agents.official_quote.nodes.pricing as pricing_nodes

    monkeypatch.setattr(
        pricing_nodes, "PricingClient", lambda **kwargs: _CrashedSidecarClient("garbage")
    )
    graph = build_official_quote_graph(checkpointer=MemorySaver(), interrupt_on_review=False)
    result = await graph.ainvoke(base_quote_input("Q-FAIL-01A"), config=quote_config("Q-FAIL-01A"))

    assert result["sanity_passed"] is False
    assert result["sanity_errors"], "N-11 phải bắt được dữ liệu hỏng"
    assert result["workflow_status"] == QuoteWorkflowStatus.CALCULATION_FAILED
    # Không được commit APPROVED khi sanity fail
    assert result.get("committed") is not True


@pytest.mark.asyncio
async def test_fail_01b_sidecar_hard_crash_raises_structured_error(monkeypatch):
    """Sidecar chết hoàn toàn → exception có cấu trúc (DomainError), bắt được ở tầng API."""
    import src.agents.official_quote.nodes.pricing as pricing_nodes

    monkeypatch.setattr(
        pricing_nodes, "PricingClient", lambda **kwargs: _CrashedSidecarClient("raise")
    )
    graph = build_official_quote_graph(checkpointer=MemorySaver(), interrupt_on_review=False)
    with pytest.raises(DomainError) as exc_info:
        await graph.ainvoke(base_quote_input("Q-FAIL-01B"), config=quote_config("Q-FAIL-01B"))
    assert exc_info.value.error_code == ErrorCode.CALCULATION_ENGINE_ERROR


# ---------------------------------------------------------------------------
# FAIL-02: DB Crash sau khi KMS ký → Atomic Commit-Discard
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_fail_02_db_crash_after_kms_sign_discards_orphan_signature():
    """
    DB rollback sau khi chữ ký sinh trong RAM → không persist signature,
    không sinh outbox event (không chữ ký mồ côi).
    """
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

    async with factory() as db:
        quote = QuoteModel(
            quote_id="Q-FAIL-02",
            unit_code="U-101",
            status="READY_FOR_REVIEW",
            approval_status="PENDING",
            created_by="SALES-001",
        )
        db.add(quote)
        await db.commit()

        service = QuoteApprovalService()
        snapshot = {"quote_id": "Q-FAIL-02", "final_price": 4_800_000_000}

        # Mô phỏng DB crash: audit chain (cùng transaction) nổ lỗi khi ghi
        async def _db_crash(*args, **kwargs):  # noqa: ANN002, ANN003
            raise ConnectionError("Simulated DB disconnect right after KMS sign")

        service.audit_chain.append_event = _db_crash

        with pytest.raises(ConnectionError):
            await service.execute_atomic_approval(
                db_session=db,
                quote_id="Q-FAIL-02",
                approver_id="MGR-002",
                snapshot_data=snapshot,
            )

        # Mô phỏng teardown của phiên crash trong thực tế: rollback tường minh.
        # Không có dòng này, dữ liệu uncommitted (APPROVED chưa rollback) vẫn nằm
        # trên shared in-memory connection (aiosqlite StaticPool) và phiên đọc dưới
        # đôi khi thấy trạng thái bẩn → test flaky (audit TASK-REVIEW-02).
        await db.rollback()

        # ROLLBACK: phiên hỏng → mở phiên mới kiểm tra sạch sẽ
        db2 = factory()
        async with db2:
            fresh_quote = await db2.get(QuoteModel, "Q-FAIL-02")
            assert fresh_quote.approval_status == "PENDING", "Không được APPROVED sau rollback"
            assert fresh_quote.signature is None, "Không được sinh chữ ký mồ côi"
            assert fresh_quote.snapshot_hash is None

            from sqlalchemy import select

            outbox_count = len(
                (await db2.execute(select(TransactionalOutboxModel))).scalars().all()
            )
            assert outbox_count == 0, "Không được ghi outbox event khi transaction fail"

    await engine.dispose()


# ---------------------------------------------------------------------------
# FAIL-03: Chính sách hết hạn mid-flight → ABSTAINED
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_fail_03_policy_expired_midflight_abstains(monkeypatch):
    """N-05 phát hiện không còn chính sách hiệu lực → ABSTAINED, không tính toán."""
    import src.agents.official_quote.graph as graph_module

    def _empty_retrieve(state):  # noqa: ANN001
        return {
            "retrieved_policy_ids": [],
            "policy_snapshot_id": None,
            "policy_snapshot_hash": None,
        }

    monkeypatch.setattr(graph_module, "retrieve_active_policies", _empty_retrieve)
    graph = graph_module.build_official_quote_graph(
        checkpointer=MemorySaver(), interrupt_on_review=False
    )
    result = await graph.ainvoke(base_quote_input("Q-FAIL-03"), config=quote_config("Q-FAIL-03"))

    assert result["is_abstained"] is True
    assert result["workflow_status"] == QuoteWorkflowStatus.ABSTAINED
    assert result["abstention_reason"]
    assert result.get("committed") is not True, "ABSTAINED thì tuyệt đối không commit"
    assert result.get("pricing_result") is None, "ABSTAINED thì không được tính giá"


@pytest.mark.asyncio
async def test_fail_03b_guardrail_node_unit():
    """Unit: N-05 với danh sách chính sách rỗng → abstain."""
    from src.agents.official_quote.nodes.policy_retrieval import security_guardrail_policy

    result = security_guardrail_policy({"retrieved_policy_ids": []})
    assert result["is_abstained"] is True
    assert result["abstention_reason"]


# ---------------------------------------------------------------------------
# FAIL-04: Concurrency race — 2 manager trên 1 version (OCC)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_fail_04_stale_version_conflict_on_concurrent_approval():
    """Manager B dùng expected_version cũ sau khi version đã đổi → VERSION_CONFLICT (412)."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

    async with factory() as db:
        quote = QuoteModel(
            quote_id="Q-FAIL-04",
            unit_code="U-101",
            status="READY_FOR_REVIEW",
            approval_status="PENDING",
            quote_version=1,
            created_by="SALES-001",
        )
        db.add(quote)
        await db.commit()

        service = QuoteApprovalService()
        snapshot = {"quote_id": "Q-FAIL-04", "final_price": 4_800_000_000}

        # Manager A thắng race với version 1
        await service.execute_atomic_approval(
            db_session=db,
            quote_id="Q-FAIL-04",
            approver_id="MGR-002",
            snapshot_data=snapshot,
            expected_version=1,
        )
        await db.commit()

        # Giả lập quote đã được bump version (sửa đổi/điều chỉnh) sau khi A duyệt
        fresh = await db.get(QuoteModel, "Q-FAIL-04")
        fresh.quote_version = 2
        await db.commit()

        # Manager B vẫn cầm ETag/version 1 cũ → OCC từ chối
        with pytest.raises(DomainError) as exc_info:
            await service.execute_atomic_approval(
                db_session=db,
                quote_id="Q-FAIL-04",
                approver_id="MGR-003",
                snapshot_data=snapshot,
                expected_version=1,
            )
        assert exc_info.value.error_code == ErrorCode.VERSION_CONFLICT

    await engine.dispose()


# ---------------------------------------------------------------------------
# FAIL-05: F8 Send Gate Bypass
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_fail_05_f8_gate_blocks_all_bypass_paths():
    """Gửi trực tiếp không thẩm định / sai hash / nội dung cấm → đều 403 BLOCKED."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

    async with factory() as db:
        gate = ComplianceGateService()

        # (a) Bypass hoàn toàn: gửi tin chưa từng qua thẩm định
        with pytest.raises(DomainError) as exc_a:
            await gate.enforce_send(
                db, message_hash="a" * 64, message_text="Báo giá 3 tỷ ạ",
                recipient_phone="0912345678",
            )
        assert exc_a.value.error_code == ErrorCode.COMPLIANCE_SEND_BLOCKED
        assert exc_a.value.http_status == 403

        # (b) Anti-tamper: hash khớp record nhưng nội dung gửi bị sửa
        ok = await gate.check_message(
            db, "Giá căn này 3 tỷ theo [POL-BEVERLY-STANDARD-2026]", quote_id="Q-FAIL-05"
        )
        with pytest.raises(DomainError) as exc_b:
            await gate.enforce_send(
                db, ok.message_hash, "Giá căn này 2 tỷ (đã sửa lén)!",
                recipient_phone="0912345678",
            )
        assert exc_b.value.error_code == ErrorCode.COMPLIANCE_SEND_BLOCKED
        assert exc_b.value.http_status == 403

        # (c) Nội dung cấm (cam kết sinh lời) dù có qua thẩm định
        bad = await gate.check_message(db, "Cam kết sinh lời 50% mỗi năm!", quote_id="Q-FAIL-05")
        with pytest.raises(DomainError) as exc_c:
            await gate.enforce_send(
                db, bad.message_hash, "Cam kết sinh lời 50% mỗi năm!",
                recipient_phone="0912345678",
            )
        assert exc_c.value.error_code == ErrorCode.COMPLIANCE_SEND_BLOCKED
        assert exc_c.value.http_status == 403

        # (d) Mượn hash chéo: tin thẩm định cho Q-FAIL-05 nhưng gửi cho Q-OTHER
        with pytest.raises(DomainError) as exc_d:
            await gate.enforce_send(
                db, ok.message_hash, "Giá căn này 3 tỷ theo [POL-BEVERLY-STANDARD-2026]",
                recipient_phone="0912345678", quote_id="Q-OTHER",
            )
        assert exc_d.value.error_code == ErrorCode.COMPLIANCE_SEND_BLOCKED
        assert exc_d.value.http_status == 403

    await engine.dispose()
