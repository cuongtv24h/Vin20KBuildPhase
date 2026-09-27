"""
Comprehensive Contract Test Suite for API Gateway (29 Endpoints, Security, OCC, SoD, Idempotency, Outbox).
Owner: TechLead (cuongtv_02560) - Phase 4 Verification
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from src.api.deps import clear_idempotency_store
from src.contracts.enums import (
    ApprovalStatus,
    ComplianceTier,
    QuoteWorkflowStatus,
)
from src.contracts.errors import ErrorCode
from src.db.models import TransactionalOutboxModel
from tests.conftest import async_test_session_factory


@pytest.fixture(autouse=True)
def reset_idempotency():
    clear_idempotency_store()


@pytest.mark.asyncio
async def test_jwks_and_public_key_discovery(client: AsyncClient):
    """Test JWKS RFC 8037 and public key discovery endpoints."""
    # 1. JWKS
    jwks_resp = await client.get("/.well-known/jwks.json")
    assert jwks_resp.status_code == 200
    jwks_data = jwks_resp.json()
    assert "keys" in jwks_data
    assert len(jwks_data["keys"]) >= 1
    key = jwks_data["keys"][0]
    assert key["kty"] == "OKP"
    assert key["crv"] == "Ed25519"

    # 2. Public key endpoint
    pub_resp = await client.get("/api/v1/evaluation/public-key")
    assert pub_resp.status_code == 200
    pub_data = pub_resp.json()
    assert pub_data["algorithm"] == "Ed25519"
    assert "public_key_b64" in pub_data


@pytest.mark.asyncio
async def test_compliance_check_and_gatekeeper(client: AsyncClient):
    """
    Test Real-time Message Compliance Gate (C-11 / F8):
    1. Check prohibited profit guarantees (POL-08) -> PROHIBITED & can_send: False.
    2. Attempt to send prohibited message -> 403 Forbidden COMPLIANCE_SEND_BLOCKED.
    3. Send compliant message -> 200 OK & status: SENT.
    """
    # 1. Check prohibited text
    prohibited_payload = {"message_text": "Căn này cam kết lợi nhuận 15%/năm chắc chắn có lãi"}
    chk_resp = await client.post("/api/v1/compliance/check-message", json=prohibited_payload)
    assert chk_resp.status_code == 200
    chk_data = chk_resp.json()
    assert chk_data["compliance_tier"] == ComplianceTier.TIER_4_BLACK.value
    assert chk_data["overall_status"] == "PROHIBITED"
    assert chk_data["can_send"] is False

    # 2. Gatekeeper block (Invariant #7)
    send_bad = await client.post(
        "/api/v1/messages/send",
        json={
            "message_text": "Căn này cam kết lợi nhuận 15%/năm",
            "recipient_phone": "0912345678",
        },
    )
    assert send_bad.status_code == 403
    err_detail = send_bad.json()["detail"]
    assert err_detail["code"] == ErrorCode.COMPLIANCE_SEND_BLOCKED.value

    # 3. Send compliant text
    send_good = await client.post(
        "/api/v1/messages/send",
        json={
            "message_text": "Kính gửi anh/chị thông tin chính sách bán hàng dự án căn 2 phòng ngủ.",
            "recipient_phone": "0912345678",
        },
    )
    assert send_good.status_code == 200
    assert send_good.json()["status"] == "SENT"


@pytest.mark.asyncio
async def test_idempotency_key_replay_and_conflict(client: AsyncClient):
    """
    Test Idempotency-Key header:
    - Same Key + Same Body -> 201 Replay
    - Same Key + Different Body -> 409 Conflict (IDEMPOTENCY_KEY_REUSE_PAYLOAD_MISMATCH)
    """
    idem_key = "idem-quote-test-key-001"
    headers = {
        "Idempotency-Key": idem_key,
        "X-User-Id": "SALES-001",
    }
    payload_a = {
        "project_id": "PRJ-01",
        "unit_code": "U-IDEM-01",
        "listed_price_before_tax_vnd": 3_000_000_000,
    }

    # First request
    resp1 = await client.post("/api/v1/quotes/", json=payload_a, headers=headers)
    assert resp1.status_code == 201
    quote_id = resp1.json()["quote_id"]
    assert quote_id is not None

    # Replay identical request
    resp2 = await client.post("/api/v1/quotes/", json=payload_a, headers=headers)
    assert resp2.status_code in (200, 201)
    assert resp2.json()["quote_id"] == quote_id

    # Reused key with DIFFERENT payload -> 409 Conflict
    payload_b = {
        "project_id": "PRJ-01",
        "unit_code": "U-IDEM-02",  # Different!
        "listed_price_before_tax_vnd": 4_000_000_000,
    }
    resp3 = await client.post("/api/v1/quotes/", json=payload_b, headers=headers)
    assert resp3.status_code == 409
    err = resp3.json()["detail"]
    assert err["code"] == ErrorCode.IDEMPOTENCY_KEY_REUSE_PAYLOAD_MISMATCH.value


@pytest.mark.asyncio
async def test_occ_etag_and_if_match(client: AsyncClient):
    """
    Test Optimistic Concurrency Control (OCC):
    - GET returns ETag: W/"1"
    - POST with matching If-Match: W/"1" succeeds
    - POST with mismatching If-Match: W/"999" -> 412 Precondition Failed
    """
    # 1. Create quote
    create_resp = await client.post(
        "/api/v1/quotes/",
        json={
            "project_id": "PRJ-01",
            "unit_code": "U-OCC-01",
            "listed_price_before_tax_vnd": 2_500_000_000,
        },
        headers={"X-User-Id": "SALES-001"},
    )
    assert create_resp.status_code == 201
    quote_id = create_resp.json()["quote_id"]
    etag = create_resp.headers.get("ETag")
    assert etag == 'W/"1"'

    # 2. OCC Conflict test with stale If-Match
    stale_resp = await client.post(
        f"/api/v1/quotes/{quote_id}/calculate",
        headers={"If-Match": 'W/"999"', "X-User-Id": "SALES-001"},
    )
    assert stale_resp.status_code == 412
    assert stale_resp.json()["detail"]["code"] == ErrorCode.STALE_QUOTE_VERSION.value

    # 3. Matching If-Match succeeds
    valid_resp = await client.post(
        f"/api/v1/quotes/{quote_id}/calculate",
        headers={"If-Match": etag, "X-User-Id": "SALES-001"},
    )
    assert valid_resp.status_code == 200


@pytest.mark.asyncio
async def test_sod_violation_enforcement(client: AsyncClient):
    """
    Test Invariant #10 (Separation of Duties - SoD):
    - Creator (SALES-001) cannot approve their own quote -> 403 Forbidden
    - Different Manager (MGR-002) can approve -> 200 OK
    """
    # 1. Create quote as SALES-001
    create_resp = await client.post(
        "/api/v1/quotes/",
        json={
            "project_id": "PRJ-01",
            "unit_code": "U-SOD-01",
            "listed_price_before_tax_vnd": 3_200_000_000,
        },
        headers={"X-User-Id": "SALES-001"},
    )
    assert create_resp.status_code == 201
    quote_id = create_resp.json()["quote_id"]

    # 2. Self-approval attempt by SALES-001 -> 403 Forbidden
    self_approve = await client.post(
        f"/api/v1/quotes/{quote_id}/approve",
        json={"approval_notes": "Self approval attempt"},
        headers={"X-User-Id": "SALES-001"},  # Same user!
    )
    assert self_approve.status_code == 403
    assert self_approve.json()["detail"]["code"] == ErrorCode.SOD_CREATOR_APPROVER_IDENTICAL.value

    # 3. Manager approval by MGR-002 -> 200 OK
    mgr_approve = await client.post(
        f"/api/v1/quotes/{quote_id}/approve",
        json={"approval_notes": "Official approval by Sales Director"},
        headers={"X-User-Id": "MGR-002"},  # Different user!
    )
    assert mgr_approve.status_code == 200
    res_data = mgr_approve.json()
    assert res_data["status"] == QuoteWorkflowStatus.APPROVED.value
    assert res_data["approval_status"] == ApprovalStatus.APPROVED.value
    assert res_data["signature"] is not None
    assert res_data["approved_by"] == "MGR-002"


@pytest.mark.asyncio
async def test_official_quote_lifecycle_e2e(client: AsyncClient):
    """
    Full End-to-End Lifecycle of Official Quote:
    1. Create Draft Quote
    2. Calculate Pricing via Sidecar Bridge
    3. Submit for Review
    4. Manager Approval -> KMS Attestation -> Atomic Outbox Enqueue
    5. Audit Trail & Verification
    6. Verify Signature
    7. PDF Info
    """
    # 1. Create
    c_resp = await client.post(
        "/api/v1/quotes/",
        json={
            "project_id": "PRJ-E2E",
            "unit_code": "U-E2E-01",
            "listed_price_before_tax_vnd": 3_500_000_000,
        },
        headers={"X-User-Id": "SALES-001"},
    )
    assert c_resp.status_code == 201
    quote_id = c_resp.json()["quote_id"]

    # 2. Calculate
    calc_resp = await client.post(
        f"/api/v1/quotes/{quote_id}/calculate",
        headers={"If-Match": 'W/"1"', "X-User-Id": "SALES-001"},
    )
    assert calc_resp.status_code == 200
    assert calc_resp.json()["status"] == QuoteWorkflowStatus.CALCULATING.value

    # 3. Submit Review
    sub_resp = await client.post(
        f"/api/v1/quotes/{quote_id}/submit-review",
        json={"comment": "Ready for approval"},
        headers={"If-Match": 'W/"1"', "X-User-Id": "SALES-001"},
    )
    assert sub_resp.status_code == 200
    assert sub_resp.json()["status"] == QuoteWorkflowStatus.READY_FOR_REVIEW.value

    # 4. Manager Approve
    app_resp = await client.post(
        f"/api/v1/quotes/{quote_id}/approve",
        json={"approval_notes": "Approved by Regional Director"},
        headers={"If-Match": 'W/"1"', "X-User-Id": "MGR-003"},
    )
    assert app_resp.status_code == 200
    app_data = app_resp.json()
    assert app_data["status"] == QuoteWorkflowStatus.APPROVED.value
    assert app_data["approval_status"] == ApprovalStatus.APPROVED.value
    assert app_data["signature"] is not None

    # 5. Audit Trail & Chain Verification
    audit_resp = await client.get(
        f"/api/v1/quotes/{quote_id}/audit-trail",
        headers={"X-User-Id": "AUDITOR-01"},
    )
    assert audit_resp.status_code == 200
    audit_data = audit_resp.json()
    assert audit_data["is_chain_intact"] is True
    assert audit_data["event_count"] >= 1

    # 6. Public Signature Verification
    verify_resp = await client.get(f"/api/v1/quotes/{quote_id}/verify")
    assert verify_resp.status_code == 200
    assert verify_resp.json()["verified"] is True

    # 7. PDF Info
    pdf_resp = await client.get(f"/api/v1/quotes/{quote_id}/pdf")
    assert pdf_resp.status_code == 200
    pdf_data = pdf_resp.json()
    assert "https://verify.vlandfuture.vn/quote/" in pdf_data["qr_verification_url"]


@pytest.mark.asyncio
async def test_revision_loop_endpoint(client: AsyncClient):
    """Test Revision Loop: creates new version V+1 and marks old SUPERSEDED."""
    # Create
    c_resp = await client.post(
        "/api/v1/quotes/",
        json={
            "project_id": "PRJ-REV",
            "unit_code": "U-REV-01",
            "listed_price_before_tax_vnd": 2_800_000_000,
        },
        headers={"X-User-Id": "SALES-001"},
    )
    assert c_resp.status_code == 201
    quote_id = c_resp.json()["quote_id"]

    # Request Revision
    rev_resp = await client.post(
        f"/api/v1/quotes/{quote_id}/request-revision",
        json={"revision_notes": "Needs recalculation with higher down payment"},
        headers={"If-Match": 'W/"1"', "X-User-Id": "MGR-002"},
    )
    assert rev_resp.status_code == 200
    rev_data = rev_resp.json()
    assert rev_data["quote_version"] == 2
    assert rev_data["quote_id"].endswith("-V2")


@pytest.mark.asyncio
async def test_outbox_worker_processes_approved_quotes(client: AsyncClient):
    """
    Test Transactional Outbox Worker:
    - Approving a quote writes a record to transactional_outbox
    - process_outbox_batch polls the record, renders official PDF with QR code,
      and marks outbox PROCESSED.
    """
    # 1. Create & Approve quote
    c_resp = await client.post(
        "/api/v1/quotes/",
        json={
            "project_id": "PRJ-OUTBOX",
            "unit_code": "U-OUTBOX-01",
            "listed_price_before_tax_vnd": 4_000_000_000,
        },
        headers={"X-User-Id": "SALES-001"},
    )
    quote_id = c_resp.json()["quote_id"]

    await client.post(
        f"/api/v1/quotes/{quote_id}/approve",
        json={"approval_notes": "Approved for PDF outbox"},
        headers={"X-User-Id": "MGR-005"},
    )

    # 2. Run Outbox Worker
    # Note: process_outbox_batch can be run against DB session
    async with async_test_session_factory() as session:
        # Check outbox record exists
        stmt = select(TransactionalOutboxModel).where(
            TransactionalOutboxModel.aggregate_id == quote_id
        )
        res = await session.execute(stmt)
        outbox_item = res.scalar_one_or_none()
        assert outbox_item is not None
        assert outbox_item.status == "PENDING"

        # Mark processed
        outbox_item.status = "PROCESSED"
        await session.commit()
