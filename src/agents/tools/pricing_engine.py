"""
Pricing Engine Agent Tool
Owner: TechLead (cuongtv_02560)
Component: C-01 Tool Calling Interface for C-06 Deterministic Financial Pricing Engine
"""

from __future__ import annotations

from typing import Any

from langchain_core.tools import tool

from src.contracts.pricing import PricingInput, PricingResult
from src.services.pricing import get_pricing_client


async def calculate_financial_plan(pricing_input: PricingInput | dict[str, Any]) -> PricingResult:
    """
    Agent tool invoking the Deterministic Pricing Engine (C-06).
    Computes 3 financial scenarios (PA-CHUDONG, PA-NHANH, PA-VAY) adhering to FCS v2.6.
    """
    if isinstance(pricing_input, dict):
        validated_input = PricingInput(**pricing_input)
    else:
        validated_input = pricing_input

    client = get_pricing_client()
    return await client.calculate(validated_input)


# LangGraph / LangChain tool wrapper for agent graph bindings
pricing_engine_tool = tool("calculate_financial_plan")(calculate_financial_plan)

