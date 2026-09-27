"""
Input Validation and Security Guardrail Nodes (N-01, N-02)
Owner: TechLead (cuongtv_02560)
"""

from __future__ import annotations

import re

from src.agents.official_quote.state import OfficialQuoteState
from src.contracts.enums import QuoteWorkflowStatus

INJECTION_PATTERNS = [
    re.compile(r"ignore\s+(all\s+)?(previous|prior)\s+instructions", re.IGNORECASE),
    re.compile(r"system\s+prompt\s+leak", re.IGNORECASE),
    re.compile(r"<script.*?>.*?</script>", re.IGNORECASE),
    re.compile(r"(drop|delete\s+from)\s+[a-z_]+", re.IGNORECASE),
]


def validate_input(state: OfficialQuoteState) -> dict:
    """
    N-01: Validate raw input parameters.
    Checks mandatory fields: quote_id, project_id, unit_code, listed_price_before_tax_vnd.
    """
    quote_id = state.get("quote_id")
    project_id = state.get("project_id")
    unit_code = state.get("unit_code")
    listed_price = state.get("listed_price_before_tax_vnd", 0)

    if not quote_id or not project_id or not unit_code or listed_price <= 0:
        return {
            "is_input_valid": False,
            "workflow_status": QuoteWorkflowStatus.NEEDS_INPUT,
            "errors": ["Missing mandatory quote fields: quote_id, project_id, unit_code, or valid listed_price."],
        }

    return {
        "is_input_valid": True,
        "quote_version": state.get("quote_version", 1),
        "workflow_status": QuoteWorkflowStatus.ANALYZING,
    }


def security_guardrail_input(state: OfficialQuoteState) -> dict:
    """
    N-02: Security Guardrail on Input.
    Protects against prompt injection, SQL injections, and unauthorized tampering.
    """
    text_corpus = f"{state.get('project_id', '')} {state.get('unit_code', '')}"

    for pattern in INJECTION_PATTERNS:
        if pattern.search(text_corpus):
            return {
                "is_blocked": True,
                "security_event": "PROMPT_INJECTION_BLOCKED",
                "blocked_reason": "Potentially malicious prompt injection detected in input.",
                "workflow_status": QuoteWorkflowStatus.BLOCKED,
            }

    return {
        "is_blocked": False,
        "security_event": None,
    }
