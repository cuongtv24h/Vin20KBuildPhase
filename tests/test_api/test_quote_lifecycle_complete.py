"""Luồng hoàn chỉnh: Sale lập báo giá → **bản chờ duyệt gửi Manager**.

Bốn điểm gãy của luồng cũ được khoá lại bằng test ở đây:
1. `/calculate` không được làm mất ĐẦU VÀO trong snapshot (màn duyệt cần vốn tự có/dự án/giá niêm
   yết, không chỉ `scenarios`).
2. `/calculate` phát hành **bộ chứng cứ cấp-luận-điểm**; `GET /evidence` trả claim thật có toạ độ nguồn.
3. `/submit-review` **chặn bản khuyết** bằng 409 kèm `checklist`, chỉ cho qua khi đủ 3 điều kiện
   (đã tính + có bằng chứng + qua cổng F8).
4. Submit ghi **audit hash-chain + outbox trong cùng giao dịch** và tra lại được qua `/audit`.
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from src.db.models import TransactionalOutboxModel
from tests.conftest import async_test_session_factory

SALE_HEADERS = {"X-User-Id": "SALES-001"}
BACKEND_CREATE_PAYLOAD = {
    "project_id": "THE_ZEN_PARK",
    "unit_code": "ZEN-A-1205",
    "listed_price_before_tax_vnd": 4_200_000_000,
    "own_funds_vnd": 1_500_000_000,
    "monthly_capacity_vnd": 40_000_000,
    "objective": "MIN_INITIAL_CASH",
}
#: Ngày nằm trong hiệu lực của CSBH-ZEN-2026-V3.1 (2026-08-01 → 2026-12-31).
TX_DATE = "2026-09-15"


async def _create_quote(client: AsyncClient, unit_code: str = "ZEN-A-1205") -> str:
    resp = await client.post(
        "/api/v1/quotes",
        json={**BACKEND_CREATE_PAYLOAD, "unit_code": unit_code},
        headers=SALE_HEADERS,
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["quote_id"]


async def _calculate(client: AsyncClient, quote_id: str) -> dict:
    resp = await client.post(
        f"/api/v1/quotes/{quote_id}/calculate",
        params={"transaction_date": TX_DATE},
        headers=SALE_HEADERS,
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


@pytest.mark.asyncio
async def test_full_lifecycle_sale_to_pending_manager_approval(client: AsyncClient):
    """Đường hạnh phúc: tạo → tính → bằng chứng → trình duyệt → Manager thấy PENDING."""
    quote_id = await _create_quote(client)

    # 1) Tính phương án: snapshot phải giữ ĐẦU VÀO + có 3 phương án + phát hành bằng chứng.
    calc = await _calculate(client, quote_id)
    snapshot = calc["snapshot_payload"]
    assert snapshot["project_id"] == "THE_ZEN_PARK"
    assert snapshot["transaction_date"] == TX_DATE
    assert snapshot["own_funds_vnd"] == 1_500_000_000
    assert snapshot["listed_price_before_tax_vnd"] == 4_200_000_000
    assert len(snapshot["scenarios"]) == 3
    assert snapshot["recommended_scenario_code"]
    assert calc["evidence"]["decision_status"] in {"VERIFIED", "CONDITIONAL"}
    assert calc["evidence"]["applied_rule_count"] >= 1

    # 2) Màn duyệt đọc bằng chứng: claim thật, có toạ độ điều khoản.
    evidence = await client.get(f"/api/v1/quotes/{quote_id}/evidence", headers=SALE_HEADERS)
    assert evidence.status_code == 200
    body = evidence.json()
    assert body["quote_id"] == quote_id
    assert body["decision_status"] in {"VERIFIED", "CONDITIONAL"}
    assert body["claims"], "bộ chứng cứ phải có ít nhất một luận điểm"
    assert body["policy_id"] == "CSBH-ZEN-2026-V3.1"
    # Claim điều khoản (POL-*) là lớp bằng chứng pháp lý: BẮT BUỘC có toạ độ nguồn.
    entitlement_claims = [c for c in body["claims"] if c["claim_id"].startswith("POL-")]
    assert entitlement_claims and all(c["source_coordinates"] for c in entitlement_claims)
    assert all(c["source_coordinates"][0]["document_hash"] for c in entitlement_claims)

    # 3) Trình duyệt: đủ điều kiện ⇒ READY_FOR_REVIEW + PENDING.
    submit = await client.post(
        f"/api/v1/quotes/{quote_id}/submit-review",
        json={"comment": "Trình Quản lý duyệt"},
        headers=SALE_HEADERS,
    )
    assert submit.status_code == 200, submit.text
    submitted = submit.json()
    assert submitted["status"] == "READY_FOR_REVIEW"
    assert submitted["approval_status"] == "PENDING"
    assert all(item["ok"] for item in submitted["checklist"])
    assert submitted["evidence"]["bundle_id"]

    # 4) Audit trail: sự kiện submit nằm trong hash-chain và chuỗi còn nguyên.
    audit = await client.get(f"/api/v1/quotes/{quote_id}/audit", headers=SALE_HEADERS)
    assert audit.status_code == 200
    audit_body = audit.json()
    assert audit_body["is_chain_intact"] is True
    assert any(e["event_type"] == "QUOTE_SUBMITTED_FOR_REVIEW" for e in audit_body["events"])

    # 5) Outbox: sự kiện thông báo Manager được xếp hàng trong cùng giao dịch.
    async with async_test_session_factory() as db:
        rows = (
            await db.execute(
                select(TransactionalOutboxModel).where(TransactionalOutboxModel.aggregate_id == quote_id)
            )
        ).scalars().all()
    assert any(r.event_type == "QUOTE_SUBMITTED_FOR_REVIEW" for r in rows)

    # 6) Manager (khác người tạo) duyệt được và báo giá ký số.
    approve = await client.post(
        f"/api/v1/quotes/{quote_id}/approve",
        json={"approval_notes": "OK"},
        headers={"X-User-Id": "MGR-002", "If-Match": submit.headers.get("ETag", 'W/"1"')},
    )
    assert approve.status_code == 200, approve.text
    assert approve.json()["status"] == "APPROVED"
    assert approve.json()["signature"]


@pytest.mark.asyncio
async def test_submit_review_blocks_incomplete_quote_with_checklist(client: AsyncClient):
    """Bản khuyết (chưa tính) KHÔNG được đẩy sang Manager — 409 kèm checklist chỉ đúng việc cần làm."""
    quote_id = await _create_quote(client, unit_code="ZEN-A-0803")

    blocked = await client.post(
        f"/api/v1/quotes/{quote_id}/submit-review",
        json={"comment": "Gửi sớm"},
        headers=SALE_HEADERS,
    )
    assert blocked.status_code == 409
    detail = blocked.json()["detail"]
    assert detail["code"] == "QUOTE_NOT_READY"
    items = {item["key"]: item for item in detail["checklist"]}
    assert set(items) == {"calculated", "evidence", "compliance"}
    assert items["calculated"]["ok"] is False
    assert items["evidence"]["ok"] is False

    # Báo giá vẫn ở DRAFT — không có trạng thái nửa vời nào bị ghi.
    quote = await client.get(f"/api/v1/quotes/{quote_id}", headers=SALE_HEADERS)
    assert quote.json()["status"] == "DRAFT"
    assert quote.json()["approval_status"] == "NOT_REQUIRED"


@pytest.mark.asyncio
async def test_evidence_missing_before_calculate_is_explicit_not_404(client: AsyncClient):
    """Chưa có bằng chứng ⇒ trả MISSING + gợi ý bước tiếp theo (UI không hiểu nhầm là lỗi mạng)."""
    quote_id = await _create_quote(client, unit_code="ZEN-B-1502")

    resp = await client.get(f"/api/v1/quotes/{quote_id}/evidence", headers=SALE_HEADERS)
    assert resp.status_code == 200
    body = resp.json()
    assert body["claims"] == []
    assert body["decision_status"] == "MISSING"
    assert "calculate" in body["hint"]


@pytest.mark.asyncio
async def test_pdf_retry_requires_snapshot_then_queues_outbox(client: AsyncClient):
    """Phát lại PDF: chặn khi chưa có snapshot, xếp outbox khi đã tính xong."""
    quote_id = await _create_quote(client)

    early = await client.post(f"/api/v1/quotes/{quote_id}/pdf-retry", headers=SALE_HEADERS)
    assert early.status_code == 409
    assert early.json()["detail"]["code"] == "QUOTE_NOT_READY"

    await _calculate(client, quote_id)
    retry = await client.post(f"/api/v1/quotes/{quote_id}/pdf-retry", headers=SALE_HEADERS)
    assert retry.status_code == 200
    assert retry.json()["pdf_status"] == "RETRYING"

    async with async_test_session_factory() as db:
        rows = (
            await db.execute(
                select(TransactionalOutboxModel).where(TransactionalOutboxModel.aggregate_id == quote_id)
            )
        ).scalars().all()
    assert any(r.event_type == "OFFICIAL_QUOTE_ISSUED" for r in rows)


@pytest.mark.asyncio
async def test_new_version_endpoint_supersedes_and_restarts_lifecycle(client: AsyncClient):
    """`/versions` (đường Quản lý yêu cầu sửa): bản cũ SUPERSEDED, bản mới phải tính lại + có bằng chứng."""
    quote_id = await _create_quote(client)
    await _calculate(client, quote_id)

    resp = await client.post(f"/api/v1/quotes/{quote_id}/versions", headers=SALE_HEADERS)
    assert resp.status_code == 201, resp.text
    new_quote = resp.json()
    assert new_quote["quote_id"] == f"{quote_id}-V2"
    assert new_quote["quote_version"] == 2

    # Bản mới chưa tính ⇒ chưa trình duyệt được (vòng đời bắt đầu lại đúng quy trình).
    blocked = await client.post(
        f"/api/v1/quotes/{new_quote['quote_id']}/submit-review",
        json={},
        headers=SALE_HEADERS,
    )
    assert blocked.status_code == 409
    assert blocked.json()["detail"]["code"] == "QUOTE_NOT_READY"
