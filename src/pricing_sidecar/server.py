"""Hardened UDS / TCP Sidecar Worker Server (Tasks 5.1 - 5.4).

FCS v2.6 Reference: Section 1.1 (Pure Deterministic Pricing Engine Boundary)
TD-4.1 Reference: Section 2.1, 2.2, 3.2 (Hardened Sidecar Worker, K8s Security Context)
TD-4.4 Reference: Section 3.1 (RFC 9457 Error Codes, CALCULATOR_UNAVAILABLE)
Implement Plan Detail Reference: Section 7.1, 7.3, 7.4 (D2-1, D2-3, D2-4)

Features:
- Unix Domain Socket `/var/run/pricing/engine.sock` with permission 0660 (Linux Production)
- Local TCP Loopback 127.0.0.1:8001 (Windows Dev Environment & Fallback)
- Enforced 50ms hard processing timeout
- Maximum request payload size limit: 1 MB (protects against DOS)
- RFC 9457 structured error responses
- Endpoint health_check (PING -> PONG)
- Graceful shutdown handling
"""

import asyncio
import json
import logging
import os
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any

from src.pricing_sidecar.arithmetic import assert_no_float
from src.pricing_sidecar.canonical_hash import (
    create_pricing_calculation_output,
)
from src.pricing_sidecar.contracts import (
    OptimizationObjective,
    PricingCalculationInput,
    ScenarioCalculationResult,
)
from src.pricing_sidecar.engine import (
    calculate_pa_chudong,
    calculate_pa_nhanh,
    calculate_pa_vay,
)
from src.pricing_sidecar.ranking import recommend_best_scenario
from src.pricing_sidecar.validation import (
    FinancialSanityError,
    validate_pricing_results,
)

logger = logging.getLogger("pricing_sidecar.server")

# ---------------------------------------------------------------------------
# Default Configuration Constants
# ---------------------------------------------------------------------------
DEFAULT_SOCKET_PATH: str = "/var/run/pricing/engine.sock"
DEFAULT_TCP_HOST: str = "127.0.0.1"
DEFAULT_TCP_PORT: int = 28001
MAX_REQUEST_SIZE: int = 1_048_576  # 1 MB
DEFAULT_PROCESSING_TIMEOUT_SECONDS: float = 0.050  # 50 ms
SOCKET_FILE_MODE: int = 0o660

ERROR_CALCULATOR_UNAVAILABLE: str = "CALCULATOR_UNAVAILABLE"
ERROR_INVALID_REQUEST: str = "INVALID_REQUEST"
ERROR_PAYLOAD_TOO_LARGE: str = "PAYLOAD_TOO_LARGE"
ERROR_FINANCIAL_SANITY_FAILED: str = "FINANCIAL_SANITY_FAILED"
ERROR_INTERNAL_ERROR: str = "INTERNAL_ERROR"


# ---------------------------------------------------------------------------
# Helper: JSON Serialization for Engine Entities
# ---------------------------------------------------------------------------
def _serialize_for_wire(obj: Any) -> Any:
    """Helper normalizing decimals, dates, and models into JSON-compatible dicts."""
    if isinstance(obj, Decimal):
        return int(obj) if obj % 1 == 0 else str(obj)
    if isinstance(obj, (date, datetime)):
        return obj.isoformat()
    if hasattr(obj, "model_dump"):
        return _serialize_for_wire(obj.model_dump(mode="python"))
    if isinstance(obj, dict):
        return {k: _serialize_for_wire(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_serialize_for_wire(item) for item in obj]
    return obj


# ---------------------------------------------------------------------------
# Core Server Class (Tasks 5.1 - 5.4)
# ---------------------------------------------------------------------------
class PricingSidecarServer:
    """Async IO Socket Server running the Deterministic Pricing Engine Sidecar."""

    def __init__(
        self,
        socket_path: str | None = None,
        host: str = DEFAULT_TCP_HOST,
        port: int = DEFAULT_TCP_PORT,
        use_tcp: bool | None = None,
        timeout_seconds: float = DEFAULT_PROCESSING_TIMEOUT_SECONDS,
        max_request_size: int = MAX_REQUEST_SIZE,
    ) -> None:
        self.socket_path = socket_path
        self.host = host
        self.port = port
        self.timeout_seconds = timeout_seconds
        self.max_request_size = max_request_size

        # Determine whether to use TCP or Unix Socket
        # On Windows (nt), Unix Domain Sockets often lack support/permissions -> default to TCP
        if use_tcp is not None:
            self.use_tcp = use_tcp
        else:
            self.use_tcp = os.name == "nt" or (self.socket_path is None)

        if not self.use_tcp and not self.socket_path:
            self.socket_path = DEFAULT_SOCKET_PATH

        self._server: asyncio.AbstractServer | None = None
        self._is_running = False

    @property
    def is_running(self) -> bool:
        """Check whether the socket server is currently active."""
        return self._is_running

    @property
    def bound_address(self) -> str:
        """Return human-readable address of the active listener."""
        if self.use_tcp:
            return f"tcp://{self.host}:{self.port}"
        return f"unix://{self.socket_path}"

    async def start(self) -> None:
        """Start listening on either UDS or TCP Loopback."""
        if self._is_running:
            return

        if self.use_tcp:
            self._server = await asyncio.start_server(
                self._handle_client,
                host=self.host,
                port=self.port,
            )
            # If dynamic port (port=0) was passed, capture actual bound port
            sockets = self._server.sockets
            if sockets:
                sockname = sockets[0].getsockname()
                if isinstance(sockname, tuple):
                    self.port = sockname[1]
            logger.info("Pricing Sidecar Worker started on %s", self.bound_address)
        else:
            assert self.socket_path is not None
            socket_dir = os.path.dirname(self.socket_path)
            if socket_dir and not os.path.exists(socket_dir):
                os.makedirs(socket_dir, exist_ok=True)

            if os.path.exists(self.socket_path):
                try:
                    os.unlink(self.socket_path)
                except OSError as e:
                    logger.warning("Could not unlink stale socket file: %s", e)

            self._server = await asyncio.start_unix_server(
                self._handle_client,
                path=self.socket_path,
            )

            # Apply permission 0660 (Task 5.1 / TD-4.1 §2.1)
            try:
                os.chmod(self.socket_path, SOCKET_FILE_MODE)
            except OSError as e:
                logger.warning("Failed to chmod socket to 0660: %s", e)

            logger.info("Pricing Sidecar Worker started on %s (mode 0660)", self.bound_address)

        self._is_running = True

    async def stop(self) -> None:
        """Gracefully stop the server and clean up filesystem socket resources (Task 5.4)."""
        if not self._is_running or not self._server:
            return

        self._server.close()
        await self._server.wait_closed()
        self._is_running = False

        if not self.use_tcp and self.socket_path and os.path.exists(self.socket_path):
            try:
                os.unlink(self.socket_path)
            except OSError as e:
                logger.warning("Error cleaning up socket file: %s", e)

        logger.info("Pricing Sidecar Worker stopped cleanly.")

    # -----------------------------------------------------------------------
    # Client Connection Handler & Request Dispatcher (Tasks 5.2 - 5.4)
    # -----------------------------------------------------------------------
    async def _handle_client(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        """Handle individual client socket sessions using streaming newline-delimited JSON."""
        try:
            while not reader.at_eof():
                line = await reader.readline()
                if not line:
                    break

                if len(line) > self.max_request_size:
                    error_resp = self._make_error_response(
                        error_code=ERROR_PAYLOAD_TOO_LARGE,
                        status_code=413,
                        message=f"Request size {len(line)} bytes exceeds limit {self.max_request_size} bytes.",
                    )
                    writer.write(self._encode_line(error_resp))
                    await writer.drain()
                    break

                # Process request with hard timeout (Task 5.3)
                try:
                    response_dict = await asyncio.wait_for(
                        self._process_request_line(line),
                        timeout=self.timeout_seconds,
                    )
                except TimeoutError:
                    response_dict = self._make_error_response(
                        error_code=ERROR_CALCULATOR_UNAVAILABLE,
                        status_code=503,
                        message=f"Pricing calculation exceeded hard timeout of {int(self.timeout_seconds * 1000)}ms.",
                    )
                except Exception as ex:
                    logger.exception("Unexpected error processing request: %s", ex)
                    response_dict = self._make_error_response(
                        error_code=ERROR_INTERNAL_ERROR,
                        status_code=500,
                        message=f"Internal sidecar error: {str(ex)}",
                    )

                writer.write(self._encode_line(response_dict))
                await writer.drain()
        except (ConnectionResetError, BrokenPipeError):
            pass
        finally:
            try:
                writer.close()
                await writer.wait_closed()
            except Exception:
                pass

    async def _process_request_line(self, line: bytes) -> dict[str, Any]:
        """Parse JSON request, route action, and return response dict."""
        try:
            req_str = line.decode("utf-8").strip()
            req_json = json.loads(req_str)
        except Exception as e:
            return self._make_error_response(
                error_code=ERROR_INVALID_REQUEST,
                status_code=400,
                message=f"Invalid JSON payload: {str(e)}",
            )

        if not isinstance(req_json, dict):
            return self._make_error_response(
                error_code=ERROR_INVALID_REQUEST,
                status_code=400,
                message="Request must be a JSON object.",
            )

        action = req_json.get("action", "")
        request_id = req_json.get("request_id")
        payload = req_json.get("payload", {})

        # -------------------------------------------------------------------
        # Action 1: Health Check (PING -> PONG) (Task 5.4)
        # -------------------------------------------------------------------
        if action in ("ping", "health", "health_check"):
            return {
                "success": True,
                "request_id": request_id,
                "data": {
                    "status": "ok",
                    "service": "pricing-worker",
                    "version": "v2.6",
                    "bound_address": self.bound_address,
                    "timestamp": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
                },
            }

        # -------------------------------------------------------------------
        # Action 2: Calculate Scenarios (FCS §5, §6)
        # -------------------------------------------------------------------
        if action == "calculate_scenarios":
            return await self._action_calculate_scenarios(payload, request_id)

        # -------------------------------------------------------------------
        # Action 3: Validate Pricing Results (FCS §9, TD-4.4 §3.3)
        # -------------------------------------------------------------------
        if action == "validate_pricing":
            return await self._action_validate_pricing(payload, request_id)

        # -------------------------------------------------------------------
        # Action 4: Rank Scenarios by Objective (FCS §7, TD-4.4 §4.1)
        # -------------------------------------------------------------------
        if action == "rank_scenarios":
            return await self._action_rank_scenarios(payload, request_id)

        # Unknown action
        return self._make_error_response(
            error_code=ERROR_INVALID_REQUEST,
            status_code=400,
            message=f"Unknown action: '{action}'.",
            request_id=request_id,
        )

    # -----------------------------------------------------------------------
    # Action Dispatcher Implementations
    # -----------------------------------------------------------------------
    async def _action_calculate_scenarios(self, payload: dict[str, Any], request_id: str | None) -> dict[str, Any]:
        """Execute calculation of all 3 canonical scenarios for PricingCalculationInput."""
        try:
            inp = PricingCalculationInput.model_validate(payload)
            assert_no_float(inp)

            # Compute standard scenarios
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

            # Validation & Ranking
            val_report = validate_pricing_results(scenarios, listed_price_vnd=inp.listed_price_vnd)
            rec_result = recommend_best_scenario(scenarios, objective=OptimizationObjective.MIN_NET_PRICE)

            output = create_pricing_calculation_output(
                input_data=inp,
                scenario_results=scenarios,
                recommended_result=rec_result,
                validation_report=val_report,
            )

            return {
                "success": True,
                "request_id": request_id,
                "data": _serialize_for_wire(output),
            }
        except FinancialSanityError as fe:
            return {
                "success": False,
                "request_id": request_id,
                "error": fe.to_envelope(),
            }
        except Exception as e:
            return self._make_error_response(
                error_code=ERROR_INVALID_REQUEST,
                status_code=400,
                message=f"Calculation input validation error: {str(e)}",
                request_id=request_id,
            )

    async def _action_validate_pricing(self, payload: dict[str, Any], request_id: str | None) -> dict[str, Any]:
        """Validate scenarios against 6 Sanity Checks."""
        try:
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
            return {
                "success": True,
                "request_id": request_id,
                "data": _serialize_for_wire(report),
            }
        except Exception as e:
            return self._make_error_response(
                error_code=ERROR_INVALID_REQUEST,
                status_code=400,
                message=f"Validation request error: {str(e)}",
                request_id=request_id,
            )

    async def _action_rank_scenarios(self, payload: dict[str, Any], request_id: str | None) -> dict[str, Any]:
        """Execute deterministic ranking across provided scenarios."""
        try:
            sc_list = [ScenarioCalculationResult.model_validate(s) for s in payload.get("scenarios", [])]
            obj_str = payload.get("objective", OptimizationObjective.MIN_NET_PRICE.value)
            objective = OptimizationObjective(obj_str)
            infeasible = payload.get("infeasible_scenarios", None)

            rec = recommend_best_scenario(
                scenarios=sc_list,
                objective=objective,
                infeasible_scenarios=infeasible,
            )
            return {
                "success": True,
                "request_id": request_id,
                "data": _serialize_for_wire(rec),
            }
        except Exception as e:
            return self._make_error_response(
                error_code=ERROR_INVALID_REQUEST,
                status_code=400,
                message=f"Ranking request error: {str(e)}",
                request_id=request_id,
            )

    # -----------------------------------------------------------------------
    # Utilities: RFC 9457 Error Generator & Byte Encoding
    # -----------------------------------------------------------------------
    def _make_error_response(
        self,
        error_code: str,
        status_code: int,
        message: str,
        request_id: str | None = None,
    ) -> dict[str, Any]:
        """Construct RFC 9457 compliant error dictionary."""
        return {
            "success": False,
            "request_id": request_id,
            "error": {
                "error_code": error_code,
                "status_code": status_code,
                "message": message,
            },
        }

    def _encode_line(self, data: dict[str, Any]) -> bytes:
        """Serialize dictionary to single-line UTF-8 JSON bytes ending with newline."""
        return json.dumps(data, separators=(",", ":"), ensure_ascii=False).encode("utf-8") + b"\n"
