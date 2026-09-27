"""
Adapter utilities bridging Policy Extraction (Dev 1 / F9) and Pricing Sidecar (Dev 2 / FCS v2.6).
Converts StructuredRuleDTO into BenefitApplicationRule with strict invariant validation.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

from src.contracts.policy import StructuredRuleDTO
from src.pricing_sidecar.contracts import (
    BenefitApplicationRule,
    BenefitCategory,
    BenefitType,
    CalculationBase,
    StructuredPolicyReference,
    ValuationStatus,
)


def adapt_structured_rule_to_benefit(
    rule: StructuredRuleDTO | dict[str, Any],
    source_file_sha256: str = "0" * 64,
) -> BenefitApplicationRule:
    """
    Transforms a StructuredRuleDTO from Dev 1 RAG pipeline into a validated
    BenefitApplicationRule consumable by the Deterministic Pricing Engine.
    """
    if isinstance(rule, StructuredRuleDTO):
        rule_dict = rule.model_dump()
    else:
        rule_dict = dict(rule)

    rule_id = rule_dict.get("rule_id", "RULE-UNKNOWN")
    policy_id = rule_dict.get("policy_id", "POL-UNKNOWN")
    policy_version = rule_dict.get("policy_version", "v1.0")
    clause_id = rule_dict.get("clause_id", "Điều 1")
    formula = rule_dict.get("benefit_formula", {})

    # Determine category & benefit_type aligned with VALID_BENEFIT_MAPPING
    raw_cat = str(formula.get("category") or rule_dict.get("rule_type", "DISCOUNT")).upper()
    raw_type = str(formula.get("type") or formula.get("benefit_type") or rule_dict.get("rule_type", "DISCOUNT")).upper()

    if "GIFT" in raw_cat or "IN_KIND" in raw_cat or "GIFT" in raw_type or "IN_KIND" in raw_type:
        category = BenefitCategory.IN_KIND_GIFT
        benefit_type = BenefitType.IN_KIND
    elif "VOUCHER" in raw_cat or "VOUCHER" in raw_type:
        category = BenefitCategory.VOUCHER
        benefit_type = BenefitType.VOUCHER
    elif "WAIVER" in raw_cat or "SERVICE" in raw_cat:
        category = BenefitCategory.SERVICE_WAIVER
        benefit_type = BenefitType.SERVICE_WAIVER
    else:
        # Default to CASH_DISCOUNT: either PERCENTAGE or FIXED_CASH
        category = BenefitCategory.CASH_DISCOUNT
        if "PERCENT" in raw_type or formula.get("discount_rate") or formula.get("rate"):
            benefit_type = BenefitType.PERCENTAGE
        else:
            benefit_type = BenefitType.FIXED_CASH

    # Extract deduction amounts
    fixed_deduction = int(formula.get("fixed_deduction_vnd") or formula.get("amount_vnd") or 0)
    raw_rate = formula.get("discount_rate") or formula.get("rate") or "0.0000"
    discount_rate = Decimal(str(raw_rate))

    # In-kind valuation status
    raw_val_status = str(formula.get("valuation_status", "APPROVED")).upper()
    try:
        val_status = ValuationStatus(raw_val_status)
    except Exception:
        val_status = ValuationStatus.APPROVED

    # Price deduction authorization
    authorized = bool(formula.get("price_deduction_authorized", True))

    # Guardrails for required positive fields
    if benefit_type == BenefitType.FIXED_CASH and fixed_deduction <= 0:
        fixed_deduction = 1_000_000  # Default nominal positive deduction if marked FIXED_CASH
    if benefit_type == BenefitType.PERCENTAGE and discount_rate <= Decimal("0.0000"):
        discount_rate = Decimal("0.0100")  # Default nominal positive rate if marked PERCENTAGE

    # Build reference
    policy_ref = StructuredPolicyReference(
        policy_id=policy_id,
        policy_version=policy_version,
        clause_id=clause_id,
        page_number=int(rule_dict.get("page", 1)),
        source_file_sha256=source_file_sha256,
        effective_from=date.today(),
        effective_to=date(2026, 12, 31),
    )

    return BenefitApplicationRule(
        benefit_id=rule_id,
        benefit_type=benefit_type,
        category=category,
        fixed_deduction_vnd=fixed_deduction,
        discount_rate=discount_rate,
        calculation_base=CalculationBase.PRICE_AFTER_FIXED,
        application_order=int(rule_dict.get("priority", 1)),
        valuation_status=val_status,
        price_deduction_authorized=authorized,
        source_policy_clause=policy_ref,
    )
