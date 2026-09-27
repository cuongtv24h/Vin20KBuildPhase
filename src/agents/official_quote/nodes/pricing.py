"""
Pricing Engine and Accounting Sanity Check Nodes (N-09, N-10A, N-10B, N-11)
Owner: TechLead (cuongtv_02560)
"""

from __future__ import annotations

from src.agents.official_quote.state import OfficialQuoteState
from src.contracts.enums import OptimizationObjective, QuoteWorkflowStatus
from src.contracts.pricing import PricingInput, PricingResult
from src.services.pricing import PricingClient, validate_pricing_result_sanity


def prepare_pricing_input(state: OfficialQuoteState) -> dict:
    """
    N-09: Prepare standardized PricingInput DTO for the pricing engine.
    """
    p_input = PricingInput(
        schema_version="pricing-input.v1",
        execution_context="OFFICIAL_QUOTE",
        quote_id=state.get("quote_id", ""),
        quote_version=state.get("quote_version", 1),
        project_id=state.get("project_id", ""),
        unit_code=state.get("unit_code", ""),
        listed_price_before_tax_vnd=state.get("listed_price_before_tax_vnd", 3_000_000_000),
        transaction_date=state.get("transaction_date", "2026-09-26"),
        own_funds_vnd=state.get("own_funds_vnd", 1_000_000_000),
        monthly_capacity_vnd=state.get("monthly_capacity_vnd", 50_000_000),
        objective=state.get("objective", OptimizationObjective.MIN_INITIAL_CASH),
        policy_snapshot_hash=state.get("policy_snapshot_hash"),
        active_policy_ids=state.get("retrieved_policy_ids", []),
    )

    return {
        "pricing_input": p_input.model_dump(),
        "workflow_status": QuoteWorkflowStatus.CALCULATING,
    }


def tool_guardrail_pricing(state: OfficialQuoteState) -> dict:
    """
    N-10A: Pre-invocation tool guardrail.
    Validates range and sanity of input parameters before executing pricing math.
    """
    p_in = state.get("pricing_input") or {}
    price = p_in.get("listed_price_before_tax_vnd", 0)

    if price <= 0:
        return {
            "is_blocked": True,
            "blocked_reason": "Listed price must be strictly greater than 0.",
            "workflow_status": QuoteWorkflowStatus.CALCULATION_FAILED,
        }

    return {
        "is_blocked": False,
    }


async def call_pricing_engine(state: OfficialQuoteState) -> dict:
    """
    N-10B: Call the Deterministic Financial Pricing Engine (C-06) via PricingClient.
    Supports UDS bridge with automatic deterministic in-process fallback.
    """
    p_in_dict = state.get("pricing_input") or {}
    p_input = PricingInput(**p_in_dict)

    client = PricingClient()
    result: PricingResult = await client.calculate(p_input)

    return {
        "pricing_result": result.model_dump(),
    }


def validate_financial_sanity(state: OfficialQuoteState) -> dict:
    """
    N-11: Validate the 6 accounting sanity checks (FCS v2.6).
    Reconciles schedules, non-negativity, and exact total contract price.
    """
    raw_res = state.get("pricing_result") or {}
    result = PricingResult(**raw_res)

    sanity_errors = validate_pricing_result_sanity(result)
    if sanity_errors:
        return {
            "sanity_passed": False,
            "sanity_errors": sanity_errors,
            "workflow_status": QuoteWorkflowStatus.CALCULATION_FAILED,
        }

    return {
        "sanity_passed": True,
        "sanity_errors": [],
    }
