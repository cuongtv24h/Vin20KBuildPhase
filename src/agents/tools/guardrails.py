"""Guardrail helpers dùng chung cho N-02/N-05/N-10A/N-14A và pre-sales."""

TOOL_ALLOWLIST: frozenset[str] = frozenset(
    {
        "policy_time_travel_search",
        "calculate_financial_plan",
    }
)


def scan_prompt_injection(text: str) -> list[str]:
    """Quét mẫu prompt injection (trực tiếp lẫn gián tiếp trong chunk).

    Returns:
        Danh sách mẫu vi phạm tìm thấy — rỗng nếu sạch.

    TODO(Dev 1): heuristic + LLM classifier theo TD-4.3 (N-02, N-05).
    """
    raise NotImplementedError("Guardrail: scan_prompt_injection")


def check_tool_allowed(tool_name: str) -> bool:
    """Kiểm tra tool nằm trong allowlist (N-10A)."""
    return tool_name in TOOL_ALLOWLIST


def scan_output_leakage(text: str) -> list[str]:
    """Quét rò rỉ system prompt / chỉ thị nội bộ trong output LLM (N-14A)."""
    raise NotImplementedError("Guardrail: scan_output_leakage")
