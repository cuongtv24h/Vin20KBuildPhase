import pytest


@pytest.mark.asyncio
async def test_health(client):
    response = await client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"


@pytest.mark.asyncio
async def test_chat_empty_message(client):
    response = await client.post("/api/v1/chat", json={"message": ""})
    assert response.status_code == 422  # Validation error


@pytest.mark.asyncio
async def test_agent_status(client):
    response = await client.get("/api/v1/status")
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_pricing_mock_rejects_unverified_bundle(client):
    """Test that Pricing Engine strictly rejects unverified bundle."""
    payload = {
        "evidence_bundle_ref": {
            "bundle_id": "EB-001",
            "bundle_hash": "sha256:abc",
            "decision_status": "ABSTAINED",
            "resolved_policy_snapshot_hash": "sha256:snap1",
        }
    }
    response = await client.post("/api/v1/pricing/calculate", json=payload)
    assert response.status_code == 400
    assert "not VERIFIED" in response.json()["detail"]


@pytest.mark.asyncio
async def test_pricing_mock_accepts_verified_bundle(client):
    """Test that Pricing Engine accepts VERIFIED evidence bundle."""
    payload = {
        "evidence_bundle_ref": {
            "bundle_id": "EB-001",
            "bundle_hash": "sha256:e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
            "decision_status": "VERIFIED",
            "resolved_policy_snapshot_hash": "sha256:snap1",
        }
    }
    response = await client.post("/api/v1/pricing/calculate", json=payload)
    assert response.status_code == 200
    assert response.json()["status"] == "success"


@pytest.mark.asyncio
async def test_correlation_id_propagation_and_generation(client):
    # 1. Given explicit X-Correlation-ID -> echoed in headers
    resp = await client.get("/health", headers={"X-Correlation-ID": "trace-custom-999"})
    assert resp.status_code == 200
    assert resp.headers["X-Correlation-ID"] == "trace-custom-999"
    assert resp.headers["X-Request-ID"] == "trace-custom-999"

    # 2. No header given -> auto-generated trace ID
    resp2 = await client.get("/health")
    assert resp2.status_code == 200
    assert "X-Correlation-ID" in resp2.headers
    assert resp2.headers["X-Correlation-ID"].startswith("trace-")


@pytest.mark.asyncio
async def test_domain_error_carries_request_correlation_id(client):
    # Requesting non-existent session triggers DomainError (ErrorCode.NOT_FOUND)
    resp = await client.get(
        "/api/v1/pre-sales/sessions/PS-NONEXISTENT",
        headers={"X-Correlation-ID": "trace-error-test-456"},
    )
    assert resp.status_code == 400
    data = resp.json()
    assert data["detail"]["correlation_id"] == "trace-error-test-456"
