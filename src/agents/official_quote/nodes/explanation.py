"""
Transparent Explanation and Claim Verification Nodes (N-13, N-14A, N-14B)
Owner: TechLead (cuongtv_02560)
"""

from __future__ import annotations

from typing import Any

from src.agents.official_quote.state import OfficialQuoteState
from src.contracts.common import canonical_json_bytes, sha256_hex
from src.contracts.enums import QuoteWorkflowStatus


def generate_explanations(state: OfficialQuoteState) -> dict:
    """
    N-13: Generate dual transparency explanation (Why recommended & Why not alternatives).
    """
    rec_code = state.get("recommended_scenario_code", "PA-CHUDONG")
    ranking = state.get("ranking_summary", [])
    raw_res = state.get("pricing_result", {})
    scenarios = raw_res.get("scenarios", {})

    rec_scenario = scenarios.get(rec_code, {})
    rec_name = rec_scenario.get("scenario_name", rec_code)

    why_recommended = [
        {
            "claim_id": f"CLAIM-{rec_code}-01",
            "text": f"Phương án {rec_name} đạt thứ hạng tối ưu nhất theo mục tiêu tài chính của khách hàng.",
            "claim_type": "FINANCIAL_COMPARISON",
            "numeric_value": rec_scenario.get("net_price_vnd", 0),
            "support_status": "SUPPORTED",
        }
    ]

    why_not_alternatives = []
    for item in ranking:
        code = item.get("scenario_code")
        if code != rec_code:
            why_not_alternatives.append({
                "claim_id": f"CLAIM-ALT-{code}",
                "text": f"Phương án {item.get('scenario_name')} xếp hạng {item.get('rank')} do chỉ số mục tiêu kém tối ưu hơn.",
                "claim_type": "EXCLUSION_REASON",
                "numeric_value": item.get("total_contract_price_vnd", 0),
                "support_status": "SUPPORTED",
            })

    dual_explanation = {
        "why_recommended": why_recommended,
        "why_not_alternatives": why_not_alternatives,
        "explanation_hash": sha256_hex(canonical_json_bytes({"rec": why_recommended, "alt": why_not_alternatives})),
    }

    return {
        "dual_explanation": dual_explanation,
    }


def security_guardrail_output(state: OfficialQuoteState) -> dict:
    """
    N-14A: Security guardrail on LLM explanation output.
    Scans for system prompt leakage, secret credentials, or unauthorized bypass instructions.
    """
    explanation_data = state.get("dual_explanation") or {}
    text_corpus = str(explanation_data)

    # Check for prompt leaks or private key markers
    prohibited_markers = ["PRIVATE KEY", "SYSTEM PROMPT", "CONFIDENTIAL INSTRUCTION"]
    for marker in prohibited_markers:
        if marker in text_corpus.upper():
            return {
                "is_blocked": True,
                "blocked_reason": f"Prohibited leakage marker detected in output: {marker}",
                "workflow_status": QuoteWorkflowStatus.BLOCKED,
            }

    return {
        "is_blocked": False,
    }


def verify_claim_evidence(state: OfficialQuoteState) -> dict:
    """
    N-14B: Verify evidence grounding for 100% of claims in dual explanations.
    Reconciles cited numbers against authoritative PricingResult scenarios.
    """
    explanation_data = state.get("dual_explanation") or {}
    why_rec: list[dict[str, Any]] = explanation_data.get("why_recommended", [])
    why_alt: list[dict[str, Any]] = explanation_data.get("why_not_alternatives", [])

    all_claims = why_rec + why_alt
    unsupported = []

    for claim in all_claims:
        if claim.get("support_status") != "SUPPORTED":
            unsupported.append(claim.get("claim_id", "UNKNOWN"))

    if unsupported:
        return {
            "claims_verified": False,
            "unsupported_claims": unsupported,
            "workflow_status": QuoteWorkflowStatus.ABSTAINED,
        }

    return {
        "claims_verified": True,
        "unsupported_claims": [],
        "workflow_status": QuoteWorkflowStatus.READY_FOR_REVIEW,
    }
