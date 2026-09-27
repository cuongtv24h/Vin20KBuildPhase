"""
Test Suite for Pricing Service Layer (Task 7.2)
Owner: Dev 2 (ChungVanDuy_02854)
Tests: PricingClient Singleton, Sidecar Integration, Sanity Gate, 6-Objective Ranking,
Pre-Sales Optimizer, and LangGraph Tool Binding.
"""

import pytest

from src.agents.tools.pricing_engine import calculate_financial_plan, pricing_engine_tool
from src.contracts.enums import OptimizationObjective
from src.contracts.pricing import PricingInput, ScenarioCode
from src.services.pricing import (
    PricingClient,
    generate_reference_plans,
    get_pricing_client,
    rank_and_recommend,
    run_financial_sanity_gate,
)


@pytest.fixture
def sample_pricing_input() -> PricingInput:
    return PricingInput(
        project_id="PRJ-VIN-001",
        unit_code="VH-GRAND-PARK-S101",
        listed_price_before_tax_vnd=3_500_000_000,
        transaction_date="2026-09-27",
        own_funds_vnd=1_200_000_000,
        monthly_capacity_vnd=60_000_000,
        objective=OptimizationObjective.MIN_INITIAL_CASH,
    )


def test_pricing_client_singleton():
    """Verify get_pricing_client acts as a singleton lifecycle manager."""
    c1 = get_pricing_client()
    c2 = get_pricing_client()
    assert c1 is c2
    assert isinstance(c1, PricingClient)


@pytest.mark.asyncio
async def test_pricing_client_calculate_via_sidecar(sample_pricing_input: PricingInput):
    """Verify PricingClient integrates with PricingSidecarClient and returns valid PricingResult."""
    client = get_pricing_client()
    result = await client.calculate(sample_pricing_input)

    assert result.schema_version == "pricing-result.v1"
    assert len(result.calculation_hash) == 64
    assert len(result.scenarios) == 3
    assert ScenarioCode.PA_CHUDONG.value in result.scenarios
    assert ScenarioCode.PA_NHANH.value in result.scenarios
    assert ScenarioCode.PA_VAY.value in result.scenarios
    assert result.sanity_passed is True
    assert len(result.sanity_errors) == 0

    # Verify reconciliation for all 3 scenarios
    for code, sc in result.scenarios.items():
        assert sc.total_contract_price_vnd == sc.net_price_vnd + sc.vat_vnd + sc.kpbt_vnd
        assert sc.initial_cash_outflow_vnd > 0
        schedule_sum = sum(inst.amount_vnd for inst in sc.payment_schedule)
        assert schedule_sum == sc.total_contract_price_vnd


@pytest.mark.asyncio
async def test_run_financial_sanity_gate(sample_pricing_input: PricingInput):
    """Verify run_financial_sanity_gate returns ValidationReport conforming to FCS v2.6."""
    client = get_pricing_client()
    result = await client.calculate(sample_pricing_input)

    # Positive test
    report = run_financial_sanity_gate(result)
    assert report.is_valid is True
    assert len(report.invariants_checked) == 6
    assert len(report.field_errors) == 0

    # Negative test: tamper with one scenario
    tampered_sc = result.scenarios[ScenarioCode.PA_CHUDONG.value].model_copy()
    tampered_sc.net_price_vnd = -500_000_000
    report_neg = run_financial_sanity_gate([tampered_sc])
    assert report_neg.is_valid is False
    assert len(report_neg.field_errors) > 0


@pytest.mark.asyncio
async def test_rank_and_recommend_all_six_objectives(sample_pricing_input: PricingInput):
    """Verify rank_and_recommend evaluates all 6 canonical objectives under ADR-021."""
    client = get_pricing_client()
    result = await client.calculate(sample_pricing_input)

    all_objectives = [
        OptimizationObjective.MIN_NET_PRICE,
        OptimizationObjective.MIN_INITIAL_CASH,
        OptimizationObjective.MIN_MONTHLY_BURDEN,
        OptimizationObjective.MIN_TOTAL_CASH_OUTFLOW,
        OptimizationObjective.MAX_BENEFIT_VALUE,
        OptimizationObjective.EARLY_HANDOVER,
    ]

    for obj in all_objectives:
        rec = rank_and_recommend(result.scenarios, objective=obj)
        assert rec.selected_objective.value == obj.value
        assert rec.recommended_scenario.canonical_code in ("PA-CHUDONG", "PA-NHANH", "PA-VAY")
        assert len(rec.comparison_summary) == 3
        assert rec.comparison_summary[0]["rank"] == 1
        assert len(rec.quantitative_rationale) > 0


@pytest.mark.asyncio
async def test_pre_sales_optimizer_generate_reference_plans():
    """Verify Pre-Sales financial optimizer F3/F5 generates and filters reference plans."""
    unit_context = {
        "unit_code": "VH-GRAND-PARK-S101",
        "listed_price_vnd": 3_500_000_000,
        "project_id": "PRJ-VIN-001",
    }
    constraints = {
        "own_funds_vnd": 1_000_000_000,
        "monthly_capacity_vnd": 50_000_000,
        "objective": OptimizationObjective.MIN_INITIAL_CASH,
        "transaction_date": "2026-09-27",
    }

    # Generate all reference plans
    plans = await generate_reference_plans(unit_context, constraints, filter_infeasible=False)
    assert len(plans) == 3

    # Generate filtered feasible plans with very small own_funds
    strict_constraints = {
        "own_funds_vnd": 600_000_000,
        "monthly_capacity_vnd": 30_000_000,
        "objective": OptimizationObjective.MIN_INITIAL_CASH,
        "transaction_date": "2026-09-27",
    }
    feasible_plans = await generate_reference_plans(unit_context, strict_constraints, filter_infeasible=True)
    # At 600M funds, PA-NHANH (needs 95% upfront ~3.4B) must be filtered out
    for p in feasible_plans:
        assert p.initial_cash_outflow_vnd <= 600_000_000


@pytest.mark.asyncio
async def test_pricing_engine_langgraph_tool(sample_pricing_input: PricingInput):
    """Verify LangGraph Tool calculate_financial_plan can be directly awaited and invoked via tool protocol."""
    # 1. Direct await call
    res_direct = await calculate_financial_plan(sample_pricing_input)
    assert res_direct.schema_version == "pricing-result.v1"
    assert res_direct.sanity_passed is True

    # 2. Tool metadata verification
    assert pricing_engine_tool.name == "calculate_financial_plan"
    assert "FCS v2.6" in pricing_engine_tool.description

    # 3. Tool ainvoke call
    res_tool = await pricing_engine_tool.ainvoke({"pricing_input": sample_pricing_input})
    assert res_tool.schema_version == "pricing-result.v1"
    assert res_tool.sanity_passed is True
