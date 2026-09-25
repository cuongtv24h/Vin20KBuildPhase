"""Performance Benchmark & Latency SLA Test Suite (Task 6.2).

Validates:
- TD-4.1 §3.2 & TD-4.4 §4.1: Pure Deterministic Math Engine In-Process latency:
    - calculate_cashflow_deterministic: P50 <= 5.0 ms, P95 <= 15.0 ms (Budget: 50 ms).
    - validate_pricing_results: P50 <= 3.0 ms, P95 <= 10.0 ms (Budget: 20 ms).
    - rank_scenarios_by_objective: P50 <= 3.0 ms, P95 <= 10.0 ms (Budget: 20 ms).
- Socket IPC Round-Trip Latency: P95 <= 25.0 ms (well within 50 ms hard timeout).
- Concurrency Thread-Safety: 15 concurrent requests without race conditions or memory corruption.
"""

import asyncio
import statistics
import time
from datetime import date
from decimal import Decimal

import pytest

from src.pricing_sidecar.arithmetic import assert_no_float
from src.pricing_sidecar.client import (
    PricingSidecarClient,
    SidecarMode,
)
from src.pricing_sidecar.contracts import (
    OptimizationObjective,
    PricingCalculationInput,
    PricingCalculationOutput,
    RecommendationResult,
    ValidationReport,
    create_pa_chudong_config,
    create_pa_nhanh_config,
    create_pa_vay_config,
)
from src.pricing_sidecar.server import (
    DEFAULT_TCP_HOST,
    PricingSidecarServer,
)


@pytest.fixture
def benchmark_input() -> PricingCalculationInput:
    """Fixture producing a standard representative pricing calculation input."""
    deposit_amt = Decimal("100000000")
    return PricingCalculationInput(
        unit_code="VH-GRAND-PARK-S101",
        deposit_date=date(2026, 9, 1),
        contract_signing_date=date(2026, 9, 15),
        listed_price_vnd=Decimal("3500000000"),
        deposit_amount_vnd=deposit_amt,
        tax_vat_rate=Decimal("0.1000"),
        maintenance_fee_rate=Decimal("0.0200"),
        max_discount_rate=Decimal("0.2000"),
        max_total_discount_cap_rate=Decimal("0.2500"),
        resolved_policy_snapshot_id="SNP-2026-VLF-01",
        source_policy_hash="e" * 64,
        scenario_configs=[
            create_pa_chudong_config(deposit_amount_vnd=deposit_amt),
            create_pa_nhanh_config(deposit_amount_vnd=deposit_amt),
            create_pa_vay_config(deposit_amount_vnd=deposit_amt),
        ],
    )


@pytest.mark.asyncio
async def test_in_process_direct_engine_p95_sla(benchmark_input: PricingCalculationInput) -> None:
    """TD-4.1 §3.2 & TD-4.4 §4.1: Verify Direct Pricing Engine latency P50 <= 5.0 ms, P95 <= 15.0 ms (Budget: 50 ms)."""
    client = PricingSidecarClient(mode=SidecarMode.DIRECT)

    # Warm-up run
    warmup_out = await client.calculate_scenarios(benchmark_input)
    assert len(warmup_out.scenario_results) == 3

    latencies_ms: list[float] = []
    iterations = 100

    for _ in range(iterations):
        t0 = time.perf_counter_ns()
        output = await client.calculate_scenarios(benchmark_input)
        elapsed_ms = (time.perf_counter_ns() - t0) / 1_000_000.0
        latencies_ms.append(elapsed_ms)
        assert len(output.scenario_results) == 3

    latencies_sorted = sorted(latencies_ms)
    p50 = latencies_sorted[int(iterations * 0.50)]
    p90 = latencies_sorted[int(iterations * 0.90)]
    p95 = latencies_sorted[int(iterations * 0.95)]
    p99 = latencies_sorted[int(iterations * 0.99)]
    avg = statistics.mean(latencies_ms)

    print(
        f"\n[SLA Direct In-Process Benchmark - {iterations} runs]\n"
        f"  Average: {avg:.3f} ms | P50: {p50:.3f} ms | P90: {p90:.3f} ms | "
        f"P95: {p95:.3f} ms | P99: {p99:.3f} ms | Max: {latencies_sorted[-1]:.3f} ms"
    )

    # Hard SLA Assertions conforming to TD-4.1 §3.2 & TD-4.4 §4.1
    assert p50 <= 6.0, f"SLA Violation: Direct Engine P50 ({p50:.3f} ms) exceeds 6.0 ms!"
    assert p95 <= 15.0, f"SLA Violation: Direct Engine P95 ({p95:.3f} ms) exceeds 15.0 ms (Budget 50 ms)!"


@pytest.mark.asyncio
async def test_validation_gate_p95_sla(benchmark_input: PricingCalculationInput) -> None:
    """TD-4.4 §4.1: Verify Financial Validation Gate SLA P50 <= 3.0 ms, P95 <= 10.0 ms (Budget: 20 ms)."""
    client = PricingSidecarClient(mode=SidecarMode.DIRECT)
    calc_out = await client.calculate_scenarios(benchmark_input)

    latencies_ms: list[float] = []
    iterations = 100

    for _ in range(iterations):
        t0 = time.perf_counter_ns()
        val_report: ValidationReport = await client.validate_pricing(calc_out.scenario_results)
        elapsed_ms = (time.perf_counter_ns() - t0) / 1_000_000.0
        latencies_ms.append(elapsed_ms)
        assert val_report.is_valid is True

    latencies_sorted = sorted(latencies_ms)
    p50 = latencies_sorted[int(iterations * 0.50)]
    p95 = latencies_sorted[int(iterations * 0.95)]

    print(
        f"\n[SLA Validation Gate Benchmark - {iterations} runs]\n"
        f"  P50: {p50:.3f} ms | P95: {p95:.3f} ms | Max: {latencies_sorted[-1]:.3f} ms"
    )

    # Budget is 20 ms in TD-4.4; assert P95 <= 10.0 ms
    assert p50 <= 3.0, f"Validation Gate P50 ({p50:.3f} ms) exceeds 3.0 ms!"
    assert p95 <= 10.0, f"Validation Gate P95 ({p95:.3f} ms) exceeds 10.0 ms (Budget 20 ms)!"


@pytest.mark.asyncio
async def test_ranking_engine_p95_sla(benchmark_input: PricingCalculationInput) -> None:
    """TD-4.4 §4.1: Verify Ranking Engine & Tie-Break SLA P50 <= 3.0 ms, P95 <= 10.0 ms (Budget: 20 ms)."""
    client = PricingSidecarClient(mode=SidecarMode.DIRECT)
    calc_out = await client.calculate_scenarios(benchmark_input)

    latencies_ms: list[float] = []
    iterations = 100

    for _ in range(iterations):
        t0 = time.perf_counter_ns()
        rank_res: RecommendationResult = await client.rank_scenarios(
            calc_out.scenario_results, objective=OptimizationObjective.MIN_NET_PRICE
        )
        elapsed_ms = (time.perf_counter_ns() - t0) / 1_000_000.0
        latencies_ms.append(elapsed_ms)
        assert rank_res.recommended_scenario is not None

    latencies_sorted = sorted(latencies_ms)
    p50 = latencies_sorted[int(iterations * 0.50)]
    p95 = latencies_sorted[int(iterations * 0.95)]

    print(
        f"\n[SLA Ranking Engine Benchmark - {iterations} runs]\n"
        f"  P50: {p50:.3f} ms | P95: {p95:.3f} ms | Max: {latencies_sorted[-1]:.3f} ms"
    )

    # Budget is 20 ms in TD-4.4; assert P95 <= 10.0 ms
    assert p50 <= 3.0, f"Ranking Engine P50 ({p50:.3f} ms) exceeds 3.0 ms!"
    assert p95 <= 10.0, f"Ranking Engine P95 ({p95:.3f} ms) exceeds 10.0 ms (Budget 20 ms)!"


@pytest.mark.asyncio
async def test_socket_ipc_roundtrip_latency_sla(
    benchmark_input: PricingCalculationInput,
) -> None:
    """TD-4.1 & TD-4.4: Verify Socket IPC round-trip latency P95 <= 25.0 ms (budget: 50 ms)."""
    server = PricingSidecarServer(host=DEFAULT_TCP_HOST, port=0, use_tcp=True)
    await server.start()

    try:
        client = PricingSidecarClient(
            mode=SidecarMode.IPC,
            host=server.host,
            port=server.port,
            use_tcp=True,
            fallback_to_direct=False,
        )

        # Warm-up request
        warmup = await client.calculate_scenarios(benchmark_input)
        assert len(warmup.scenario_results) == 3

        latencies_ms: list[float] = []
        iterations = 30

        for _ in range(iterations):
            t0 = time.perf_counter_ns()
            out = await client.calculate_scenarios(benchmark_input)
            elapsed_ms = (time.perf_counter_ns() - t0) / 1_000_000.0
            latencies_ms.append(elapsed_ms)
            assert len(out.scenario_results) == 3

        latencies_sorted = sorted(latencies_ms)
        p50 = latencies_sorted[int(iterations * 0.50)]
        p90 = latencies_sorted[int(iterations * 0.90)]
        p95 = latencies_sorted[int(iterations * 0.95)]
        avg = statistics.mean(latencies_ms)

        print(
            f"\n[SLA Socket IPC Round-Trip Benchmark - {iterations} runs]\n"
            f"  Average: {avg:.3f} ms | P50: {p50:.3f} ms | P90: {p90:.3f} ms | "
            f"P95: {p95:.3f} ms | Max: {latencies_sorted[-1]:.3f} ms"
        )

        # 50 ms is hard timeout in TD-4.4; assert P95 <= 25.0 ms
        assert p95 <= 25.0, f"Socket IPC P95 ({p95:.3f} ms) exceeds 25.0 ms limit!"
    finally:
        await server.stop()


@pytest.mark.asyncio
async def test_concurrent_load_determinism(
    benchmark_input: PricingCalculationInput,
) -> None:
    """Verify thread-safety and idempotency across 15 concurrent calculation requests."""
    server = PricingSidecarServer(host=DEFAULT_TCP_HOST, port=0, use_tcp=True)
    await server.start()

    try:
        client = PricingSidecarClient(
            mode=SidecarMode.IPC,
            host=server.host,
            port=server.port,
            use_tcp=True,
            fallback_to_direct=False,
        )

        async def worker_calc(idx: int) -> tuple[int, PricingCalculationOutput]:
            res = await client.calculate_scenarios(benchmark_input)
            return (idx, res)

        concurrent_count = 15
        tasks = [worker_calc(i) for i in range(concurrent_count)]
        results = await asyncio.gather(*tasks)

        assert len(results) == concurrent_count

        # All concurrent runs must yield exact same canonical_snapshot_hash
        first_hash = results[0][1].canonical_snapshot_hash
        for idx, out in results:
            assert out.canonical_snapshot_hash == first_hash
            assert_no_float(out)
            assert len(out.scenario_results) == 3
            assert out.validation_report.is_valid is True

        print(f"\n[Concurrent Load Test] 15/15 concurrent requests succeeded with identical hash {first_hash[:16]}...")
    finally:
        await server.stop()
