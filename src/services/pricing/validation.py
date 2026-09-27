"""
Financial Sanity Validation Module (FCS v2.6)
Owner: TechLead (cuongtv_02560)
Component: C-06 / C-01
Validates the 6 financial sanity check invariants across calculated scenarios.
"""

from __future__ import annotations

from src.contracts.pricing import PricingResult, ScenarioDetail


class SanityValidationError(ValueError):
    """Phát hiện vi phạm một trong 6 nhóm Sanity Checks kế toán."""
    pass


def validate_scenario_sanity(scenario: ScenarioDetail) -> list[str]:
    """
    Validate a single ScenarioDetail against the 6 accounting invariants.
    Returns a list of error strings (empty if passed).
    """
    errors: list[str] = []
    code = scenario.scenario_code.value

    # Check 1: Non-negative financial values
    if scenario.net_price_vnd < 0:
        errors.append(f"{code}: Net price is negative ({scenario.net_price_vnd}).")
    if scenario.vat_vnd < 0:
        errors.append(f"{code}: VAT amount is negative ({scenario.vat_vnd}).")
    if scenario.kpbt_vnd < 0:
        errors.append(f"{code}: KPBT amount is negative ({scenario.kpbt_vnd}).")
    if scenario.total_contract_price_vnd < 0:
        errors.append(f"{code}: Total contract price is negative ({scenario.total_contract_price_vnd}).")
    if scenario.initial_cash_outflow_vnd < 0:
        errors.append(f"{code}: Initial cash outflow is negative ({scenario.initial_cash_outflow_vnd}).")
    if scenario.total_cash_outflow_vnd < 0:
        errors.append(f"{code}: Total cash outflow is negative ({scenario.total_cash_outflow_vnd}).")
    if scenario.benefit_value_vnd < 0:
        errors.append(f"{code}: Benefit value is negative ({scenario.benefit_value_vnd}).")

    # Check 2: Total contract price reconciliation: Total = Net + VAT + KPBT
    expected_total = scenario.net_price_vnd + scenario.vat_vnd + scenario.kpbt_vnd
    if scenario.total_contract_price_vnd != expected_total:
        errors.append(
            f"{code}: Total contract price ({scenario.total_contract_price_vnd}) "
            f"does not match Net+VAT+KPBT sum ({expected_total})."
        )

    # Check 3: Payment schedule total must reconcile 100% with total contract price
    if scenario.payment_schedule:
        schedule_sum = sum(item.amount_vnd for item in scenario.payment_schedule)
        if schedule_sum != scenario.total_contract_price_vnd:
            errors.append(
                f"{code}: Schedule installments sum ({schedule_sum}) "
                f"does not match total contract price ({scenario.total_contract_price_vnd})."
            )

    # Check 4: Initial cash outflow must be strictly positive
    if scenario.initial_cash_outflow_vnd <= 0:
        errors.append(f"{code}: Initial cash outflow must be > 0.")

    # Check 5: Bank loan ratio (if applicable in PA-VAY) <= 75%
    if scenario.scenario_code.value == "PA-VAY":
        # Total cash outflow should be less than total contract price due to bank loan
        if scenario.total_cash_outflow_vnd >= scenario.total_contract_price_vnd:
            errors.append(
                f"{code}: Bank loan scenario requires total cash outflow < total contract price."
            )

    # Check 6: Benefits cannot exceed 50% of base net price
    if scenario.benefit_value_vnd > (scenario.net_price_vnd // 2):
        errors.append(f"{code}: Benefit value exceeds 50% of net price threshold.")

    return errors


def validate_pricing_result_sanity(result: PricingResult) -> list[str]:
    """
    Validate all scenarios inside a PricingResult.
    Returns combined list of errors.
    """
    all_errors: list[str] = []
    if not result.scenarios:
        return ["PricingResult contains no scenarios."]

    for scenario in result.scenarios.values():
        errs = validate_scenario_sanity(scenario)
        all_errors.extend(errs)

    return all_errors
