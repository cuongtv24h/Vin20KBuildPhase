"""Khóa routing hợp đồng TD-4.4: đúng đường dẫn, đúng cơ chế chặn đầu vào.

Router wired → endpoint chưa implement trả 501; command POST thiếu
Idempotency-Key bị chặn 400 TRƯỚC khi vào logic (nguyên tắc contract-first).
"""

import pytest


@pytest.mark.asyncio
async def test_create_quote_requires_idempotency_key(client):
    response = await client.post("/api/v1/quotes", json={})
    assert response.status_code == 400
    assert "Idempotency-Key" in response.json()["detail"]


@pytest.mark.asyncio
async def test_create_quote_wired_but_not_implemented(client):
    response = await client.post(
        "/api/v1/quotes", json={}, headers={"Idempotency-Key": "test-key-001"}
    )
    assert response.status_code == 501


@pytest.mark.asyncio
async def test_sse_events_endpoint_wired(client):
    response = await client.get("/api/v1/quotes/Q-1/events")
    assert response.status_code == 501


@pytest.mark.asyncio
async def test_compliance_gate_endpoint_wired(client):
    response = await client.post("/api/v1/compliance/check-message", json={"message": "x"})
    assert response.status_code == 501


@pytest.mark.asyncio
async def test_pre_sales_session_endpoints_wired(client):
    response = await client.post("/api/v1/pre-sales/sessions")
    assert response.status_code == 501
    response = await client.post("/api/v1/pre-sales/sessions/s1/consent-and-handoff")
    assert response.status_code == 501


@pytest.mark.asyncio
async def test_jwks_endpoint_wired(client):
    response = await client.get("/api/v1/.well-known/jwks.json")
    assert response.status_code == 501
