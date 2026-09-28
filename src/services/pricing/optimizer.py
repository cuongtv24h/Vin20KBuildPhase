"""
Pre-Sales Financial Optimizer Module (F3/F5)
Owner: Dev 2 (ChungVanDuy_02854)
Component: C-06 / C-09

Generates reference financial payment plans for Pre-Sales consultation,
filters infeasible scenarios based on customer constraints (own funds & monthly capacity),
and ranks optimal scenarios according to customer objectives.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from src.contracts.enums import OptimizationObjective
from src.contracts.pricing import PricingInput, ScenarioDetail
from src.services.pricing.client import get_pricing_client


def filter_feasible_scenarios(
    scenarios: list[ScenarioDetail] | dict[str, ScenarioDetail],
    own_funds_vnd: int = 0,
    monthly_capacity_vnd: int = 0,
) -> list[ScenarioDetail]:
    """
    Filters scenarios that satisfy customer financial constraints.
    - If own_funds_vnd > 0: initial_cash_outflow_vnd <= own_funds_vnd
    - If monthly_capacity_vnd > 0: monthly_burden_vnd <= monthly_capacity_vnd
    """
    items = list(scenarios.values()) if isinstance(scenarios, dict) else scenarios
    feasible: list[ScenarioDetail] = []
    for sc in items:
        valid_funds = (own_funds_vnd <= 0) or (sc.initial_cash_outflow_vnd <= own_funds_vnd)
        valid_monthly = (monthly_capacity_vnd <= 0) or (sc.monthly_burden_vnd <= monthly_capacity_vnd)
        if valid_funds and valid_monthly:
            feasible.append(sc)
    return feasible


async def generate_reference_plans(
    unit_context: dict[str, Any],
    constraints: dict[str, Any] | None = None,
    filter_infeasible: bool = False,
) -> list[ScenarioDetail]:
    """
    Generates reference financial plans (PA-CHUDONG, PA-NHANH, PA-VAY) for Pre-Sales Discovery (F1/F2/F3/F5).

    Args:
        unit_context: Contains unit details (unit_code, listed_price_vnd / listed_price_before_tax_vnd, project_id).
        constraints: Customer constraints (own_funds_vnd, monthly_capacity_vnd, objective, transaction_date).
        filter_infeasible: If True, returns only scenarios meeting own_funds & monthly_capacity limits.

    Returns:
        List of ScenarioDetail objects sorted by recommendation rank.
    """
    c = constraints or {}
    unit_code = unit_context.get("unit_code", "U-DEFAULT")
    listed_price = (
        unit_context.get("listed_price_before_tax_vnd")
        or unit_context.get("listed_price_vnd")
        or 3_000_000_000
    )
    project_id = unit_context.get("project_id", "PRJ-DEFAULT")

    own_funds = c.get("own_funds_vnd", 0)
    monthly_cap = c.get("monthly_capacity_vnd", 0)
    obj_raw = c.get("objective", OptimizationObjective.MIN_INITIAL_CASH)
    if isinstance(obj_raw, str):
        objective = OptimizationObjective(obj_raw)
    else:
        objective = obj_raw

    tx_date = c.get("transaction_date") or date.today().isoformat()

    pricing_input = PricingInput(
        schema_version="pricing-input.v1",
        execution_context="PRE_SALES",
        project_id=project_id,
        unit_code=unit_code,
        listed_price_before_tax_vnd=listed_price,
        transaction_date=tx_date,
        own_funds_vnd=own_funds,
        monthly_capacity_vnd=monthly_cap,
        objective=objective,
        active_policy_ids=unit_context.get("active_policy_ids", []),
    )

    client = get_pricing_client()
    result = await client.calculate(pricing_input)

    # Sort scenarios with recommended scenario first
    scenarios_list = list(result.scenarios.values())
    rec_code = result.recommended_scenario_code
    scenarios_list.sort(key=lambda s: 0 if s.scenario_code == rec_code else 1)

    if filter_infeasible:
        return filter_feasible_scenarios(
            scenarios_list,
            own_funds_vnd=own_funds,
            monthly_capacity_vnd=monthly_cap,
        )
    return scenarios_list
