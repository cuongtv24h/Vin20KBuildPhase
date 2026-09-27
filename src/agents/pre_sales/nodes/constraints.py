"""
Pre-Sales advisory nodes: PS-03 (Extract Constraints) và PS-04 (Validate & Confirm interrupt).
Owner: Phase 2 — Pre-Sales Advisory StateGraph (C-09)
"""

from __future__ import annotations

from typing import Any

from pydantic import ValidationError

from src.agents.pre_sales.state import PreSalesState
from src.contracts.enums import SecurityEventType
from src.contracts.errors import DomainError, ErrorCode
from src.contracts.pre_sales import CustomerConstraints

CONFIRM_MESSAGE_TEMPLATE = (
    "Em xin xác nhận lại nhu cầu của anh/chị:\n"
    "• Vốn tự có: {own_funds}\n"
    "• Khả năng trả góp hàng tháng: {monthly}\n"
    "• Dự án quan tâm: {project}\n"
    "• Loại căn: {unit_type}\n"
    "Thông tin trên có chính xác không ạ? Anh/chị bấm 'Xác nhận' để em tính phương án tài chính."
)


def node_extract_constraints(state: PreSalesState) -> dict[str, Any]:
    """
    PS-03 — Extract: hợp nhất dữ liệu thô thành `CustomerConstraints` hợp lệ.
    Dữ liệu không hợp lệ bị loại bỏ an toàn (chưa tới ước tính), không bao giờ
    bị đẩy thẳng sang tính toán.
    """
    raw = dict(state.get("customer_constraints") or {})
    # Giữ lại những gì còn thiếu làm mặc định an toàn
    raw.setdefault("own_funds_vnd", 0)
    raw.setdefault("monthly_capacity_vnd", 0)

    try:
        constraints = CustomerConstraints(**raw)
    except ValidationError:
        # Rơi về bộ ràng buộc an toàn, đánh dấu cần hỏi lại
        constraints = CustomerConstraints()

    return {
        "customer_constraints": constraints.model_dump(mode="json"),
        "status": "WAITING_FOR_CONSTRAINT_CONFIRMATION",
        "_interrupt_gate": "WAITING_FOR_CONSTRAINT_CONFIRMATION",
        "agent_message": CONFIRM_MESSAGE_TEMPLATE.format(
            own_funds=f"{constraints.own_funds_vnd:,}".replace(",", "."),
            monthly=f"{constraints.monthly_capacity_vnd:,}".replace(",", "."),
            project=constraints.project_id or "Chưa xác định",
            unit_type=constraints.unit_type or "Chưa xác định",
        ),
    }


def node_validate_confirm_constraints(state: PreSalesState) -> dict[str, Any]:
    """
    PS-04 — Validate & Confirm (HITL interrupt gate).
    Chỉ tiếp tục khi khách xác nhận (`constraints_confirmed=True`).
    Nếu khách điều chỉnh (revised_constraints) -> hợp nhất và quay lại chờ xác nhận.
    """
    confirmation = state.get("constraint_confirmation") or {}

    if not confirmation.get("confirmed", False):
        revised = confirmation.get("revised_constraints")
        updated: dict[str, Any] = dict(state.get("customer_constraints") or {})
        if revised:
            try:
                parsed = CustomerConstraints(**revised)
                updated = parsed.model_dump(mode="json")
            except ValidationError:
                # Giữ nguyên ràng buộc cũ, xin khách nhập lại
                pass
        return {
            "customer_constraints": updated,
            "constraints_confirmed": False,
            "status": "WAITING_FOR_CONSTRAINT_CONFIRMATION",
            "_interrupt_gate": "WAITING_FOR_CONSTRAINT_CONFIRMATION",
            "agent_message": "Em xin phép xác nhận lại thông tin đã điều chỉnh nhé ạ.",
        }

    try:
        constraints = CustomerConstraints(**(state.get("customer_constraints") or {}))
    except ValidationError as exc:
        raise DomainError(
            ErrorCode.INPUT_VALIDATION_ERROR,
            "Ràng buộc khách hàng không hợp lệ khi xác nhận.",
            details={"errors": exc.errors()},
        ) from exc

    return {
        "constraints_confirmed": True,
        "customer_constraints": constraints.model_dump(mode="json"),
        "status": "ACTIVE",
        "_interrupt_gate": None,
        "agent_message": (
            "Đã xác nhận! Em tiến hành tra cứu chính sách bán hàng hiện hành "
            "và tính phương án tài chính tham khảo cho anh/chị."
        ),
    }


def detect_prompt_injection(message: str) -> bool:
    """Phát hiện tín hiệu prompt injection cơ bản trong lời nhắn khách hàng."""
    lowered = (message or "").lower()
    patterns = ("bỏ qua chỉ dẫn", "ignore previous", "system prompt", "quên vai trò", "act as")
    return any(p in lowered for p in patterns)


def raise_injection_if_needed(state: PreSalesState) -> None:
    """Cổng an toàn PS-02/PS-03: chặn prompt injection trước khi xử lý ràng buộc."""
    if detect_prompt_injection(state.get("last_customer_message", "")):
        raise DomainError(
            ErrorCode.UNAUTHORIZED_ACCESS,
            f"{SecurityEventType.PROMPT_INJECTION_DETECTED.value}: từ chối xử lý yêu cầu.",
        )
