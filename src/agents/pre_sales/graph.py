"""
Pre-Sales Advisory StateGraph Builder (C-09) — 11 nodes PS-01 → PS-11.
Owner: Phase 2 — Pre-Sales Advisory StateGraph
Thread format: presales:{tenant_id}:{session_id} | checkpoint_ns: PRE_SALES | TTL 1800s

Ranh giới Phase 2 (Zero-Trust Invariants):
- Không import src/agents/official_quote/
- Không gọi KMS Server Signer, không sinh chữ ký số Ed25519
- Không ghi transactional_outbox, không chuyển trạng thái APPROVED
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt

from src.agents.pre_sales.nodes import (
    node_await_handoff_consent,
    node_build_reference_plan,
    node_calculate_sidecar,
    node_collect_input,
    node_conflict_gate,
    node_extract_constraints,
    node_init,
    node_rank_objectives,
    node_resolve_policy,
    node_safe_abstain_or_handoff,
    node_validate_confirm_constraints,
)
from src.agents.pre_sales.state import PreSalesState
from src.contracts.errors import DomainError, ErrorCode
from src.orchestrator.checkpointer import CheckpointManager

GATE_CUSTOMER_INPUT = "WAITING_FOR_CUSTOMER_INPUT"
GATE_CONSTRAINT_CONFIRM = "WAITING_FOR_CONSTRAINT_CONFIRMATION"
GATE_HANDOFF_CONSENT = "WAITING_FOR_HANDOFF_CONSENT"


# ---------------------------------------------------------------------------
# Node wrappers: tích hợp interrupt() HITL vào các gate node (PS-02/04/10)
# ---------------------------------------------------------------------------

def ps02_collect_input(state: PreSalesState) -> dict[str, Any]:
    """
    PS-02 với interrupt WAITING_FOR_CUSTOMER_INPUT.
    Anti-deadlock: nếu node vẫn còn thiếu thông tin sau khi xử lý tin nhắn,
    xóa `last_customer_message` để lần lặp sau trigger interrupt() thay vì lặp vô hạn.
    """
    gate = state.get("_interrupt_gate")
    has_message = bool(state.get("last_customer_message"))

    if gate == GATE_CUSTOMER_INPUT and not has_message:
        resumed = interrupt(GATE_CUSTOMER_INPUT)
        message = ""
        if isinstance(resumed, dict):
            message = str(resumed.get("message", "") or "")
        elif isinstance(resumed, str):
            message = resumed
        result = node_collect_input(
            {**state, "last_customer_message": message, "_interrupt_gate": None}
        )
        result["last_customer_message"] = message
    else:
        result = node_collect_input(state)

    if result.get("_interrupt_gate") == GATE_CUSTOMER_INPUT:
        result = {**result, "last_customer_message": ""}
    return result


def ps04_validate_confirm(state: PreSalesState) -> dict[str, Any]:
    """
    PS-04 với interrupt WAITING_FOR_CONSTRAINT_CONFIRMATION.
    Anti-deadlock: nếu node yêu cầu xác nhận lại (revised), xóa
    `constraint_confirmation` cũ để lần lặp sau trigger interrupt() mới.
    """
    gate = state.get("_interrupt_gate")
    confirmation = state.get("constraint_confirmation")

    if gate == GATE_CONSTRAINT_CONFIRM and not confirmation:
        resumed = interrupt(GATE_CONSTRAINT_CONFIRM)
        payload = resumed if isinstance(resumed, dict) else {}
        result = node_validate_confirm_constraints(
            {**state, "constraint_confirmation": payload, "_interrupt_gate": None}
        )
    else:
        result = node_validate_confirm_constraints(state)

    if result.get("_interrupt_gate") == GATE_CONSTRAINT_CONFIRM:
        result = {**result, "constraint_confirmation": None}
    return result


def ps10_await_consent(state: PreSalesState) -> dict[str, Any]:
    """PS-10 với interrupt WAITING_FOR_HANDOFF_CONSENT."""
    gate = state.get("_interrupt_gate")
    consent = state.get("handoff_consent")

    if gate == GATE_HANDOFF_CONSENT and not consent:
        resumed = interrupt(GATE_HANDOFF_CONSENT)
        payload = resumed if isinstance(resumed, dict) else {}
        state = {**state, "handoff_consent": payload, "_interrupt_gate": None}
        return {**node_await_handoff_consent(state), "handoff_consent": payload}

    return node_await_handoff_consent(state)


# ---------------------------------------------------------------------------
# Routing
# ---------------------------------------------------------------------------

def route_after_collect(state: PreSalesState) -> str:
    """Sau PS-02: đủ thông tin → PS-03; chưa đủ → tự ngắt chờ tin nhắn tiếp."""
    if state.get("_interrupt_gate") == GATE_CUSTOMER_INPUT:
        return "collect_input"  # self-loop: node sẽ interrupt ngay lần chạy này
    return "extract_constraints"


def route_after_confirm(state: PreSalesState) -> str:
    """Sau PS-04: xác nhận xong → PS-05; cần điều chỉnh → quay lại chờ xác nhận."""
    if state.get("_interrupt_gate") == GATE_CONSTRAINT_CONFIRM:
        return "validate_confirm_constraints"  # self-loop: interrupt & chờ resume
    return "resolve_policy"


def route_after_handoff_gate(state: PreSalesState) -> str:
    """Sau PS-10: consent xử lý xong → PS-11; chưa có consent → interrupt chờ."""
    if state.get("_interrupt_gate") == GATE_HANDOFF_CONSENT:
        return "await_handoff_consent"  # self-loop
    return "safe_abstain_or_handoff"


def build_pre_sales_graph(checkpointer: Any | None = None):
    """
    Dựng và compile đồ thị 11 nodes PS-01 → PS-11 với checkpointer.
    `checkpointer` nên là MemorySaver (test/dev) hoặc AsyncPostgresSaver (prod).
    """
    builder = StateGraph(PreSalesState)

    builder.add_node("init", node_init)
    builder.add_node("collect_input", ps02_collect_input)
    builder.add_node("extract_constraints", node_extract_constraints)
    builder.add_node("validate_confirm_constraints", ps04_validate_confirm)
    builder.add_node("resolve_policy", node_resolve_policy)
    builder.add_node("conflict_gate", node_conflict_gate)
    builder.add_node("calculate_sidecar", node_calculate_sidecar)
    builder.add_node("rank_objectives", node_rank_objectives)
    builder.add_node("build_reference_plan", node_build_reference_plan)
    builder.add_node("await_handoff_consent", ps10_await_consent)
    builder.add_node("safe_abstain_or_handoff", node_safe_abstain_or_handoff)

    builder.add_edge(START, "init")
    builder.add_edge("init", "collect_input")
    builder.add_conditional_edges(
        "collect_input", route_after_collect, ["collect_input", "extract_constraints"]
    )
    builder.add_edge("extract_constraints", "validate_confirm_constraints")
    builder.add_conditional_edges(
        "validate_confirm_constraints",
        route_after_confirm,
        ["validate_confirm_constraints", "resolve_policy"],
    )
    builder.add_edge("resolve_policy", "conflict_gate")
    builder.add_edge("conflict_gate", "calculate_sidecar")
    builder.add_edge("calculate_sidecar", "rank_objectives")
    builder.add_edge("rank_objectives", "build_reference_plan")
    builder.add_edge("build_reference_plan", "await_handoff_consent")
    builder.add_conditional_edges(
        "await_handoff_consent",
        route_after_handoff_gate,
        ["await_handoff_consent", "safe_abstain_or_handoff"],
    )
    builder.add_edge("safe_abstain_or_handoff", END)

    return builder.compile(checkpointer=checkpointer)


# ---------------------------------------------------------------------------
# Session Runner — API điều khiển phiên cho endpoints & tests
# ---------------------------------------------------------------------------

class PreSalesSessionRunner:
    """Điều khiển vòng đời phiên Pre-Sales trên 3 điểm ngắt HITL."""

    def __init__(self, checkpointer: Any | None = None) -> None:
        self.checkpointer = checkpointer or CheckpointManager().get_memory_checkpointer()
        self.graph = build_pre_sales_graph(self.checkpointer)

    @staticmethod
    def build_config(tenant_id: str, session_id: str) -> dict[str, Any]:
        return CheckpointManager.build_thread_config(
            namespace="PRE_SALES", tenant_id=tenant_id, entity_id=session_id
        )

    @staticmethod
    def is_expired(state: PreSalesState) -> bool:
        expires_at = state.get("expires_at")
        if not expires_at:
            return False
        try:
            return datetime.fromisoformat(str(expires_at)) < datetime.now(UTC)
        except ValueError:
            return False

    async def _paused_state(self, config: dict[str, Any]) -> PreSalesState | None:
        snapshot = await self.graph.aget_state(config)
        if any(t.interrupts for t in snapshot.tasks):
            return dict(snapshot.values)
        return None

    async def start_session(
        self,
        tenant_id: str,
        session_id: str,
        initial_message: str | None = None,
        initial_constraints: dict[str, Any] | None = None,
        transaction_date: str | None = None,
    ) -> PreSalesState:
        """PS-01: khởi tạo phiên. Nếu có lời nhắn đầu vào → chạy tiếp PS-02."""
        initial: PreSalesState = {
            "tenant_id": tenant_id,
            "session_id": session_id,
            "last_customer_message": initial_message or "",
            "customer_constraints": initial_constraints,
            "transaction_date": transaction_date or "",
        }
        config = self.build_config(tenant_id, session_id)
        await self.graph.ainvoke(initial, config=config)
        paused = await self._paused_state(config)
        if paused:
            return paused
        snapshot = await self.graph.aget_state(config)
        return dict(snapshot.values)

    async def submit_message(self, tenant_id: str, session_id: str, message: str) -> PreSalesState:
        """Resume tại interrupt WAITING_FOR_CUSTOMER_INPUT bằng tin nhắn mới.

        Chỉ chấp nhận khi phiên đang pause ĐÚNG tại gate chờ tin nhắn — tránh
        tiêm resume payload vào interrupt sai (tin nhắn bị nuốt im lặng).
        """
        config = self.build_config(tenant_id, session_id)
        paused = await self._paused_state(config)
        if paused is None:
            raise DomainError(
                ErrorCode.INVALID_STATE_TRANSITION,
                "Phiên không đang chờ tin nhắn của khách hàng.",
            )
        if paused.get("_interrupt_gate") != GATE_CUSTOMER_INPUT:
            raise DomainError(
                ErrorCode.INVALID_STATE_TRANSITION,
                f"Phiên đang chờ '{paused.get('_interrupt_gate')}' — "
                "không phải chờ tin nhắn. Hãy dùng đúng API cho gate đó.",
            )
        await self.graph.ainvoke(Command(resume={"message": message}), config=config)
        paused = await self._paused_state(config)
        if paused:
            return paused
        snapshot = await self.graph.aget_state(config)
        return dict(snapshot.values)

    async def confirm_constraints(
        self, tenant_id: str, session_id: str, confirmation: dict[str, Any]
    ) -> PreSalesState:
        """Resume tại interrupt WAITING_FOR_CONSTRAINT_CONFIRMATION (đúng gate mới nhận)."""
        config = self.build_config(tenant_id, session_id)
        paused = await self._paused_state(config)
        if paused is None or paused.get("_interrupt_gate") != GATE_CONSTRAINT_CONFIRM:
            raise DomainError(
                ErrorCode.INVALID_STATE_TRANSITION,
                "Phiên không đang chờ xác nhận ràng buộc "
                f"(hiện tại: {paused.get('_interrupt_gate') if paused else 'không pause'}).",
            )
        await self.graph.ainvoke(Command(resume=confirmation), config=config)
        paused = await self._paused_state(config)
        if paused:
            return paused
        snapshot = await self.graph.aget_state(config)
        return dict(snapshot.values)

    async def provide_consent(
        self, tenant_id: str, session_id: str, consent: dict[str, Any]
    ) -> PreSalesState:
        """Resume tại interrupt WAITING_FOR_HANDOFF_CONSENT (đúng gate mới nhận).

        Sau resume, phiên kết thúc tại PS-11.
        """
        config = self.build_config(tenant_id, session_id)
        paused = await self._paused_state(config)
        if paused is None or paused.get("_interrupt_gate") != GATE_HANDOFF_CONSENT:
            raise DomainError(
                ErrorCode.INVALID_STATE_TRANSITION,
                "Phiên không đang chờ đồng thuận handoff "
                f"(hiện tại: {paused.get('_interrupt_gate') if paused else 'không pause'}).",
            )
        await self.graph.ainvoke(Command(resume=consent), config=config)
        snapshot = await self.graph.aget_state(config)
        return dict(snapshot.values)
