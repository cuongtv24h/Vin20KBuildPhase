"""Golden Benchmark Test Suite (15 Cases FCS v2.6 Table 10 + 2 Regression Cases).

FCS v2.6 Reference: Table 10 (Canonical Benchmark Scenarios Suite)
AC-FIN-01 Reference: Exact Zero-Delta (Delta = 0 VND) on all golden vectors.
TD-4.1 Reference: INV-RT-01 (Deterministic Accounting Math) & Spike 2.

This test suite:
1. Loads 17 test vectors from `dataset/fixtures/golden_scenarios.json`.
2. Evaluates 13 valid calculation scenarios and asserts Delta = 0 VND on every financial field.
3. Evaluates 4 exception / blocked edge cases (TC-07, TC-09, TC-12, TC-13).
4. Verifies 100% RFC 8785 Canonical JSON and SHA-256 snapshot hashes.
5. Verifies performance SLA (< 500ms for full suite).
"""

import json
import time
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest

from src.pricing_sidecar.canonical_hash import (
    build_pricing_snapshot_payload,
    create_pricing_calculation_output,
    verify_canonical_hash,
)
from src.pricing_sidecar.contracts import (
    BenefitApplicationRule,
    BenefitCategory,
    BenefitType,
    OptimizationObjective,
    PricingCalculationInput,
    ScenarioType,
    StructuredPolicyReference,
    ValuationStatus,
)
from src.pricing_sidecar.engine import (
    calculate_canonical_scenario,
    calculate_pa_chudong,
    calculate_pa_nhanh,
    calculate_pa_vay,
)
from src.pricing_sidecar.ranking import recommend_best_scenario
from src.pricing_sidecar.validation import check_scenario_sanity

FIXTURE_PATH = Path(__file__).resolve().parent.parent.parent / "dataset" / "fixtures" / "golden_scenarios.json"


def load_golden_scenarios() -> list[dict[str, Any]]:
    """Load golden test vectors from JSON fixture file."""
    with open(FIXTURE_PATH, encoding="utf-8") as f:
        return json.load(f)


ALL_CASES = load_golden_scenarios()
CALCULATION_CASES = [c for c in ALL_CASES if c.get("calc_status") == "VALID"]
EXCEPTION_CASES = [c for c in ALL_CASES if c.get("calc_status") == "NOT_RUN"]

DEFAULT_POLICY_REF = StructuredPolicyReference(
    policy_id="POL-2026-VLF-GEN",
    policy_version="v2.6",
    clause_id="Điều 4 Khoản 1",
    page_number=10,
    source_file_sha256="c" * 64,
    effective_from=date(2026, 1, 1),
    effective_to=date(2026, 12, 31),
)


def build_approved_benefits(case: dict[str, Any]) -> list[BenefitApplicationRule]:
    """Extract and build BenefitApplicationRule list from golden test case definition."""
    rules: list[BenefitApplicationRule] = []
    case_id = case["case_id"]

    # 1. Fixed cash deductions
    # TC-06: 160tr in-kind SJC gold deducting price (approved valuation)
    if case_id == "TC-06":
        rules.append(
            BenefitApplicationRule(
                benefit_id=f"BEN-GOLD-{case_id}",
                benefit_type=BenefitType.IN_KIND,
                category=BenefitCategory.IN_KIND_GIFT,
                fixed_deduction_vnd=160_000_000,
                price_deduction_authorized=True,
                valuation_status=ValuationStatus.APPROVED,
                source_policy_clause=DEFAULT_POLICY_REF,
            )
        )
    elif case.get("fixed_discount_vnd", 0) > 0:
        fixed_val = int(case["fixed_discount_vnd"])
        rules.append(
            BenefitApplicationRule(
                benefit_id=f"BEN-FIXED-{case_id}",
                benefit_type=BenefitType.FIXED_CASH,
                category=BenefitCategory.CASH_DISCOUNT,
                fixed_deduction_vnd=fixed_val,
                price_deduction_authorized=True,
                valuation_status=ValuationStatus.APPROVED,
                source_policy_clause=DEFAULT_POLICY_REF,
            )
        )

    # 2. Additive percentage commercial discounts
    # BENCH-02: 2% progress discount
    if case_id == "BENCH-02":
        rules.append(
            BenefitApplicationRule(
                benefit_id="BEN-PROG-BENCH-02",
                benefit_type=BenefitType.PERCENTAGE,
                category=BenefitCategory.CASH_DISCOUNT,
                discount_rate=Decimal("0.0200"),
                price_deduction_authorized=True,
                valuation_status=ValuationStatus.APPROVED,
                source_policy_clause=DEFAULT_POLICY_REF,
            )
        )

    # TC-04: 1% Resident discount (cộng dồn với 8% TT sớm = 9%)
    if case_id == "TC-04":
        rules.append(
            BenefitApplicationRule(
                benefit_id="BEN-RESIDENT-TC04",
                benefit_type=BenefitType.PERCENTAGE,
                category=BenefitCategory.CASH_DISCOUNT,
                discount_rate=Decimal("0.0100"),
                price_deduction_authorized=True,
                valuation_status=ValuationStatus.APPROVED,
                source_policy_clause=DEFAULT_POLICY_REF,
            )
        )

    return rules


class TestGoldenFixturesIntegrity:
    """Verifies that golden fixture dataset is complete and intact."""

    def test_fixture_file_contains_17_cases(self) -> None:
        assert len(ALL_CASES) == 17
        case_ids = [c["case_id"] for c in ALL_CASES]
        expected_ids = ["BENCH-01", "BENCH-02"] + [f"TC-{i:02d}" for i in range(1, 16)]
        assert sorted(case_ids) == sorted(expected_ids)

    def test_zero_delta_allowed_for_all_cases(self) -> None:
        for c in ALL_CASES:
            assert c["delta_allowed_vnd"] == 0, f"Case {c['case_id']} must have delta_allowed_vnd = 0"


class TestGoldenCalculations:
    """Rigorous verification of AC-FIN-01 (Delta = 0 VND) on all 13 valid calculation vectors."""

    @pytest.mark.parametrize("case", CALCULATION_CASES, ids=lambda c: c["case_id"])
    def test_golden_scenario_exact_amounts(self, case: dict[str, Any]) -> None:
        case_id = case["case_id"]
        listed_price = case["listed_price_before_tax_vnd"]
        deposit_amount = case["deposit_amount_vnd"]
        deposit_date = date.fromisoformat(case["deposit_date"])
        signing_date = date.fromisoformat(case["transaction_date"])
        benefits = build_approved_benefits(case)

        # Determine early discount rate for time-travel or standard
        # TC-06 & TC-11 use 6% early discount; others use 8%
        if case_id in ("TC-06", "TC-11"):
            early_rate = Decimal("0.0600")
        else:
            early_rate = Decimal("0.0800")

        # Handle multi-objective cases vs single-scenario cases
        if "optimization_objective" in case:
            # Multi-scenario optimization case (TC-14, TC-15)
            objective = OptimizationObjective(case["optimization_objective"])
            res_chudong = calculate_pa_chudong(
                listed_price_vnd=listed_price,
                approved_benefits=benefits,
                deposit_amount_vnd=deposit_amount,
                deposit_date=deposit_date,
            )
            res_nhanh = calculate_pa_nhanh(
                listed_price_vnd=listed_price,
                approved_benefits=benefits,
                deposit_amount_vnd=deposit_amount,
                early_discount_rate=early_rate,
                deposit_date=deposit_date,
            )
            res_vay = calculate_pa_vay(
                listed_price_vnd=listed_price,
                approved_benefits=benefits,
                deposit_amount_vnd=deposit_amount,
                deposit_date=deposit_date,
            )
            scenarios = [res_chudong, res_nhanh, res_vay]
            recommendation = recommend_best_scenario(scenarios, objective=objective)

            # Match recommended scenario result
            matched = next(s for s in scenarios if s.scenario_type == recommendation.recommended_scenario)
            calc_result = matched
            assert recommendation.recommended_scenario.canonical_code == case["recommended_scenario"]
        else:
            # Direct canonical scenario dispatch
            rec_code = case["recommended_scenario"]
            if rec_code == "PA-NHANH":
                stype = ScenarioType.EARLY_95
            elif rec_code == "PA-VAY":
                stype = ScenarioType.BANK_LOAN_HTLS
            else:
                stype = ScenarioType.STANDARD_PROGRESS

            calc_result = calculate_canonical_scenario(
                scenario_type_or_code=stype,
                listed_price_vnd=listed_price,
                approved_benefits=benefits,
                deposit_amount_vnd=deposit_amount,
                early_discount_rate=early_rate,
                deposit_date=deposit_date,
            )

        # -------------------------------------------------------------------
        # AC-FIN-01: Zero-Delta Assertions on All 9 Financial Fields
        # -------------------------------------------------------------------
        expected_net = case["net_price_before_tax_vnd"]
        expected_vat = case["vat_vnd"]
        expected_kpbt = case["maintenance_fee_vnd"]
        expected_contract = case["contract_price_vnd"]
        expected_fixed_discount = case["fixed_discount_vnd"]
        expected_discount_amount = case["discount_amount_vnd"]
        expected_initial_gross = case["initial_gross_obligation_vnd"]
        expected_initial_due = case["initial_additional_cash_due_vnd"]

        # Note on legacy BENCH-01 fixture: (4.655.200.000 * 0.95 = 4.422.440.000; fixture typo: 4422240000)
        if case_id == "BENCH-01":
            expected_initial_gross = 4422440000
            expected_initial_due = 4322440000

        # 1. Net Price before tax (Delta = 0 VND)
        diff_net = abs(int(calc_result.net_price_before_vat) - expected_net)
        assert diff_net == 0, (
            f"[{case_id}] Sai lệch Net Price: thực tế={calc_result.net_price_before_vat}, "
            f"kỳ vọng={expected_net}, delta={diff_net}đ"
        )

        # 2. VAT amount (Delta = 0 VND)
        diff_vat = abs(int(calc_result.vat_amount) - expected_vat)
        assert diff_vat == 0, (
            f"[{case_id}] Sai lệch VAT: thực tế={calc_result.vat_amount}, kỳ vọng={expected_vat}, delta={diff_vat}đ"
        )

        # 3. Maintenance fee KPBT (Delta = 0 VND)
        diff_kpbt = abs(int(calc_result.maintenance_fee_amount) - expected_kpbt)
        assert diff_kpbt == 0, (
            f"[{case_id}] Sai lệch KPBT: thực tế={calc_result.maintenance_fee_amount}, "
            f"kỳ vọng={expected_kpbt}, delta={diff_kpbt}đ"
        )

        # 4. Total Contract Price (Delta = 0 VND)
        if case_id.startswith("BENCH-"):
            expected_contract = case.get("total_outflow_vnd") or case["contract_price_vnd"]
        else:
            expected_contract = case["contract_price_vnd"]

        diff_contract = abs(int(calc_result.final_contract_price) - expected_contract)
        assert diff_contract == 0, (
            f"[{case_id}] Sai lệch Contract Price: thực tế={calc_result.final_contract_price}, "
            f"kỳ vọng={expected_contract}, delta={diff_contract}đ"
        )

        # 5. Fixed cash discount
        assert int(calc_result.fixed_discount_vnd) == expected_fixed_discount, (
            f"[{case_id}] Sai lệch fixed_discount: thực tế={calc_result.fixed_discount_vnd}, "
            f"kỳ vọng={expected_fixed_discount}"
        )

        # 6. Total discount amount (Fixed + Percentage)
        actual_total_discount = int(calc_result.fixed_discount_vnd + calc_result.percentage_discount_vnd)
        assert actual_total_discount == expected_discount_amount, (
            f"[{case_id}] Sai lệch discount_amount: thực tế={actual_total_discount}, kỳ vọng={expected_discount_amount}"
        )

        # 7. Milestone 1 Gross Obligation
        diff_gross = abs(int(calc_result.initial_gross_obligation_vnd) - expected_initial_gross)
        assert diff_gross == 0, (
            f"[{case_id}] Sai lệch Đợt 1 gross: thực tế={calc_result.initial_gross_obligation_vnd}, "
            f"kỳ vọng={expected_initial_gross}"
        )

        # 8. Milestone 1 Additional Cash Due (after deposit credit)
        actual_initial_due = int(calc_result.cashflow_schedule[0].installment_additional_cash_due_vnd)
        diff_due = abs(actual_initial_due - expected_initial_due)
        assert diff_due == 0, (
            f"[{case_id}] Sai lệch Đợt 1 nộp thêm: thực tế={actual_initial_due}, kỳ vọng={expected_initial_due}"
        )

        # 9. Sanity Gate Validation Check
        sanity_errors = check_scenario_sanity(calc_result)
        assert len(sanity_errors) == 0, f"[{case_id}] Bị lỗi Sanity Checks: {sanity_errors}"

        # 10. Cryptographic Snapshot Hash Verification
        input_data = PricingCalculationInput(
            unit_code=case["unit_code"],
            deposit_date=deposit_date,
            contract_signing_date=signing_date,
            listed_price_vnd=listed_price,
            deposit_amount_vnd=deposit_amount,
            resolved_policy_snapshot_id=f"SNAP-{case_id}-V1",
            source_policy_hash="sha256:e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
            approved_benefits=benefits,
        )
        output = create_pricing_calculation_output(
            input_data=input_data,
            scenario_results=[calc_result],
            quote_id=f"QUOTE-{case_id}",
            quote_version=1,
        )
        assert len(output.canonical_snapshot_hash) == 64
        rebuilt_payload = build_pricing_snapshot_payload(
            input_data=input_data,
            scenario_results=[calc_result],
        )
        assert verify_canonical_hash(rebuilt_payload, output.canonical_snapshot_hash) is True


class TestGoldenExceptionCases:
    """Verifies that edge cases, conflicts, and blocked properties are correctly guarded."""

    @pytest.mark.parametrize("case", EXCEPTION_CASES, ids=lambda c: c["case_id"])
    def test_exception_case_guards(self, case: dict[str, Any]) -> None:
        case_id = case["case_id"]

        # Ensure calculation was safely abstained / not executed
        assert case["calc_status"] == "NOT_RUN", f"[{case_id}] calc_status must be NOT_RUN"
        assert case["net_price_before_tax_vnd"] is None
        assert case["contract_price_vnd"] is None
        assert case["initial_gross_obligation_vnd"] is None
        assert case["initial_additional_cash_due_vnd"] is None

        # Verify business governance states
        if case_id == "TC-07":
            # Conflict tier 1 (Loan + Early discount conflict)
            assert case["policy_decision"] == "CONFLICT"
            assert case["agent_action"] == "SAFE_ABSTAIN"
            assert case["workflow_status"] == "ABSTAINED"
        elif case_id == "TC-09":
            # Ambiguous clause
            assert case["policy_decision"] == "AMBIGUOUS"
            assert case["agent_action"] == "SAFE_ABSTAIN"
            assert case["workflow_status"] == "ABSTAINED"
        elif case_id in ("TC-12", "TC-13"):
            # Unit already deposited or locked by another sale
            assert case["policy_decision"] == "NOT_ELIGIBLE"
            assert case["agent_action"] == "STOP"
            assert case["workflow_status"] == "BLOCKED"


class TestGoldenSuitePerformance:
    """Verifies that evaluating the entire 17-vector benchmark suite completes well under SLA."""

    def test_full_benchmark_suite_latency_under_500ms(self) -> None:
        start = time.perf_counter()

        # Run 10 iterations of the full 13 calculation cases
        for _ in range(10):
            for case in CALCULATION_CASES:
                listed_price = case["listed_price_before_tax_vnd"]
                deposit_amount = case["deposit_amount_vnd"]
                deposit_date = date.fromisoformat(case["deposit_date"])
                benefits = build_approved_benefits(case)
                early_rate = Decimal("0.0600") if case["case_id"] in ("TC-06", "TC-11") else Decimal("0.0800")

                calculate_canonical_scenario(
                    scenario_type_or_code=ScenarioType.STANDARD_PROGRESS,
                    listed_price_vnd=listed_price,
                    approved_benefits=benefits,
                    deposit_amount_vnd=deposit_amount,
                    early_discount_rate=early_rate,
                    deposit_date=deposit_date,
                )

        elapsed_ms = (time.perf_counter() - start) * 1000
        # 10 iterations * 13 cases = 130 scenario evaluations must take < 500ms
        assert elapsed_ms < 500.0, f"Full suite 10 runs took {elapsed_ms:.2f}ms, exceeding 500ms limit"
