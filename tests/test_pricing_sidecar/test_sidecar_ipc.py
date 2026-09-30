"""Comprehensive Test Suite for Hardened UDS / TCP Sidecar Worker & Client (Tasks 5.1 - 5.5).

Validates:
- Task 5.1 & 5.2: UDS / TCP socket lifecycle, dynamic port binding, multi-client connection.
- Task 5.3: Hard 50ms timeout enforcement, 1MB maximum payload guard, RFC 9457 error contracts.
- Task 5.4: Health check endpoint (PING -> PONG) and Graceful shutdown handling.
- Task 5.5: Dual-mode client (SidecarMode.IPC vs SidecarMode.DIRECT), automatic fallback, sync wrappers.
"""

import asyncio
import json
from datetime import date
from decimal import Decimal

import pytest

from src.pricing_sidecar.arithmetic import assert_no_float
from src.pricing_sidecar.client import (
    PricingSidecarClient,
    PricingSidecarError,
    SidecarMode,
)
from src.pricing_sidecar.contracts import (
    OptimizationObjective,
    PricingCalculationInput,
    PricingCalculationOutput,
    RecommendationResult,
    ScenarioType,
    ValidationReport,
    create_pa_chudong_config,
    create_pa_nhanh_config,
    create_pa_vay_config,
)
from src.pricing_sidecar.server import (
    DEFAULT_TCP_HOST,
    ERROR_CALCULATOR_UNAVAILABLE,
    ERROR_INVALID_REQUEST,
    ERROR_PAYLOAD_TOO_LARGE,
    PricingSidecarServer,
)


@pytest.fixture
def sample_pricing_input() -> PricingCalculationInput:
    """Fixture providing a standard valid PricingCalculationInput."""
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
async def test_server_lifecycle_and_health_check() -> None:
    """Task 5.2 & 5.4: Test TCP loopback server lifecycle and health check."""
    server = PricingSidecarServer(host=DEFAULT_TCP_HOST, port=0, use_tcp=True)
    await server.start()

    assert server.is_running is True
    assert server.port > 0
    assert "tcp://127.0.0.1:" in server.bound_address

    client = PricingSidecarClient(
        mode=SidecarMode.IPC,
        host=server.host,
        port=server.port,
        use_tcp=True,
        fallback_to_direct=False,
    )

    # Health check ping
    pong = await client.ping()
    assert pong["status"] == "ok"
    assert pong["service"] == "pricing-worker"
    assert pong["version"] == "v2.6"
    assert "bound_address" in pong
    assert "timestamp" in pong

    # Graceful shutdown
    await server.stop()
    assert server.is_running is False


@pytest.mark.asyncio
async def test_calculate_scenarios_ipc_roundtrip(
    sample_pricing_input: PricingCalculationInput,
) -> None:
    """Task 5.2 & 5.5: Full calculation roundtrip over socket IPC."""
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

        output: PricingCalculationOutput = await client.calculate_scenarios(sample_pricing_input)

        # Invariant and schema validation
        assert_no_float(output)
        assert len(output.scenario_results) == 3
        scenario_types = [s.scenario_type for s in output.scenario_results]
        assert ScenarioType.STANDARD_PROGRESS in scenario_types
        assert ScenarioType.EARLY_95 in scenario_types
        assert ScenarioType.BANK_LOAN_HTLS in scenario_types

        # Recommended scenario present
        assert output.recommended_result is not None
        assert output.recommended_result.recommended_scenario in [
            ScenarioType.STANDARD_PROGRESS,
            ScenarioType.EARLY_95,
            ScenarioType.BANK_LOAN_HTLS,
        ]

        # Canonical hash verification
        assert output.canonical_snapshot_hash is not None
        assert len(output.canonical_snapshot_hash) == 64

        # Sanity check report verification
        assert output.validation_report is not None
        assert output.validation_report.is_valid is True
        assert len(output.validation_report.field_errors) == 0
    finally:
        await server.stop()


@pytest.mark.asyncio
async def test_validate_pricing_and_ranking_ipc(
    sample_pricing_input: PricingCalculationInput,
) -> None:
    """Task 5.2: Test IPC validation and ranking dedicated endpoints."""
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

        calc_out = await client.calculate_scenarios(sample_pricing_input)

        # Dedicated validation call
        val_report: ValidationReport = await client.validate_pricing(calc_out.scenario_results)
        assert val_report.is_valid is True

        # Dedicated ranking call
        rank_res: RecommendationResult = await client.rank_scenarios(
            scenarios=calc_out.scenario_results,
            objective=OptimizationObjective.MIN_NET_PRICE,
        )
        assert rank_res.recommended_scenario is not None
        assert len(rank_res.comparison_summary) == 3
    finally:
        await server.stop()


@pytest.mark.asyncio
async def test_guard_payload_too_large() -> None:
    """Task 5.3: Guard against requests exceeding 1MB limit."""
    server = PricingSidecarServer(
        host=DEFAULT_TCP_HOST,
        port=0,
        use_tcp=True,
        max_request_size=1024,  # Artificially set to 1KB for test
    )
    await server.start()

    try:
        reader, writer = await asyncio.open_connection(server.host, server.port)
        # Send payload > 1KB
        oversized = {"action": "ping", "payload": {"dummy": "x" * 2048}}
        oversized_bytes = json.dumps(oversized).encode("utf-8") + b"\n"
        writer.write(oversized_bytes)
        await writer.drain()

        resp_line = await reader.readline()
        resp_json = json.loads(resp_line.decode("utf-8"))

        assert resp_json["success"] is False
        assert resp_json["error"]["error_code"] == ERROR_PAYLOAD_TOO_LARGE
        assert resp_json["error"]["status_code"] == 413

        writer.close()
        await writer.wait_closed()
    finally:
        await server.stop()


@pytest.mark.asyncio
async def test_guard_timeout_enforcement() -> None:
    """Task 5.3: Guard against processing timeouts (> 50ms hard limit)."""
    # Create server with strict 10ms timeout
    server = PricingSidecarServer(
        host=DEFAULT_TCP_HOST,
        port=0,
        use_tcp=True,
        timeout_seconds=0.010,
    )

    # Simulate slow processing beyond timeout
    async def slow_process(line: bytes):
        await asyncio.sleep(0.030)
        return {"success": True}

    server._process_request_line = slow_process  # type: ignore
    await server.start()

    try:
        reader, writer = await asyncio.open_connection(server.host, server.port)
        req = {"action": "ping", "payload": {}}
        writer.write(json.dumps(req).encode("utf-8") + b"\n")
        await writer.drain()

        resp_line = await reader.readline()
        resp_json = json.loads(resp_line.decode("utf-8"))

        assert resp_json["success"] is False
        assert resp_json["error"]["error_code"] == ERROR_CALCULATOR_UNAVAILABLE
        assert resp_json["error"]["status_code"] == 503
        assert "hard timeout" in resp_json["error"]["message"]

        writer.close()
        await writer.wait_closed()
    finally:
        await server.stop()


@pytest.mark.asyncio
async def test_guard_invalid_json_payload() -> None:
    """Task 5.3: Error handling for malformed JSON."""
    server = PricingSidecarServer(host=DEFAULT_TCP_HOST, port=0, use_tcp=True)
    await server.start()

    try:
        reader, writer = await asyncio.open_connection(server.host, server.port)
        writer.write(b"NOT_A_VALID_JSON_STRING\n")
        await writer.drain()

        resp_line = await reader.readline()
        resp_json = json.loads(resp_line.decode("utf-8"))

        assert resp_json["success"] is False
        assert resp_json["error"]["error_code"] == ERROR_INVALID_REQUEST
        assert resp_json["error"]["status_code"] == 400

        writer.close()
        await writer.wait_closed()
    finally:
        await server.stop()


@pytest.mark.asyncio
async def test_guard_unknown_action() -> None:
    """Task 5.3: Error handling for unknown action string."""
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
        with pytest.raises(PricingSidecarError) as exc_info:
            await client.send_request("unknown_nonexistent_action", {})

        assert exc_info.value.status_code == 400
        assert exc_info.value.error_code == ERROR_INVALID_REQUEST
    finally:
        await server.stop()


@pytest.mark.asyncio
async def test_dual_mode_direct_mode(sample_pricing_input: PricingCalculationInput) -> None:
    """Task 5.5: Test Client in Direct In-Memory Mode without socket server."""
    client = PricingSidecarClient(mode=SidecarMode.DIRECT)

    # Ping
    pong = await client.ping()
    assert pong["status"] == "ok"
    assert pong["mode"] == "direct"

    # Calculate
    calc_out = await client.calculate_scenarios(sample_pricing_input)
    assert len(calc_out.scenario_results) == 3
    assert calc_out.canonical_snapshot_hash is not None

    # Validate
    val_report = await client.validate_pricing(calc_out.scenario_results)
    assert val_report.is_valid is True

    # Rank
    rank_res = await client.rank_scenarios(calc_out.scenario_results)
    assert rank_res.recommended_scenario is not None


@pytest.mark.asyncio
async def test_dual_mode_automatic_fallback(sample_pricing_input: PricingCalculationInput) -> None:
    """Task 5.5: Test automatic fallback to Direct mode when IPC server is dead."""
    # Point to a closed port on loopback
    client = PricingSidecarClient(
        mode=SidecarMode.IPC,
        host=DEFAULT_TCP_HOST,
        port=59999,  # Non-listening port
        use_tcp=True,
        timeout_seconds=0.1,
        fallback_to_direct=True,  # Enable fallback
    )

    # Calculation should succeed by falling back gracefully
    calc_out = await client.calculate_scenarios(sample_pricing_input)
    assert len(calc_out.scenario_results) == 3
    assert calc_out.canonical_snapshot_hash is not None


@pytest.mark.asyncio
async def test_dual_mode_no_fallback_raises_error() -> None:
    """Task 5.5: Verify PricingSidecarError raised when fallback is disabled and server is dead."""
    client = PricingSidecarClient(
        mode=SidecarMode.IPC,
        host=DEFAULT_TCP_HOST,
        port=59999,
        use_tcp=True,
        timeout_seconds=0.1,
        fallback_to_direct=False,  # Disable fallback
    )

    with pytest.raises(PricingSidecarError) as exc_info:
        await client.ping()

    assert exc_info.value.status_code == 503
    assert exc_info.value.error_code == ERROR_CALCULATOR_UNAVAILABLE


def test_synchronous_wrappers(sample_pricing_input: PricingCalculationInput) -> None:
    """Task 5.5: Verify synchronous convenience wrappers run smoothly."""
    client = PricingSidecarClient(mode=SidecarMode.DIRECT)

    pong = client.ping_sync()
    assert pong["status"] == "ok"

    output = client.calculate_scenarios_sync(sample_pricing_input)
    assert len(output.scenario_results) == 3

    val = client.validate_pricing_sync(output.scenario_results)
    assert val.is_valid is True

    rank = client.rank_scenarios_sync(output.scenario_results)
    assert rank.recommended_scenario is not None
