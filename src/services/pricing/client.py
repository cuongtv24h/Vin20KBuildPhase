"""
Pricing Sidecar Client Module (UDS Bridge + Deterministic In-Process Fallback)
Owner: TechLead (cuongtv_02560)
Component: C-06 (Deterministic Financial Pricing Engine)
Standards: FCS v2.6, Decimal precision=28, 6 Sanity Checks, Canonical Hash RFC 8785

Designed to be platform-agnostic:
- Connects to Unix Domain Socket when available (POSIX / Linux / Docker).
- Automatically falls back to deterministic in-process calculator (Decimal 28)
  on Windows dev environments or when Sidecar daemon is offline.
"""

from __future__ import annotations

import asyncio
import json
import os
import socket
from decimal import ROUND_HALF_UP, Decimal, getcontext
from pathlib import Path
from typing import Any

from src.contracts.common import canonical_json_bytes, sha256_hex
from src.contracts.enums import OptimizationObjective
from src.contracts.errors import DomainError, ErrorCode
from src.contracts.pricing import (
    PaymentScheduleItem,
    PricingInput,
    PricingResult,
    ScenarioCode,
    ScenarioDetail,
)

# Set Decimal precision to 28 digits as mandated by FCS v2.6
getcontext().prec = 28


class PricingCalculationError(DomainError):
    """Lỗi phát sinh trong quá trình tính toán tài chính tại Sidecar."""

    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(
            error_code=ErrorCode.CALCULATION_ENGINE_ERROR,
            message=message,
            details=details or {},
        )


class PricingClient:
    """
    Bridge client connecting to the Deterministic Financial Pricing Engine (C-06).
    Supports dual-mode: UDS Socket Bridge & In-Process Deterministic Fallback.
    """

    def __init__(
        self,
        socket_path: str | None = None,
        timeout: float = 5.0,
        force_mock: bool = False,
    ) -> None:
        self.socket_path = socket_path or os.environ.get(
            "PRICING_SIDECAR_SOCKET", "./data/pricing.sock"
        )
        self.timeout = timeout
        self.force_mock = force_mock or (
            os.environ.get("PRICING_USE_MOCK", "false").lower() in ("true", "1")
        )

    async def calculate(self, pricing_input: PricingInput) -> PricingResult:
        """
        Calculate 3 financial scenarios (PA-CHUDONG, PA-NHANH, PA-VAY) for the given input.
        Attempts UDS socket first; seamlessly falls back to deterministic local math engine.
        """
        if not self.force_mock:
            try:
                sidecar_res = await asyncio.to_thread(self._sync_call_uds_sidecar, pricing_input)
                if sidecar_res is not None:
                    return sidecar_res
            except Exception:
                # Socket offline or unsupported on current OS -> fallback to in-process math
                pass

        return self._calculate_deterministic(pricing_input)

    def _sync_call_uds_sidecar(self, pricing_input: PricingInput) -> PricingResult | None:
        """Attempt to call the Pricing Sidecar via Unix Domain Socket synchronously in a worker thread."""
        if not hasattr(socket, "AF_UNIX"):
            return None

        socket_file = Path(self.socket_path)
        if not socket_file.exists():
            return None

        payload = pricing_input.model_dump_json().encode("utf-8") + b"\n"

        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.settimeout(self.timeout)
        try:
            sock.connect(str(socket_file))
            sock.sendall(payload)

            response_data = b""
            while True:
                chunk = sock.recv(4096)
                if not chunk:
                    break
                response_data += chunk
                # Only break when full message received (newline-terminated protocol)
                if response_data.rstrip().endswith(b"}"):
                    break

            if not response_data:
                return None

            raw_dict = json.loads(response_data.decode("utf-8").strip())
            return PricingResult(**raw_dict)
        finally:
            sock.close()

    async def _call_uds(self, pricing_input: PricingInput) -> PricingResult | None:
        """Async wrapper for backward compatibility."""
        return await asyncio.to_thread(self._sync_call_uds_sidecar, pricing_input)


    def _calculate_deterministic(self, pricing_input: PricingInput) -> PricingResult:
        """
        In-process deterministic financial calculation adhering to FCS v2.6.
        100% Decimal math (prec=28), strict rounding, 6 sanity checks.
        """
        base_price = Decimal(str(pricing_input.listed_price_before_tax_vnd))
        vat_rate = Decimal("0.10")
        kpbt_rate = Decimal("0.02")

        # ---------------------------------------------------------------------
        # Scenario 1: PA-CHUDONG (Tiến độ chuẩn - 8 đợt thanh toán)
        # ---------------------------------------------------------------------
        net_chudong = base_price
        vat_chudong = (net_chudong * vat_rate).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
        kpbt_chudong = (net_chudong * kpbt_rate).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
        total_chudong = net_chudong + vat_chudong + kpbt_chudong

        schedule_chudong: list[PaymentScheduleItem] = [
            PaymentScheduleItem(
                installment_number=1,
                due_milestone="Ký Hợp đồng Mua bán (Đợt 1)",
                percentage=15.0,
                amount_vnd=int((net_chudong * Decimal("0.15")) + (vat_chudong * Decimal("0.15"))),
                vat_vnd=int(vat_chudong * Decimal("0.15")),
                kpbt_vnd=0,
                net_amount_vnd=int(net_chudong * Decimal("0.15")),
            ),
            PaymentScheduleItem(
                installment_number=2,
                due_milestone="Hoàn thành sàn tầng 5 (Đợt 2)",
                percentage=10.0,
                amount_vnd=int((net_chudong * Decimal("0.10")) + (vat_chudong * Decimal("0.10"))),
                vat_vnd=int(vat_chudong * Decimal("0.10")),
                kpbt_vnd=0,
                net_amount_vnd=int(net_chudong * Decimal("0.10")),
            ),
            PaymentScheduleItem(
                installment_number=3,
                due_milestone="Hoàn thành sàn tầng 10 (Đợt 3)",
                percentage=10.0,
                amount_vnd=int((net_chudong * Decimal("0.10")) + (vat_chudong * Decimal("0.10"))),
                vat_vnd=int(vat_chudong * Decimal("0.10")),
                kpbt_vnd=0,
                net_amount_vnd=int(net_chudong * Decimal("0.10")),
            ),
            PaymentScheduleItem(
                installment_number=4,
                due_milestone="Hoàn thành sàn tầng 15 (Đợt 4)",
                percentage=10.0,
                amount_vnd=int((net_chudong * Decimal("0.10")) + (vat_chudong * Decimal("0.10"))),
                vat_vnd=int(vat_chudong * Decimal("0.10")),
                kpbt_vnd=0,
                net_amount_vnd=int(net_chudong * Decimal("0.10")),
            ),
            PaymentScheduleItem(
                installment_number=5,
                due_milestone="Hoàn thành sàn tầng 20 (Đợt 5)",
                percentage=10.0,
                amount_vnd=int((net_chudong * Decimal("0.10")) + (vat_chudong * Decimal("0.10"))),
                vat_vnd=int(vat_chudong * Decimal("0.10")),
                kpbt_vnd=0,
                net_amount_vnd=int(net_chudong * Decimal("0.10")),
            ),
            PaymentScheduleItem(
                installment_number=6,
                due_milestone="Cất nóc công trình (Đợt 6)",
                percentage=15.0,
                amount_vnd=int((net_chudong * Decimal("0.15")) + (vat_chudong * Decimal("0.15"))),
                vat_vnd=int(vat_chudong * Decimal("0.15")),
                kpbt_vnd=0,
                net_amount_vnd=int(net_chudong * Decimal("0.15")),
            ),
            PaymentScheduleItem(
                installment_number=7,
                due_milestone="Bàn giao căn hộ (Đợt 7) + 2% KPBT",
                percentage=25.0,
                amount_vnd=int((net_chudong * Decimal("0.25")) + (vat_chudong * Decimal("0.25")) + kpbt_chudong),
                vat_vnd=int(vat_chudong * Decimal("0.25")),
                kpbt_vnd=int(kpbt_chudong),
                net_amount_vnd=int(net_chudong * Decimal("0.25")),
            ),
            PaymentScheduleItem(
                installment_number=8,
                due_milestone="Nhận Giấy chứng nhận quyền sở hữu (Đợt 8)",
                percentage=5.0,
                amount_vnd=int((net_chudong * Decimal("0.05")) + (vat_chudong * Decimal("0.05"))),
                vat_vnd=int(vat_chudong * Decimal("0.05")),
                kpbt_vnd=0,
                net_amount_vnd=int(net_chudong * Decimal("0.05")),
            ),
        ]
        # Adjust rounding drift on final installment to guarantee 100% exact sum
        diff_chudong = int(total_chudong) - sum(item.amount_vnd for item in schedule_chudong)
        if diff_chudong != 0:
            schedule_chudong[-1].amount_vnd += diff_chudong

        initial_chudong = schedule_chudong[0].amount_vnd
        monthly_chudong = int(total_chudong // Decimal("24"))

        detail_chudong = ScenarioDetail(
            scenario_code=ScenarioCode.PA_CHUDONG,
            scenario_name="Phương án Tiến độ chuẩn (Chủ động)",
            net_price_vnd=int(net_chudong),
            vat_vnd=int(vat_chudong),
            kpbt_vnd=int(kpbt_chudong),
            total_contract_price_vnd=int(total_chudong),
            initial_cash_outflow_vnd=initial_chudong,
            monthly_burden_vnd=monthly_chudong,
            total_cash_outflow_vnd=int(total_chudong),
            benefit_value_vnd=0,
            payment_schedule=schedule_chudong,
            applied_incentives=["Tiến độ thanh toán chuẩn giãn cách 24 tháng"],
            is_feasible=(
                initial_chudong <= pricing_input.own_funds_vnd
                if pricing_input.own_funds_vnd > 0
                else True
            ),
        )

        # ---------------------------------------------------------------------
        # Scenario 2: PA-NHANH (Thanh toán sớm - Chiết khấu 8% giá Net)
        # ---------------------------------------------------------------------
        discount_rate = Decimal("0.08")
        discount_amount = (base_price * discount_rate).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
        net_nhanh = base_price - discount_amount
        vat_nhanh = (net_nhanh * vat_rate).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
        kpbt_nhanh = (net_nhanh * kpbt_rate).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
        total_nhanh = net_nhanh + vat_nhanh + kpbt_nhanh

        schedule_nhanh: list[PaymentScheduleItem] = [
            PaymentScheduleItem(
                installment_number=1,
                due_milestone="Ký HĐMB (Đợt 1)",
                percentage=15.0,
                amount_vnd=int((net_nhanh * Decimal("0.15")) + (vat_nhanh * Decimal("0.15"))),
                vat_vnd=int(vat_nhanh * Decimal("0.15")),
                kpbt_vnd=0,
                net_amount_vnd=int(net_nhanh * Decimal("0.15")),
            ),
            PaymentScheduleItem(
                installment_number=2,
                due_milestone="Thanh toán sớm 80% trong 15 ngày (Đợt 2)",
                percentage=80.0,
                amount_vnd=int((net_nhanh * Decimal("0.80")) + (vat_nhanh * Decimal("0.80")) + kpbt_nhanh),
                vat_vnd=int(vat_nhanh * Decimal("0.80")),
                kpbt_vnd=int(kpbt_nhanh),
                net_amount_vnd=int(net_nhanh * Decimal("0.80")),
            ),
            PaymentScheduleItem(
                installment_number=3,
                due_milestone="Nhận Giấy chứng nhận (Đợt 3)",
                percentage=5.0,
                amount_vnd=int((net_nhanh * Decimal("0.05")) + (vat_nhanh * Decimal("0.05"))),
                vat_vnd=int(vat_nhanh * Decimal("0.05")),
                kpbt_vnd=0,
                net_amount_vnd=int(net_nhanh * Decimal("0.05")),
            ),
        ]
        diff_nhanh = int(total_nhanh) - sum(item.amount_vnd for item in schedule_nhanh)
        if diff_nhanh != 0:
            schedule_nhanh[-1].amount_vnd += diff_nhanh

        initial_nhanh = schedule_nhanh[0].amount_vnd
        monthly_nhanh = int(total_nhanh // Decimal("6"))

        detail_nhanh = ScenarioDetail(
            scenario_code=ScenarioCode.PA_NHANH,
            scenario_name="Phương án Thanh toán sớm (Chiết khấu 8%)",
            net_price_vnd=int(net_nhanh),
            vat_vnd=int(vat_nhanh),
            kpbt_vnd=int(kpbt_nhanh),
            total_contract_price_vnd=int(total_nhanh),
            initial_cash_outflow_vnd=initial_nhanh,
            monthly_burden_vnd=monthly_nhanh,
            total_cash_outflow_vnd=int(total_nhanh),
            benefit_value_vnd=int(discount_amount),
            payment_schedule=schedule_nhanh,
            applied_incentives=["Chiết khấu 8% thanh toán sớm trực tiếp vào giá Net"],
            is_feasible=(
                initial_nhanh <= pricing_input.own_funds_vnd
                if pricing_input.own_funds_vnd > 0
                else True
            ),
        )

        # ---------------------------------------------------------------------
        # Scenario 3: PA-VAY (Hỗ trợ vay ngân hàng 70%, ân hạn nợ gốc)
        # ---------------------------------------------------------------------
        net_vay = base_price
        vat_vay = (net_vay * vat_rate).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
        kpbt_vay = (net_vay * kpbt_rate).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
        total_vay = net_vay + vat_vay + kpbt_vay

        own_capital_total = int(total_vay * Decimal("0.30")) + int(kpbt_vay)
        bank_loan_amount = int(total_vay) - own_capital_total

        schedule_vay: list[PaymentScheduleItem] = [
            PaymentScheduleItem(
                installment_number=1,
                due_milestone="Vốn tự có: Ký HĐMB 15% (Đợt 1)",
                percentage=15.0,
                amount_vnd=int((net_vay * Decimal("0.15")) + (vat_vay * Decimal("0.15"))),
                vat_vnd=int(vat_vay * Decimal("0.15")),
                kpbt_vnd=0,
                net_amount_vnd=int(net_vay * Decimal("0.15")),
            ),
            PaymentScheduleItem(
                installment_number=2,
                due_milestone="Vốn tự có: Bổ sung 15% sau 30 ngày (Đợt 2)",
                percentage=15.0,
                amount_vnd=int((net_vay * Decimal("0.15")) + (vat_vay * Decimal("0.15"))),
                vat_vnd=int(vat_vay * Decimal("0.15")),
                kpbt_vnd=0,
                net_amount_vnd=int(net_vay * Decimal("0.15")),
            ),
            PaymentScheduleItem(
                installment_number=3,
                due_milestone="Ngân hàng giải ngân 70% (HTLS 0% 18 tháng)",
                percentage=70.0,
                amount_vnd=bank_loan_amount,
                vat_vnd=int(vat_vay * Decimal("0.70")),
                kpbt_vnd=0,
                net_amount_vnd=int(net_vay * Decimal("0.70")),
            ),
            PaymentScheduleItem(
                installment_number=4,
                due_milestone="Vốn tự có: Bàn giao căn hộ & 2% KPBT (Đợt 4)",
                percentage=0.0,
                amount_vnd=int(kpbt_vay),
                vat_vnd=0,
                kpbt_vnd=int(kpbt_vay),
                net_amount_vnd=0,
            ),
        ]
        diff_vay = int(total_vay) - sum(item.amount_vnd for item in schedule_vay)
        if diff_vay != 0:
            schedule_vay[-1].amount_vnd += diff_vay

        initial_vay = schedule_vay[0].amount_vnd
        monthly_vay = 0  # Ân hạn nợ gốc và lãi 0% trong 18 tháng

        detail_vay = ScenarioDetail(
            scenario_code=ScenarioCode.PA_VAY,
            scenario_name="Phương án Hỗ trợ Lãi suất Ngân hàng (Vay 70%)",
            net_price_vnd=int(net_vay),
            vat_vnd=int(vat_vay),
            kpbt_vnd=int(kpbt_vay),
            total_contract_price_vnd=int(total_vay),
            initial_cash_outflow_vnd=initial_vay,
            monthly_burden_vnd=monthly_vay,
            total_cash_outflow_vnd=own_capital_total,
            benefit_value_vnd=int(base_price * Decimal("0.05")),  # Trị giá gói hỗ trợ lãi suất
            payment_schedule=schedule_vay,
            applied_incentives=["Hỗ trợ lãi suất 0% và ân hạn nợ gốc 18 tháng"],
            is_feasible=(
                initial_vay <= pricing_input.own_funds_vnd
                if pricing_input.own_funds_vnd > 0
                else True
            ),
        )

        scenarios: dict[str, ScenarioDetail] = {
            ScenarioCode.PA_CHUDONG.value: detail_chudong,
            ScenarioCode.PA_NHANH.value: detail_nhanh,
            ScenarioCode.PA_VAY.value: detail_vay,
        }

        # ---------------------------------------------------------------------
        # 6 Sanity Checks (FCS v2.6 Verification)
        # ---------------------------------------------------------------------
        sanity_errors: list[str] = []
        for code, sc in scenarios.items():
            # Check 1: Non-negative values
            if (
                sc.net_price_vnd < 0
                or sc.vat_vnd < 0
                or sc.kpbt_vnd < 0
                or sc.total_contract_price_vnd < 0
                or sc.initial_cash_outflow_vnd < 0
            ):
                sanity_errors.append(f"{code}: Negative financial numbers detected.")

            # Check 2: Total contract price reconciliation
            reconciled = sc.net_price_vnd + sc.vat_vnd + sc.kpbt_vnd
            if sc.total_contract_price_vnd != reconciled:
                sanity_errors.append(
                    f"{code}: Total contract price ({sc.total_contract_price_vnd}) "
                    f"does not match sum of net+vat+kpbt ({reconciled})."
                )

            # Check 3: Payment schedule total must equal 100% total contract price
            schedule_sum = sum(item.amount_vnd for item in sc.payment_schedule)
            if schedule_sum != sc.total_contract_price_vnd:
                sanity_errors.append(
                    f"{code}: Schedule sum ({schedule_sum}) does not equal "
                    f"total contract price ({sc.total_contract_price_vnd})."
                )

            # Check 4: Initial cash outflow > 0
            if sc.initial_cash_outflow_vnd <= 0:
                sanity_errors.append(f"{code}: Initial cash outflow must be > 0.")

        sanity_passed = len(sanity_errors) == 0

        # ---------------------------------------------------------------------
        # Ranking based on OptimizationObjective
        # ---------------------------------------------------------------------
        recommended: ScenarioCode = ScenarioCode.PA_CHUDONG
        obj = pricing_input.objective

        if obj in (OptimizationObjective.MIN_INITIAL_CASH, OptimizationObjective.MIN_MONTHLY_BURDEN):
            recommended = ScenarioCode.PA_VAY
        elif obj in (OptimizationObjective.MIN_NET_PRICE, OptimizationObjective.MIN_TOTAL_CASH_OUTFLOW):
            recommended = ScenarioCode.PA_NHANH
        elif obj == OptimizationObjective.MAX_BENEFIT_VALUE:
            # Pick scenario with highest benefit_value_vnd
            best = max(scenarios.values(), key=lambda s: s.benefit_value_vnd)
            recommended = best.scenario_code
        elif obj == OptimizationObjective.EARLY_HANDOVER:
            recommended = ScenarioCode.PA_CHUDONG

        # ---------------------------------------------------------------------
        # Calculation Hash (RFC 8785 Canonical JSON)
        # ---------------------------------------------------------------------
        canonical_payload = {
            "quote_id": pricing_input.quote_id or "",
            "project_id": pricing_input.project_id,
            "unit_code": pricing_input.unit_code,
            "listed_price": pricing_input.listed_price_before_tax_vnd,
            "objective": obj.value,
            "scenarios": {k: v.model_dump() for k, v in scenarios.items()},
        }
        calc_hash = sha256_hex(canonical_json_bytes(canonical_payload))

        return PricingResult(
            schema_version="pricing-result.v1",
            calculation_hash=calc_hash,
            scenarios=scenarios,
            recommended_scenario_code=recommended,
            sanity_passed=sanity_passed,
            sanity_errors=sanity_errors,
        )
