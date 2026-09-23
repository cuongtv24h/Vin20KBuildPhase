"""Unit tests for domain Enums and business mappings in src.pricing_sidecar.contracts."""

import json

from src.pricing_sidecar.contracts import (
    CANONICAL_SCENARIO_ORDER,
    SCENARIO_ALIAS_MAP,
    VALID_BENEFIT_MAPPING,
    BenefitCategory,
    BenefitType,
    CalculationBase,
    CalculationStatus,
    OptimizationObjective,
    PolicyDecisionStatus,
    QuoteWorkflowStatus,
    ScenarioType,
    ValuationStatus,
)


class TestScenarioTypeEnum:
    """Verify ScenarioType values and aliases."""

    def test_enum_values(self):
        assert ScenarioType.STANDARD_PROGRESS.value == "STANDARD_PROGRESS"
        assert ScenarioType.EARLY_95.value == "EARLY_95"
        assert ScenarioType.BANK_LOAN_HTLS.value == "BANK_LOAN_HTLS"
        assert len(ScenarioType) == 3

    def test_is_string_enum(self):
        assert isinstance(ScenarioType.STANDARD_PROGRESS, str)
        assert json.dumps({"scenario": ScenarioType.EARLY_95}) == '{"scenario": "EARLY_95"}'

    def test_canonical_codes(self):
        assert ScenarioType.STANDARD_PROGRESS.canonical_code == "PA-CHUDONG"
        assert ScenarioType.EARLY_95.canonical_code == "PA-NHANH"
        assert ScenarioType.BANK_LOAN_HTLS.canonical_code == "PA-VAY"
        assert SCENARIO_ALIAS_MAP[ScenarioType.STANDARD_PROGRESS] == "PA-CHUDONG"

    def test_canonical_scenario_order(self):
        assert CANONICAL_SCENARIO_ORDER[ScenarioType.STANDARD_PROGRESS] == 1
        assert CANONICAL_SCENARIO_ORDER[ScenarioType.EARLY_95] == 2
        assert CANONICAL_SCENARIO_ORDER[ScenarioType.BANK_LOAN_HTLS] == 3


class TestOptimizationObjectiveEnum:
    """Verify 5 business optimization objectives."""

    def test_objectives_count_and_values(self):
        assert len(OptimizationObjective) == 5
        expected = {
            "MIN_NET_PRICE",
            "MIN_CONTRACT_PRICE",
            "MIN_INITIAL_OUTFLOW",
            "MIN_CASH_OUTFLOW_TO_HANDOVER",
            "MAX_BENEFIT_VALUE",
        }
        actual = {obj.value for obj in OptimizationObjective}
        assert actual == expected

    def test_string_representation(self):
        for obj in OptimizationObjective:
            assert isinstance(obj, str)


class TestBenefitCategoryAndTypeEnums:
    """Verify benefit categories, types, and compatibility matrix."""

    def test_benefit_categories(self):
        assert len(BenefitCategory) == 4
        assert BenefitCategory.CASH_DISCOUNT.value == "CASH_DISCOUNT"
        assert BenefitCategory.IN_KIND_GIFT.value == "IN_KIND_GIFT"
        assert BenefitCategory.VOUCHER.value == "VOUCHER"
        assert BenefitCategory.SERVICE_WAIVER.value == "SERVICE_WAIVER"

    def test_benefit_types(self):
        assert len(BenefitType) == 5
        assert BenefitType.FIXED_CASH.value == "FIXED_CASH"
        assert BenefitType.PERCENTAGE.value == "PERCENTAGE"
        assert BenefitType.IN_KIND.value == "IN_KIND"
        assert BenefitType.VOUCHER.value == "VOUCHER"
        assert BenefitType.SERVICE_WAIVER.value == "SERVICE_WAIVER"

    def test_valid_benefit_mapping(self):
        assert VALID_BENEFIT_MAPPING[BenefitCategory.CASH_DISCOUNT] == {
            BenefitType.FIXED_CASH,
            BenefitType.PERCENTAGE,
        }
        assert VALID_BENEFIT_MAPPING[BenefitCategory.IN_KIND_GIFT] == {
            BenefitType.IN_KIND,
        }
        assert VALID_BENEFIT_MAPPING[BenefitCategory.VOUCHER] == {
            BenefitType.VOUCHER,
        }
        assert VALID_BENEFIT_MAPPING[BenefitCategory.SERVICE_WAIVER] == {
            BenefitType.SERVICE_WAIVER,
        }


class TestCalculationBaseAndValuationStatus:
    """Verify calculation base and valuation status Enums."""

    def test_calculation_base(self):
        assert CalculationBase.LISTED_PRICE.value == "LISTED_PRICE"
        assert CalculationBase.PRICE_AFTER_FIXED.value == "PRICE_AFTER_FIXED"
        assert len(CalculationBase) == 2

    def test_valuation_status(self):
        assert ValuationStatus.APPROVED.value == "APPROVED"
        assert ValuationStatus.PENDING.value == "PENDING"
        assert ValuationStatus.UNVALUED.value == "UNVALUED"
        assert len(ValuationStatus) == 3


class TestWorkflowAndDecisionStatus:
    """Verify quote workflow lifecycle and policy decision Enums."""

    def test_quote_workflow_status(self):
        expected_statuses = {
            "DRAFT",
            "VALIDATING",
            "CALCULATING",
            "READY_FOR_REVIEW",
            "APPROVED",
            "REJECTED",
            "ABSTAINED",
            "BLOCKED",
            "PDF_ISSUED",
            "SUPERSEDED",
        }
        actual_statuses = {s.value for s in QuoteWorkflowStatus}
        assert actual_statuses == expected_statuses

    def test_policy_decision_status(self):
        assert len(PolicyDecisionStatus) == 4
        assert PolicyDecisionStatus.ELIGIBLE.value == "ELIGIBLE"
        assert PolicyDecisionStatus.NOT_ELIGIBLE.value == "NOT_ELIGIBLE"
        assert PolicyDecisionStatus.CONFLICT.value == "CONFLICT"
        assert PolicyDecisionStatus.AMBIGUOUS.value == "AMBIGUOUS"

    def test_calculation_status(self):
        assert CalculationStatus.VALID.value == "VALID"
        assert CalculationStatus.NOT_RUN.value == "NOT_RUN"
        assert CalculationStatus.CALCULATION_FAILED.value == "CALCULATION_FAILED"
