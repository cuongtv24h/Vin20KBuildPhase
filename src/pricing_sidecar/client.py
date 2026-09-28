"""Dual-Mode Pricing Sidecar Client Adapter (Task 5.5).

FCS v2.6 Reference: Section 1.1 (Engine Boundary)
TD-4.1 Reference: Section 2.1, 2.2, 3.2 (Sidecar UDS IPC, Fallback)
TD-4.4 Reference: Section 3.1, 4.1 (Error Codes, Tool Contracts)
Implement Plan Detail Reference: Section 7.1, 7.5

Supports two operational modes:
1. SidecarMode.IPC: Communicates over Unix Domain Socket or Local TCP Loopback.
2. SidecarMode.DIRECT: In-memory direct calculation without socket overhead (fast test / fallback).
"""

import asyncio
import json
import logging
import os
import uuid
from enum import StrEnum
from typing import Any

from src.pricing_sidecar.arithmetic import assert_no_float
from src.pricing_sidecar.canonical_hash import create_pricing_calculation_output
from src.pricing_sidecar.contracts import (
    OptimizationObjective,
    PricingCalculationInput,
    PricingCalculationOutput,
    RecommendationResult,
    ScenarioCalculationResult,
    ValidationReport,
)
from src.pricing_sidecar.engine import (
    calculate_pa_chudong,
    calculate_pa_nhanh,
    calculate_pa_vay,
)
from src.pricing_sidecar.ranking import recommend_best_scenario
from src.pricing_sidecar.server import (
    DEFAULT_SOCKET_PATH,
    DEFAULT_TCP_HOST,
    DEFAULT_TCP_PORT,
    ERROR_CALCULATOR_UNAVAILABLE,
    _serialize_for_wire,
)
from src.pricing_sidecar.validation import validate_pricing_results

logger = logging.getLogger("pricing_sidecar.client")


class SidecarMode(StrEnum):
    """Operational mode for the Pricing Sidecar Client."""

    IPC = "ipc"
    DIRECT = "direct"


class PricingSidecarError(Exception):
    """Exception raised when Sidecar Worker returns an error or is unreachable."""

    def __init__(
        self,
        message: str,
        error_code: str = ERROR_CALCULATOR_UNAVAILABLE,
        status_code: int = 503,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.error_code = error_code
        self.status_code = status_code
        self.details = details or {}


class PricingSidecarClient:
    """Client adapter connecting to the Hardened Pricing Sidecar Worker."""

    def __init__(
        self,
        mode: SidecarMode | str = SidecarMode.IPC,
        socket_path: str | None = None,
        host: str = DEFAULT_TCP_HOST,
        port: int = DEFAULT_TCP_PORT,
        use_tcp: bool | None = None,
        timeout_seconds: float = 1.0,
        fallback_to_direct: bool = True,
    ) -> None:
        self.mode = SidecarMode(mode)
        self.host = host
        self.port = port
        self.timeout_seconds = timeout_seconds
        self.fallback_to_direct = fallback_to_direct

        if use_tcp is not None:
            self.use_tcp = use_tcp
        else:
            self.use_tcp = os.name == "nt" or (socket_path is None)

        self.socket_path = socket_path if socket_path else (None if self.use_tcp else DEFAULT_SOCKET_PATH)

    # -----------------------------------------------------------------------
    # Low-Level Async Socket IPC Execution
    # -----------------------------------------------------------------------
    async def send_request(self, action: str, payload: dict[str, Any], request_id: str | None = None) -> dict[str, Any]:
        """Send request to the Sidecar server over socket or direct in-memory."""
        req_id = request_id or f"req-{uuid.uuid4().hex[:12]}"
        req_data = {
            "action": action,
            "request_id": req_id,
            "payload": _serialize_for_wire(payload),
        }

        if self.mode == SidecarMode.DIRECT:
            return await self._execute_direct_action(action, req_data["payload"], req_id)

        # Mode IPC: Connect via socket
        try:
            return await self._send_socket_request(req_data)
        except PricingSidecarError:
            raise
        except Exception as ex:
            if self.fallback_to_direct:
                logger.warning(
                    "Sidecar IPC connection failed (%s). Falling back to Direct in-memory engine.",
                    ex,
                )
                return await self._execute_direct_action(action, req_data["payload"], req_id)
            raise PricingSidecarError(
                message=f"CALCULATOR_UNAVAILABLE: Cannot communicate with pricing sidecar: {str(ex)}",
                error_code=ERROR_CALCULATOR_UNAVAILABLE,
                status_code=503,
            ) from ex

    async def _send_socket_request(self, req_data: dict[str, Any]) -> dict[str, Any]:
        """Establish socket connection, send newline-delimited JSON, and read response."""
        if self.use_tcp:
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(self.host, self.port),
                timeout=self.timeout_seconds,
            )
        else:
            assert self.socket_path is not None
            reader, writer = await asyncio.wait_for(
                asyncio.open_unix_connection(self.socket_path),
                timeout=self.timeout_seconds,
            )

        try:
            req_bytes = json.dumps(req_data, separators=(",", ":"), ensure_ascii=False).encode("utf-8") + b"\n"
            writer.write(req_bytes)
            await writer.drain()

            resp_line = await asyncio.wait_for(reader.readline(), timeout=self.timeout_seconds)
            if not resp_line:
                raise PricingSidecarError(
                    "CALCULATOR_UNAVAILABLE: Empty response received from pricing sidecar.",
                    error_code=ERROR_CALCULATOR_UNAVAILABLE,
                    status_code=503,
                )

            resp_json = json.loads(resp_line.decode("utf-8"))
            if not resp_json.get("success", False):
                err = resp_json.get("error", {})
                raise PricingSidecarError(
                    message=err.get("message", "Unknown sidecar error"),
                    error_code=err.get("error_code", "ERROR"),
                    status_code=err.get("status_code", 500),
                    details=err,
                )

            return resp_json.get("data", {})
        finally:
            writer.close()
            await writer.wait_closed()

    # -----------------------------------------------------------------------
    # Direct In-Memory Action Execution (Fast Test / Fallback)
    # -----------------------------------------------------------------------
    async def _execute_direct_action(self, action: str, payload: dict[str, Any], request_id: str) -> dict[str, Any]:
        """Execute calculation directly in-memory using pure math engine."""
        if action in ("ping", "health", "health_check"):
            return {
                "status": "ok",
                "service": "pricing-worker-direct",
                "version": "v2.6",
                "mode": "direct",
            }

        if action == "calculate_scenarios":
            inp = PricingCalculationInput.model_validate(payload)
            assert_no_float(inp)

            cd = calculate_pa_chudong(
                listed_price_vnd=inp.listed_price_vnd,
                approved_benefits=inp.approved_benefits,
                deposit_amount_vnd=inp.deposit_amount_vnd,
                vat_rate=inp.tax_vat_rate,
                maintenance_fee_rate=inp.maintenance_fee_rate,
                max_discount_rate=inp.max_discount_rate,
                max_total_discount_cap_rate=inp.max_total_discount_cap_rate,
                deposit_date=inp.deposit_date,
            )
            nh = calculate_pa_nhanh(
                listed_price_vnd=inp.listed_price_vnd,
                approved_benefits=inp.approved_benefits,
                deposit_amount_vnd=inp.deposit_amount_vnd,
                vat_rate=inp.tax_vat_rate,
                maintenance_fee_rate=inp.maintenance_fee_rate,
                max_discount_rate=inp.max_discount_rate,
                max_total_discount_cap_rate=inp.max_total_discount_cap_rate,
                deposit_date=inp.deposit_date,
            )
            vy = calculate_pa_vay(
                listed_price_vnd=inp.listed_price_vnd,
                approved_benefits=inp.approved_benefits,
                deposit_amount_vnd=inp.deposit_amount_vnd,
                vat_rate=inp.tax_vat_rate,
                maintenance_fee_rate=inp.maintenance_fee_rate,
                max_discount_rate=inp.max_discount_rate,
                max_total_discount_cap_rate=inp.max_total_discount_cap_rate,
                deposit_date=inp.deposit_date,
            )
            scenarios = [cd, nh, vy]

            val_report = validate_pricing_results(scenarios, listed_price_vnd=inp.listed_price_vnd)
            rec_result = recommend_best_scenario(scenarios, objective=OptimizationObjective.MIN_NET_PRICE)

            output = create_pricing_calculation_output(
                input_data=inp,
                scenario_results=scenarios,
                recommended_result=rec_result,
                validation_report=val_report,
            )
            return _serialize_for_wire(output)

        if action == "validate_pricing":
            scenarios: list[ScenarioCalculationResult] = []
            if "scenario_results" in payload:
                for item in payload["scenario_results"]:
                    scenarios.append(ScenarioCalculationResult.model_validate(item))
            elif isinstance(payload, list):
                for item in payload:
                    scenarios.append(ScenarioCalculationResult.model_validate(item))
            else:
                scenarios.append(ScenarioCalculationResult.model_validate(payload))

            report = validate_pricing_results(scenarios, raise_on_error=False)
            return _serialize_for_wire(report)

        if action == "rank_scenarios":
            sc_list = [ScenarioCalculationResult.model_validate(s) for s in payload.get("scenarios", [])]
            obj_str = payload.get("objective", OptimizationObjective.MIN_NET_PRICE.value)
            objective = OptimizationObjective(obj_str)
            infeasible = payload.get("infeasible_scenarios", None)

            rec = recommend_best_scenario(
                scenarios=sc_list,
                objective=objective,
                infeasible_scenarios=infeasible,
            )
            return _serialize_for_wire(rec)

        raise PricingSidecarError(
            message=f"Unknown action: '{action}'",
            error_code="INVALID_REQUEST",
            status_code=400,
        )

    # -----------------------------------------------------------------------
    # Strongly-Typed Public API Methods (Async)
    # -----------------------------------------------------------------------
    async def ping(self) -> dict[str, Any]:
        """Perform health check on the pricing sidecar worker."""
        return await self.send_request("ping", {})

    async def calculate_scenarios(
        self, input_data: PricingCalculationInput | dict[str, Any]
    ) -> PricingCalculationOutput:
        """Execute calculation of 3 canonical scenarios through the sidecar."""
        raw_input = input_data.model_dump(mode="python") if hasattr(input_data, "model_dump") else input_data
        data = await self.send_request("calculate_scenarios", raw_input)
        return PricingCalculationOutput.model_validate(data)

    async def validate_pricing(
        self,
        calc_target: (
            PricingCalculationOutput | ScenarioCalculationResult | list[ScenarioCalculationResult] | dict[str, Any]
        ),
    ) -> ValidationReport:
        """Verify calculations against 6 Sanity Checks."""
        raw_target = calc_target.model_dump(mode="python") if hasattr(calc_target, "model_dump") else calc_target
        data = await self.send_request("validate_pricing", raw_target)
        return ValidationReport.model_validate(data)

    async def rank_scenarios(
        self,
        scenarios: list[ScenarioCalculationResult] | list[dict[str, Any]],
        objective: OptimizationObjective = OptimizationObjective.MIN_NET_PRICE,
        infeasible_scenarios: list[str] | None = None,
    ) -> RecommendationResult:
        """Rank scenarios by optimization objective and tie-break rules."""
        raw_scenarios = [s.model_dump(mode="python") if hasattr(s, "model_dump") else s for s in scenarios]
        payload = {
            "scenarios": raw_scenarios,
            "objective": objective.value if hasattr(objective, "value") else str(objective),
            "infeasible_scenarios": infeasible_scenarios,
        }
        data = await self.send_request("rank_scenarios", payload)
        return RecommendationResult.model_validate(data)

    # -----------------------------------------------------------------------
    # Synchronous Wrappers for Blocking Contexts / Fast Scripts
    # -----------------------------------------------------------------------
    def ping_sync(self) -> dict[str, Any]:
        """Synchronous wrapper for ping."""
        return asyncio.run(self.ping())

    def calculate_scenarios_sync(
        self, input_data: PricingCalculationInput | dict[str, Any]
    ) -> PricingCalculationOutput:
        """Synchronous wrapper for calculate_scenarios."""
        return asyncio.run(self.calculate_scenarios(input_data))

    def validate_pricing_sync(
        self,
        calc_target: (
            PricingCalculationOutput | ScenarioCalculationResult | list[ScenarioCalculationResult] | dict[str, Any]
        ),
    ) -> ValidationReport:
        """Synchronous wrapper for validate_pricing."""
        return asyncio.run(self.validate_pricing(calc_target))

    def rank_scenarios_sync(
        self,
        scenarios: list[ScenarioCalculationResult] | list[dict[str, Any]],
        objective: OptimizationObjective = OptimizationObjective.MIN_NET_PRICE,
        infeasible_scenarios: list[str] | None = None,
    ) -> RecommendationResult:
        """Synchronous wrapper for rank_scenarios."""
        return asyncio.run(self.rank_scenarios(scenarios, objective, infeasible_scenarios))
