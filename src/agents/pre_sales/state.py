"""
PreSalesState TypedDict (C-09) — biến trạng thái phiên tư vấn Pre-Sales.
Owner: Phase 2 — Pre-Sales Advisory StateGraph
Thread format: presales:{tenant_id}:{session_id} | checkpoint_ns: PRE_SALES | TTL 1800s
"""

from __future__ import annotations

from typing import Any, TypedDict

from src.contracts.enums import PreSalesSessionStatus
from src.contracts.pricing import ScenarioDetail


class PreSalesState(TypedDict, total=False):
    """Toàn bộ biến trạng thái phiên chat Pre-Sales (PS-01 → PS-11)."""

    # ---- Identity & lifecycle ----
    tenant_id: str
    session_id: str
    status: str  # PreSalesSessionStatus.value
    error: str | None
    created_at: str | None  # ISO 8601 UTC
    expires_at: str | None  # ISO 8601 UTC (created_at + TTL 1800s)

    # ---- PS-01/PS-02: Discovery & input collector ----
    last_customer_message: str
    collected_fields: list[str]  # các trường ràng buộc đã thu thập xong

    # ---- PS-03/PS-04: Constraint extraction & confirmation gate ----
    customer_constraints: dict[str, Any] | None  # CustomerConstraints.model_dump()
    constraint_confirmation: dict[str, Any] | None  # ConstraintConfirmationRequest
    constraints_confirmed: bool

    # ---- PS-05/PS-06: Policy resolution & conflict gate ----
    transaction_date: str  # YYYY-MM-DD (ngày giao dịch tham khảo)
    policy_snapshot_hash: str | None
    policy_conflicts: list[str]

    # ---- PS-07/PS-08: Pricing sidecar calculation & ranking ----
    pricing_result: dict[str, Any] | None  # PricingResult.model_dump()
    scenarios: dict[str, dict[str, Any]]  # code -> ScenarioDetail.model_dump()

    # ---- PS-09: Reference plan build ----
    plan_id: str | None
    recommended_scenario_code: str | None  # ScenarioCode.value
    recommended_scenario_detail: dict[str, Any] | None  # ScenarioDetail.model_dump()
    unit_code: str | None
    watermark_text: str
    pdf_path: str | None
    agent_message: str | None

    # ---- PS-10/PS-11: Handoff consent & safe abstain ----
    dossier_id: str | None
    decision: str | None  # HANDOFF_CREATE_DOSSIER | ABSTAIN
    dossier_payload: dict[str, Any] | None  # dữ liệu persist LeadDossier + Consent
    handoff_consent: dict[str, Any] | None  # HandoffConsentRequest
    abstain_reason: str | None

    # ---- Internal helpers ----
    _interrupt_gate: str | None  # tên điểm ngắt HITL đang chờ


def session_status_enum(state: PreSalesState) -> PreSalesSessionStatus:
    """Trích xuất trạng thái phiên dạng enum an toàn."""
    return PreSalesSessionStatus(state.get("status", PreSalesSessionStatus.ACTIVE.value))


def scenario_detail_from_state(state: PreSalesState, code: str) -> ScenarioDetail | None:
    """Tái tạo ScenarioDetail từ state mà không import node."""
    raw = state.get("scenarios", {}).get(code)
    return ScenarioDetail(**raw) if raw else None
