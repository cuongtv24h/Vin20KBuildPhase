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

from src.api.deps import create_access_token

POLICY_ADMIN_HEADERS = {
    "Authorization": f"Bearer {create_access_token('minh.tuan@vlandfuture.vn', 'POLICY_ADMIN')}",
}
SALE_HEADERS = {
    "Authorization": f"Bearer {create_access_token('nam.hoang@vlandfuture.vn', 'SALE')}",
}


@pytest.mark.asyncio
async def test_trigger_benchmark_run_endpoint(client: AsyncClient) -> None:
    """Trigger full 17-vector benchmark run and verify AC-FIN-01 Zero-Delta compliance."""
    response = await client.post("/api/v1/evaluation/benchmark-runs", json={}, headers=POLICY_ADMIN_HEADERS)
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
async def test_benchmark_report_matches_frontend_contract(client: AsyncClient) -> None:
    """Report phải mang đủ field mà màn hình /admin/benchmark đọc (chống lệch shape lần nữa)."""
    response = await client.post("/api/v1/evaluation/benchmark-runs", json={}, headers=POLICY_ADMIN_HEADERS)
    assert response.status_code == 200
    data = response.json()

    # BenchmarkRun contract
    for key in ("run_id", "started_at", "finished_at", "total", "passed", "exact_match_rate", "cases"):
        assert key in data, f"thiếu field contract: {key}"
    assert data["total"] == data["total_cases"] == 17
    assert data["passed"] == data["passed_cases"] == 17
    assert data["exact_match_rate"] == pytest.approx(1.0)
    assert len(data["cases"]) == 17

    # BenchmarkCaseResult contract
    passing_case = next(c for c in data["cases"] if c["status"] == "PASSED")
    for key in ("case_id", "name", "listed_price_before_tax_vnd", "expected", "actual", "delta_vnd", "passed"):
        assert key in passing_case, f"thiếu field contract: {key}"
    assert passing_case["passed"] is True
    for key in ("discount_vnd", "net_price_before_tax_vnd", "vat_vnd", "kpbt_vnd", "total_contract_price_vnd"):
        assert key in passing_case["expected"]
        assert key in passing_case["actual"]

    # Văn bản golden đang khoá được ghi nhận cùng lần chạy
    assert data["golden_policy_ref"] == "POL-2026-VLF-GEN v2.6"
    assert data["policy_alignment"] == "MATCH"


@pytest.mark.asyncio
async def test_benchmark_run_requires_quality_role(client: AsyncClient) -> None:
    """Không có token hoặc vai trò Sale đều bị chặn (đồng bộ với mock server)."""
    assert (await client.post("/api/v1/evaluation/benchmark-runs", json={})).status_code == 403
    assert (await client.post("/api/v1/evaluation/benchmark-runs", json={}, headers=SALE_HEADERS)).status_code == 403


@pytest.mark.asyncio
async def test_get_benchmark_run_by_id(client: AsyncClient) -> None:
    """Execute run then retrieve it by run_id."""
    # 1. Trigger run
    trigger_resp = await client.post(
        "/api/v1/evaluation/benchmark-runs",
        json={"case_ids": ["TC-01", "TC-02"]},
        headers=POLICY_ADMIN_HEADERS,
    )
    assert trigger_resp.status_code == 200
    run_id = trigger_resp.json()["run_id"]

    # 2. Retrieve by ID
    get_resp = await client.get(f"/api/v1/evaluation/benchmark-runs/{run_id}", headers=POLICY_ADMIN_HEADERS)
    assert get_resp.status_code == 200
    retrieved_data = get_resp.json()
    assert retrieved_data["run_id"] == run_id
    assert retrieved_data["total_cases"] == 2
    assert retrieved_data["passed_cases"] == 2


@pytest.mark.asyncio
async def test_get_benchmark_run_not_found(client: AsyncClient) -> None:
    """Non-existent run_id returns HTTP 404."""
    resp = await client.get("/api/v1/evaluation/benchmark-runs/NONEXISTENT-RUN-ID", headers=POLICY_ADMIN_HEADERS)
    assert resp.status_code == 404
    data = resp.json()
    assert "not found" in data["detail"].lower()


@pytest.mark.asyncio
async def test_list_benchmark_runs(client: AsyncClient) -> None:
    """List historical benchmark runs."""
    resp = await client.get("/api/v1/evaluation/benchmark-runs", headers=POLICY_ADMIN_HEADERS)
    assert resp.status_code == 200
    runs = resp.json()
    assert isinstance(runs, list)
    assert len(runs) >= 1
    assert "run_id" in runs[0]
    assert "accuracy_rate" in runs[0]
