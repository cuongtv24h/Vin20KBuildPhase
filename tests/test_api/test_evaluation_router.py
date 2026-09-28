"""
Integration Test Suite for Benchmark Evaluation Router (TD-4.4).
Tests endpoints:
- POST /api/v1/evaluation/benchmark-runs
- GET  /api/v1/evaluation/benchmark-runs/{run_id}
- GET  /api/v1/evaluation/benchmark-runs
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_trigger_benchmark_run_endpoint(client: AsyncClient) -> None:
    """Trigger full 17-vector benchmark run and verify AC-FIN-01 Zero-Delta compliance."""
    response = await client.post("/api/v1/evaluation/benchmark-runs", json={})
    assert response.status_code == 200

    data = response.json()
    assert "run_id" in data
    assert data["run_id"].startswith("BENCH-RUN-")
    assert data["total_cases"] == 17
    assert data["passed_cases"] == 17
    assert data["failed_cases"] == 0
    assert data["accuracy_rate"] == 100.0
    assert data["ac_fin_01_passed"] is True
    assert data["latency_p50_ms"] > 0
    assert data["latency_p95_ms"] >= data["latency_p50_ms"]
    assert len(data["results"]) == 17

    # Verify every passed result has delta_vnd == 0
    for res in data["results"]:
        assert res["delta_vnd"] == 0
        assert res["status"] in ("PASSED", "EXCEPTION_HANDLED")


@pytest.mark.asyncio
async def test_get_benchmark_run_by_id(client: AsyncClient) -> None:
    """Execute run then retrieve it by run_id."""
    # 1. Trigger run
    trigger_resp = await client.post(
        "/api/v1/evaluation/benchmark-runs",
        json={"case_ids": ["TC-01", "TC-02"]},
    )
    assert trigger_resp.status_code == 200
    run_id = trigger_resp.json()["run_id"]

    # 2. Retrieve by ID
    get_resp = await client.get(f"/api/v1/evaluation/benchmark-runs/{run_id}")
    assert get_resp.status_code == 200
    retrieved_data = get_resp.json()
    assert retrieved_data["run_id"] == run_id
    assert retrieved_data["total_cases"] == 2
    assert retrieved_data["passed_cases"] == 2


@pytest.mark.asyncio
async def test_get_benchmark_run_not_found(client: AsyncClient) -> None:
    """Non-existent run_id returns HTTP 404."""
    resp = await client.get("/api/v1/evaluation/benchmark-runs/NONEXISTENT-RUN-ID")
    assert resp.status_code == 404
    data = resp.json()
    assert "not found" in data["detail"].lower()


@pytest.mark.asyncio
async def test_list_benchmark_runs(client: AsyncClient) -> None:
    """List historical benchmark runs."""
    resp = await client.get("/api/v1/evaluation/benchmark-runs")
    assert resp.status_code == 200
    runs = resp.json()
    assert isinstance(runs, list)
    assert len(runs) >= 1
    assert "run_id" in runs[0]
    assert "accuracy_rate" in runs[0]
