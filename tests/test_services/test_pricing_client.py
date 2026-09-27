"""
Tests for PricingClient (UDS Bridge & In-Process Deterministic Math Engine)
Owner: TechLead (cuongtv_02560)
"""

import pytest

from src.contracts.enums import OptimizationObjective
from src.contracts.pricing import PricingInput, ScenarioCode
from src.services.pricing import PricingClient


@pytest.fixture
def sample_pricing_input() -> PricingInput:
    return PricingInput(
        project_id="PRJ-VIN-001",
        unit_code="U-1204",
        listed_price_before_tax_vnd=3_000_000_000,
        transaction_date="2026-09-26",
        own_funds_vnd=1_000_000_000,
        monthly_capacity_vnd=50_000_000,
        objective=OptimizationObjective.MIN_INITIAL_CASH,
    )


@pytest.mark.asyncio
async def test_pricing_client_deterministic_scenarios(sample_pricing_input: PricingInput):
    client = PricingClient(force_mock=True)
    result = await client.calculate(sample_pricing_input)

    assert result.schema_version == "pricing-result.v1"
    assert len(result.scenarios) == 3
    assert ScenarioCode.PA_CHUDONG.value in result.scenarios
    assert ScenarioCode.PA_NHANH.value in result.scenarios
    assert ScenarioCode.PA_VAY.value in result.scenarios

    # Check financial reconciliation for all 3 scenarios
    for code, scenario in result.scenarios.items():
        assert scenario.net_price_vnd > 0
        assert scenario.vat_vnd > 0
        assert scenario.kpbt_vnd > 0
        assert scenario.total_contract_price_vnd == (
            scenario.net_price_vnd + scenario.vat_vnd + scenario.kpbt_vnd
        )

        # Payment schedule items sum must equal 100% total contract price
        schedule_total = sum(item.amount_vnd for item in scenario.payment_schedule)
        assert schedule_total == scenario.total_contract_price_vnd, (
            f"Schedule total mismatch in {code}: {schedule_total} vs {scenario.total_contract_price_vnd}"
        )


@pytest.mark.asyncio
async def test_pricing_client_sanity_checks_passed(sample_pricing_input: PricingInput):
    client = PricingClient(force_mock=True)
    result = await client.calculate(sample_pricing_input)

    assert result.sanity_passed is True
    assert len(result.sanity_errors) == 0


@pytest.mark.asyncio
async def test_pricing_client_objective_ranking():
    client = PricingClient(force_mock=True)

    # 1. MIN_INITIAL_CASH -> PA-VAY
    inp_cash = PricingInput(
        project_id="PRJ-01",
        unit_code="U-01",
        listed_price_before_tax_vnd=2_500_000_000,
        transaction_date="2026-09-26",
        own_funds_vnd=500_000_000,
        monthly_capacity_vnd=30_000_000,
        objective=OptimizationObjective.MIN_INITIAL_CASH,
    )
    res_cash = await client.calculate(inp_cash)
    assert res_cash.recommended_scenario_code == ScenarioCode.PA_VAY

    # 2. MIN_NET_PRICE -> PA-NHANH
    inp_price = PricingInput(
        project_id="PRJ-01",
        unit_code="U-01",
        listed_price_before_tax_vnd=2_500_000_000,
        transaction_date="2026-09-26",
        own_funds_vnd=500_000_000,
        monthly_capacity_vnd=30_000_000,
        objective=OptimizationObjective.MIN_NET_PRICE,
    )
    res_price = await client.calculate(inp_price)
    assert res_price.recommended_scenario_code == ScenarioCode.PA_NHANH


@pytest.mark.asyncio
async def test_pricing_client_hash_stability(sample_pricing_input: PricingInput):
    client = PricingClient(force_mock=True)
    res1 = await client.calculate(sample_pricing_input)
    res2 = await client.calculate(sample_pricing_input)

    assert len(res1.calculation_hash) == 64
    assert res1.calculation_hash == res2.calculation_hash
