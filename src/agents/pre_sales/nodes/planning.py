"""
Pre-Sales advisory nodes: PS-05 → PS-09 (Planning pipeline).
Owner: Phase 2 — Pre-Sales Advisory StateGraph (C-09)

Ranh giới (Zero-Trust Invariant #2, #3):
- Kết quả là BẢN ƯỚC TÍNH THAM KHẢO, watermark bắt buộc, KHÔNG phải báo giá chính thức.
- Tuyệt đối không gọi KMS Ed25519, không ghi outbox, không sinh chữ ký số.
"""

from __future__ import annotations

import hashlib
from typing import Any

from src.agents.pre_sales.state import PreSalesState
from src.contracts.errors import DomainError, ErrorCode
from src.contracts.pre_sales import CustomerConstraints

WATERMARK_TEXT = (
    "BẢN ƯỚC TÍNH THAM KHẢO TIỀN BÁN HÀNG - KHÔNG PHẢI BÁO GIÁ CHÍNH THỨC"
)


def node_resolve_policy(state: PreSalesState) -> dict[str, Any]:
    """
    PS-05 — Resolve Policy: chốt ngày giao dịch tham khảo và băm snapshot chính sách.
    Phase 2 dùng snapshot hash tổng hợp từ ràng buộc + ngày giao dịch; việc tra cứu
    pgvector/RAG thời gian thực thuộc Phase 3/4 (chỉ ĐỌC, không sửa contracts).
    """
    constraints = CustomerConstraints(**(state.get("customer_constraints") or {}))
    tx_date = state.get("transaction_date") or datetime_today_iso()

    snapshot_payload = {
        "project_id": constraints.project_id or "UNKNOWN",
        "unit_code": constraints.preferred_unit_code or "",
        "transaction_date": tx_date,
        "objective": constraints.objective.value,
    }
    snapshot_hash = hashlib.sha256(
        "|".join(str(v) for v in snapshot_payload.values()).encode("utf-8")
    ).hexdigest()

    return {
        "transaction_date": tx_date,
        "policy_snapshot_hash": snapshot_hash,
        "status": "CALCULATING" if state.get("status") != "CALCULATING" else state["status"],
        "_interrupt_gate": None,
    }


def node_conflict_gate(state: PreSalesState) -> dict[str, Any]:
    """
    PS-06 — Conflict Gate: phát hiện xung đột chính sách trước khi tính toán.
    Hiện tại chính sách Phase 2 mặc định hợp lệ (ELIGIBLE); nếu có xung đột
    được đánh dấu từ node trước, đặt cờ ABSTAIN cho PS-11 xử lý.
    """
    conflicts = list(state.get("policy_conflicts", []))
    if conflicts:
        return {
            "status": "ABSTAINED",
            "abstain_reason": "POLICY_CONFLICT_UNRESOLVED",
            "_interrupt_gate": None,
        }
    return {"policy_conflicts": [], "_interrupt_gate": None}


async def node_calculate_sidecar(state: PreSalesState) -> dict[str, Any]:
    """
    PS-07 — Calculate via Pricing Sidecar (async): gọi PricingClient (UDS hoặc
    fallback in-process Decimal 28). ĐÃ XÁC MINH: client có sẵn local fallback,
    không dựng sidecar riêng. Node async chuẩn LangGraph — không chặn event loop.
    """
    from src.contracts.pricing import PricingInput
    from src.services.pricing.client import PricingClient

    constraints = CustomerConstraints(**(state.get("customer_constraints") or {}))
    unit_code = constraints.preferred_unit_code or state.get("unit_code") or "BEV-STUDIO-01"

    pricing_input = PricingInput(
        project_id=constraints.project_id or "UNKNOWN-PROJECT",
        unit_code=unit_code,
        listed_price_before_tax_vnd=_default_listed_price(state),
        transaction_date=state.get("transaction_date") or datetime_today_iso(),
        own_funds_vnd=constraints.own_funds_vnd,
        monthly_capacity_vnd=constraints.monthly_capacity_vnd,
        objective=constraints.objective,
        execution_context="PRE_SALES",
        policy_snapshot_hash=state.get("policy_snapshot_hash"),
    )

    client = PricingClient(force_mock=state.get("tenant_id") == "TEST")
    result = await client.calculate(pricing_input)

    scenarios = {code: detail.model_dump(mode="json") for code, detail in result.scenarios.items()}
    return {
        "pricing_result": result.model_dump(mode="json"),
        "scenarios": scenarios,
        "policy_conflicts": [] if result.sanity_passed else list(result.sanity_errors),
        "_interrupt_gate": None,
    }


def node_rank_objectives(state: PreSalesState) -> dict[str, Any]:
    """
    PS-08 — Rank theo 6 Objective (ADR-021): đọc `recommended_scenario_code`
    do PricingClient xếp hạng tất định theo objective của khách.
    """
    result = state.get("pricing_result") or {}
    recommended = result.get("recommended_scenario_code")
    if not recommended:
        raise DomainError(
            ErrorCode.FINANCIAL_SANITY_FAILED,
            "Không xác định được kịch bản tối ưu từ kết quả tính toán.",
        )
    scenarios: dict[str, dict[str, Any]] = state.get("scenarios", {})
    detail = scenarios.get(recommended)
    return {
        "recommended_scenario_code": recommended,
        "recommended_scenario_detail": detail,
        "status": "READY" if detail else "CALCULATION_FAILED",
    }


def node_build_reference_plan(state: PreSalesState) -> dict[str, Any]:
    """
    PS-09 — Build Reference Plan (pure node): đóng gói bản ước tính tham khảo +
    watermark. KHÔNG ký số, KHÔNG ghi outbox, KHÔNG đụng DB (persistence do
    tầng graph helper/API thực hiện). Sinh PDF best-effort, không chặn luồng.
    """
    from uuid import uuid4

    result = state.get("pricing_result") or {}
    if not result:
        raise DomainError(
            ErrorCode.FINANCIAL_SANITY_FAILED,
            "Thiếu PricingResult để dựng bản ước tính tham khảo.",
        )

    plan_id = f"PLAN-{uuid4().hex[:12].upper()}"
    unit_code = state.get("unit_code") or ""
    watermark = WATERMARK_TEXT

    # Sinh PDF tham khảo (không ký số) — best-effort
    pdf_path: str | None = None
    try:
        from src.worker.watermark_pdf import generate_reference_pdf

        pdf_path = generate_reference_pdf(
            plan_id=plan_id,
            unit_code=unit_code,
            scenarios=state.get("scenarios", {}),
            recommended_code=state.get("recommended_scenario_code") or "",
            watermark_text=watermark,
        )
    except Exception:
        pdf_path = None

    recommended = state.get("recommended_scenario_detail") or {}
    total_price = (recommended.get("total_contract_price_vnd", 0) or 0)
    message = (
        f"Dưới đây là bản ước tính tham khảo cho căn {unit_code or 'đang tư vấn'}.\n"
        f"• Phương án đề xuất: {state.get('recommended_scenario_code')}\n"
        f"• Tổng giá trị hợp đồng (gồm VAT + KPBT): "
        f"{total_price:,} VNĐ".replace(",", ".")
    )

    return {
        "plan_id": plan_id,
        "watermark_text": watermark,
        "pdf_path": pdf_path,
        "status": "PLAN_READY",
        "agent_message": message,
        "_interrupt_gate": "WAITING_FOR_HANDOFF_CONSENT",
    }


def _default_listed_price(state: PreSalesState) -> int:
    """Giá niêm yết tham khảo theo loại căn khi chưa có catalog giá (Phase 3)."""
    unit_type = (state.get("customer_constraints") or {}).get("unit_type") or "STUDIO"
    return {
        "STUDIO": 2_500_000_000,
        "1BR": 3_500_000_000,
        "2BR": 4_800_000_000,
        "3BR": 6_500_000_000,
    }.get(str(unit_type).upper(), 2_500_000_000)


def datetime_today_iso() -> str:
    """Ngày giao dịch tham khảo = hôm nay (UTC) dạng YYYY-MM-DD."""
    from datetime import UTC, datetime

    return datetime.now(UTC).strftime("%Y-%m-%d")
