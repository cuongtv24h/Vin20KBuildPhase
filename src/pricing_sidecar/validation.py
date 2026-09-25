"""Financial Validation Gate and Sanity Checks Engine.

FCS v2.6 Reference: Section 9 (Cổng kiểm duyệt Sanity Gate)
TD-4.1 Reference: Section 3.2 (Hardened Worker Sanity Verification)
TD-4.4 Reference: Section 3.3 (Financial Sanity Failed Error 422 & Tool Contract)
Implement Plan Detail Reference: Section 7.3 (D2-3 Financial Validation Gate)
"""

from decimal import Decimal
from typing import Any

from pydantic import Field

from src.pricing_sidecar.arithmetic import (
    assert_no_float,
    forbid_float,
    round_vnd,
    to_decimal,
)
from src.pricing_sidecar.contracts import (
    AntiFloatBaseModel,
    CalculationStatus,
    PricingCalculationOutput,
    ScenarioCalculationResult,
    ScenarioType,
    ValidationReport,
)

# ---------------------------------------------------------------------------
# Sanity Invariant Codes & Error Identifiers
# ---------------------------------------------------------------------------
INV_FIN_01: str = "INV-FIN-01: Net Price Bounds (0 < Net <= Listed)"
INV_FIN_02: str = "INV-FIN-02: Dual Discount Cap Compliance (Rate <= 35%, Total <= 40%)"
INV_FIN_03: str = "INV-FIN-03: VAT & KPBT Policy Snapshot Consistency"
INV_FIN_04: str = "INV-FIN-04: Contract Price Exact Sum (Contract == Net + VAT + KPBT)"
INV_FIN_05: str = "INV-FIN-05: Cashflow Reconciliation Completeness (Sum Schedule == Contract)"
INV_FIN_06: str = "INV-FIN-06: Non-negative Amounts & Monotonic Schedule Timeline"

STANDARD_SANITY_INVARIANTS: list[str] = [
    INV_FIN_01,
    INV_FIN_02,
    INV_FIN_03,
    INV_FIN_04,
    INV_FIN_05,
    INV_FIN_06,
]

FINANCIAL_SANITY_FAILED_CODE: str = "FINANCIAL_SANITY_FAILED"


# ---------------------------------------------------------------------------
# Field-Level Error Detail Model (Task 3.2)
# ---------------------------------------------------------------------------
class SanityFieldErrorDetail(AntiFloatBaseModel):
    """Field-level error specification adhering to FCS §9 and TD-4.4."""

    code: str = Field(..., min_length=1, description="Unique sanity error code")
    field: str = Field(..., min_length=1, description="Field path or identifier causing failure")
    message: str = Field(..., min_length=1, description="Human-readable violation message")
    expected_vnd: int | None = Field(default=None, description="Expected amount in integer VND")
    actual_vnd: int | None = Field(default=None, description="Actual calculated amount in integer VND")
    expected_rate: Decimal | None = Field(default=None, description="Expected rate Decimal")
    actual_rate: Decimal | None = Field(default=None, description="Actual rate Decimal")
    scenario_type: ScenarioType | str | None = Field(default=None, description="Scenario identifier if applicable")


# ---------------------------------------------------------------------------
# Specialized Exception for Financial Sanity Gate (Task 3.2)
# ---------------------------------------------------------------------------
class FinancialSanityError(ValueError):
    """Exception raised when financial sanity checks fail in calculation outputs."""

    def __init__(
        self,
        message: str,
        field_errors: list[SanityFieldErrorDetail] | list[dict[str, Any]] | None = None,
        scenario_type: ScenarioType | str | None = None,
    ) -> None:
        super().__init__(message)
        self.error_code: str = FINANCIAL_SANITY_FAILED_CODE
        self.status_code: int = 422
        self.scenario_type = scenario_type
        self.field_errors: list[SanityFieldErrorDetail] = []
        if field_errors:
            for item in field_errors:
                if isinstance(item, SanityFieldErrorDetail):
                    self.field_errors.append(item)
                elif isinstance(item, dict):
                    self.field_errors.append(SanityFieldErrorDetail(**item))

    def to_envelope(self) -> dict[str, Any]:
        """Convert into standard field-level error envelope format."""
        return {
            "valid": False,
            "error_code": self.error_code,
            "status_code": self.status_code,
            "message": str(self),
            "errors": [err.model_dump(exclude_none=True) for err in self.field_errors],
        }


# ---------------------------------------------------------------------------
# Core Scenario Sanity Check Function (Task 3.1 & 3.2)
# ---------------------------------------------------------------------------
@forbid_float
def check_scenario_sanity(
    calc_result: ScenarioCalculationResult,
    listed_price_vnd: int | None = None,
    vat_rate: Decimal = Decimal("0.1000"),
    maintenance_fee_rate: Decimal = Decimal("0.0200"),
    max_discount_rate: Decimal = Decimal("0.3500"),
    max_total_discount_cap_rate: Decimal = Decimal("0.4000"),
) -> list[SanityFieldErrorDetail]:
    """Execute 6 Sanity Checks on a single ScenarioCalculationResult.

    Returns a list of SanityFieldErrorDetail violations found (empty if 100% valid).
    """
    assert_no_float(calc_result)
    assert_no_float(listed_price_vnd)
    assert_no_float(vat_rate)
    assert_no_float(maintenance_fee_rate)
    assert_no_float(max_discount_rate)
    assert_no_float(max_total_discount_cap_rate)

    errors: list[SanityFieldErrorDetail] = []
    sc_type = calc_result.scenario_type

    effective_listed_price = listed_price_vnd if listed_price_vnd is not None else calc_result.listed_price_vnd

    # -----------------------------------------------------------------------
    # 1. Sanity Check 1: Cận Giá Net (INV-FIN-01)
    # -----------------------------------------------------------------------
    if calc_result.net_price_before_vat <= 0:
        errors.append(
            SanityFieldErrorDetail(
                code="NET_PRICE_NON_POSITIVE",
                field="net_price_before_vat",
                message=f"SANITY_FAIL: Giá Net trước thuế ({calc_result.net_price_before_vat:,}đ) phải lớn hơn 0.",
                actual_vnd=calc_result.net_price_before_vat,
                scenario_type=sc_type,
            )
        )

    if effective_listed_price > 0 and calc_result.net_price_before_vat > effective_listed_price:
        errors.append(
            SanityFieldErrorDetail(
                code="NET_PRICE_EXCEEDS_LISTED",
                field="net_price_before_vat",
                message=(
                    f"SANITY_FAIL: Giá Net trước thuế ({calc_result.net_price_before_vat:,}đ) "
                    f"vượt quá giá niêm yết ({effective_listed_price:,}đ)."
                ),
                expected_vnd=effective_listed_price,
                actual_vnd=calc_result.net_price_before_vat,
                scenario_type=sc_type,
            )
        )

    # -----------------------------------------------------------------------
    # 2. Sanity Check 2: Dual Discount Cap Compliance (INV-FIN-02)
    # -----------------------------------------------------------------------
    if calc_result.total_discount_rate > max_discount_rate:
        errors.append(
            SanityFieldErrorDetail(
                code="PERCENTAGE_DISCOUNT_CAP_EXCEEDED",
                field="total_discount_rate",
                message=(
                    f"SANITY_FAIL: Tổng tỷ lệ chiết khấu {calc_result.total_discount_rate} "
                    f"vượt trần tỷ lệ cho phép {max_discount_rate}."
                ),
                expected_rate=max_discount_rate,
                actual_rate=calc_result.total_discount_rate,
                scenario_type=sc_type,
            )
        )

    total_discount_vnd = calc_result.fixed_discount_vnd + calc_result.percentage_discount_vnd
    max_total_allowed_vnd = round_vnd(to_decimal(effective_listed_price) * max_total_discount_cap_rate)
    if total_discount_vnd > max_total_allowed_vnd:
        errors.append(
            SanityFieldErrorDetail(
                code="TOTAL_DISCOUNT_CAP_EXCEEDED",
                field="total_discount_vnd",
                message=(
                    f"SANITY_FAIL: Tổng số tiền chiết khấu ({total_discount_vnd:,}đ) "
                    f"vượt trần tổng tiền cho phép ({max_total_allowed_vnd:,}đ)."
                ),
                expected_vnd=max_total_allowed_vnd,
                actual_vnd=total_discount_vnd,
                scenario_type=sc_type,
            )
        )

    # -----------------------------------------------------------------------
    # 3. Sanity Check 3: Nhất quán Thuế GTGT VAT & Phí bảo trì KPBT (INV-FIN-03)
    # -----------------------------------------------------------------------
    expected_vat = round_vnd(to_decimal(calc_result.net_price_before_vat) * vat_rate)
    if calc_result.vat_amount != expected_vat:
        errors.append(
            SanityFieldErrorDetail(
                code="VAT_AMOUNT_MISMATCH",
                field="vat_amount",
                message=(
                    f"SANITY_FAIL: Thuế VAT sai lệch: {calc_result.vat_amount:,}đ "
                    f"vs kỳ vọng {expected_vat:,}đ theo tỷ lệ {vat_rate}."
                ),
                expected_vnd=expected_vat,
                actual_vnd=calc_result.vat_amount,
                expected_rate=vat_rate,
                scenario_type=sc_type,
            )
        )

    expected_kpbt = round_vnd(to_decimal(calc_result.net_price_before_vat) * maintenance_fee_rate)
    if calc_result.maintenance_fee_amount != expected_kpbt:
        errors.append(
            SanityFieldErrorDetail(
                code="KPBT_AMOUNT_MISMATCH",
                field="maintenance_fee_amount",
                message=(
                    f"SANITY_FAIL: Phí KPBT sai lệch: {calc_result.maintenance_fee_amount:,}đ "
                    f"vs kỳ vọng {expected_kpbt:,}đ theo tỷ lệ {maintenance_fee_rate}."
                ),
                expected_vnd=expected_kpbt,
                actual_vnd=calc_result.maintenance_fee_amount,
                expected_rate=maintenance_fee_rate,
                scenario_type=sc_type,
            )
        )

    # -----------------------------------------------------------------------
    # 4. Sanity Check 4: Cân bằng Tổng giá trị HĐMB (INV-FIN-04)
    # -----------------------------------------------------------------------
    expected_contract = calc_result.net_price_before_vat + expected_vat + expected_kpbt
    if calc_result.final_contract_price != expected_contract:
        errors.append(
            SanityFieldErrorDetail(
                code="CONTRACT_PRICE_MISMATCH",
                field="final_contract_price",
                message=(
                    f"SANITY_FAIL: Tổng giá trị HĐMB ({calc_result.final_contract_price:,}đ) "
                    f"không bằng Net + VAT + KPBT ({expected_contract:,}đ)."
                ),
                expected_vnd=expected_contract,
                actual_vnd=calc_result.final_contract_price,
                scenario_type=sc_type,
            )
        )

    # -----------------------------------------------------------------------
    # 5. Sanity Check 5: Cân bằng Dòng tiền Lập lịch (INV-FIN-05)
    # -----------------------------------------------------------------------
    if calc_result.cashflow_schedule:
        sum_schedule_gross = sum(item.installment_gross_obligation_vnd for item in calc_result.cashflow_schedule)
        if sum_schedule_gross != calc_result.final_contract_price:
            errors.append(
                SanityFieldErrorDetail(
                    code="PAYMENT_SCHEDULE_SUM_MISMATCH",
                    field="cashflow_schedule",
                    message=(
                        f"SANITY_FAIL: Tổng các đợt thanh toán ({sum_schedule_gross:,}đ) "
                        f"lệch với Tổng giá HĐMB ({calc_result.final_contract_price:,}đ)."
                    ),
                    expected_vnd=calc_result.final_contract_price,
                    actual_vnd=sum_schedule_gross,
                    scenario_type=sc_type,
                )
            )

        for idx, item in enumerate(calc_result.cashflow_schedule):
            # 5a. Gross obligation must equal equity + bank + kpbt
            expected_inst_gross = (
                item.customer_equity_paid_vnd + item.bank_disbursement_vnd + item.maintenance_fee_paid_vnd
            )
            if item.installment_gross_obligation_vnd != expected_inst_gross:
                errors.append(
                    SanityFieldErrorDetail(
                        code="INSTALLMENT_GROSS_MISMATCH",
                        field=f"cashflow_schedule[{idx}].installment_gross_obligation_vnd",
                        message=(
                            f"SANITY_FAIL: Đợt {item.installment_number}: nghĩa vụ đợt "
                            f"({item.installment_gross_obligation_vnd:,}đ) không khớp tổng "
                            f"equity + bank + kpbt ({expected_inst_gross:,}đ)."
                        ),
                        expected_vnd=expected_inst_gross,
                        actual_vnd=item.installment_gross_obligation_vnd,
                        scenario_type=sc_type,
                    )
                )

            # 5b. Additional cash due must equal equity - deposit + kpbt
            expected_additional_cash = (
                item.customer_equity_paid_vnd - item.deposit_credited_vnd + item.maintenance_fee_paid_vnd
            )
            if item.installment_additional_cash_due_vnd != expected_additional_cash:
                errors.append(
                    SanityFieldErrorDetail(
                        code="INSTALLMENT_CASH_DUE_MISMATCH",
                        field=f"cashflow_schedule[{idx}].installment_additional_cash_due_vnd",
                        message=(
                            f"SANITY_FAIL: Đợt {item.installment_number}: tiền nộp thêm thực tế "
                            f"({item.installment_additional_cash_due_vnd:,}đ) không khớp với "
                            f"equity - cọc + kpbt ({expected_additional_cash:,}đ)."
                        ),
                        expected_vnd=expected_additional_cash,
                        actual_vnd=item.installment_additional_cash_due_vnd,
                        scenario_type=sc_type,
                    )
                )

    # -----------------------------------------------------------------------
    # 6. Sanity Check 6: Không có số tiền âm & Ngày tăng đơn điệu (INV-FIN-06)
    # -----------------------------------------------------------------------
    # 6a. Check non-negative top-level amounts
    if calc_result.fixed_discount_vnd < 0:
        errors.append(
            SanityFieldErrorDetail(
                code="NEGATIVE_AMOUNT_DETECTED",
                field="fixed_discount_vnd",
                message="SANITY_FAIL: Chiết khấu cố định không được âm.",
                actual_vnd=calc_result.fixed_discount_vnd,
                scenario_type=sc_type,
            )
        )

    if calc_result.percentage_discount_vnd < 0:
        errors.append(
            SanityFieldErrorDetail(
                code="NEGATIVE_AMOUNT_DETECTED",
                field="percentage_discount_vnd",
                message="SANITY_FAIL: Chiết khấu tỷ lệ không được âm.",
                actual_vnd=calc_result.percentage_discount_vnd,
                scenario_type=sc_type,
            )
        )

    if calc_result.vat_amount < 0:
        errors.append(
            SanityFieldErrorDetail(
                code="NEGATIVE_AMOUNT_DETECTED",
                field="vat_amount",
                message="SANITY_FAIL: Thuế VAT không được âm.",
                actual_vnd=calc_result.vat_amount,
                scenario_type=sc_type,
            )
        )

    if calc_result.maintenance_fee_amount < 0:
        errors.append(
            SanityFieldErrorDetail(
                code="NEGATIVE_AMOUNT_DETECTED",
                field="maintenance_fee_amount",
                message="SANITY_FAIL: Phí KPBT không được âm.",
                actual_vnd=calc_result.maintenance_fee_amount,
                scenario_type=sc_type,
            )
        )

    # 6b. Check non-negative and monotonicity in cashflow schedule
    if calc_result.cashflow_schedule:
        for idx, item in enumerate(calc_result.cashflow_schedule):
            # Check amounts >= 0
            for field_name, amount in [
                ("installment_gross_obligation_vnd", item.installment_gross_obligation_vnd),
                ("customer_equity_paid_vnd", item.customer_equity_paid_vnd),
                ("bank_disbursement_vnd", item.bank_disbursement_vnd),
                ("maintenance_fee_paid_vnd", item.maintenance_fee_paid_vnd),
                ("deposit_credited_vnd", item.deposit_credited_vnd),
                ("installment_additional_cash_due_vnd", item.installment_additional_cash_due_vnd),
            ]:
                if amount < 0:
                    errors.append(
                        SanityFieldErrorDetail(
                            code="NEGATIVE_AMOUNT_DETECTED",
                            field=f"cashflow_schedule[{idx}].{field_name}",
                            message=f"SANITY_FAIL: Đợt {item.installment_number}: {field_name} không được âm ({amount:,}đ).",
                            actual_vnd=amount,
                            scenario_type=sc_type,
                        )
                    )

            # Check deposit credit cannot exceed customer equity paid
            if item.deposit_credited_vnd > item.customer_equity_paid_vnd:
                errors.append(
                    SanityFieldErrorDetail(
                        code="DEPOSIT_CREDIT_INVALID",
                        field=f"cashflow_schedule[{idx}].deposit_credited_vnd",
                        message=(
                            f"SANITY_FAIL: Đợt {item.installment_number}: tiền cọc kết chuyển "
                            f"({item.deposit_credited_vnd:,}đ) vượt quá vốn tự có "
                            f"({item.customer_equity_paid_vnd:,}đ)."
                        ),
                        expected_vnd=item.customer_equity_paid_vnd,
                        actual_vnd=item.deposit_credited_vnd,
                        scenario_type=sc_type,
                    )
                )

            # Monotonicity check against previous installment
            if idx > 0:
                prev_item = calc_result.cashflow_schedule[idx - 1]
                if item.installment_number <= prev_item.installment_number:
                    errors.append(
                        SanityFieldErrorDetail(
                            code="SCHEDULE_NUMBER_NON_MONOTONIC",
                            field=f"cashflow_schedule[{idx}].installment_number",
                            message=(
                                f"SANITY_FAIL: Đợt {item.installment_number} không tăng đơn điệu "
                                f"so với đợt trước ({prev_item.installment_number})."
                            ),
                            scenario_type=sc_type,
                        )
                    )
                if item.due_date < prev_item.due_date:
                    errors.append(
                        SanityFieldErrorDetail(
                            code="SCHEDULE_DATE_NON_MONOTONIC",
                            field=f"cashflow_schedule[{idx}].due_date",
                            message=(
                                f"SANITY_FAIL: Đợt {item.installment_number}: ngày đến hạn "
                                f"({item.due_date}) sớm hơn đợt trước ({prev_item.due_date})."
                            ),
                            scenario_type=sc_type,
                        )
                    )
                if hasattr(item, "days_from_deposit") and hasattr(prev_item, "days_from_deposit"):
                    if item.days_from_deposit < prev_item.days_from_deposit:
                        errors.append(
                            SanityFieldErrorDetail(
                                code="SCHEDULE_DATE_NON_MONOTONIC",
                                field=f"cashflow_schedule[{idx}].days_from_deposit",
                                message=(
                                    f"SANITY_FAIL: Đợt {item.installment_number}: days_from_deposit "
                                    f"({item.days_from_deposit}) nhỏ hơn đợt trước ({prev_item.days_from_deposit})."
                                ),
                                scenario_type=sc_type,
                            )
                        )

    return errors


# ---------------------------------------------------------------------------
# High-Level Gate Validation Functions (Task 3.1 & 3.2)
# ---------------------------------------------------------------------------
@forbid_float
def validate_scenario_calculation(
    calc_result: ScenarioCalculationResult,
    listed_price_vnd: int | None = None,
    vat_rate: Decimal = Decimal("0.1000"),
    maintenance_fee_rate: Decimal = Decimal("0.0200"),
    max_discount_rate: Decimal = Decimal("0.3500"),
    max_total_discount_cap_rate: Decimal = Decimal("0.4000"),
    raise_on_error: bool = False,
) -> ValidationReport:
    """Validate a single ScenarioCalculationResult against 6 Sanity Checks.

    If raise_on_error is True, raises FinancialSanityError when violations exist.
    Otherwise returns a ValidationReport model with status VALID or CALCULATION_FAILED.
    """
    assert_no_float(calc_result)
    assert_no_float(listed_price_vnd)
    assert_no_float(vat_rate)
    assert_no_float(maintenance_fee_rate)
    assert_no_float(max_discount_rate)
    assert_no_float(max_total_discount_cap_rate)

    errors = check_scenario_sanity(
        calc_result=calc_result,
        listed_price_vnd=listed_price_vnd,
        vat_rate=vat_rate,
        maintenance_fee_rate=maintenance_fee_rate,
        max_discount_rate=max_discount_rate,
        max_total_discount_cap_rate=max_total_discount_cap_rate,
    )

    if errors:
        first_error_msg = errors[0].message
        full_error_msg = (
            f"FINANCIAL_SANITY_FAILED: Phát hiện {len(errors)} vi phạm kiểm duyệt tài chính. "
            f"Lỗi đầu tiên: {first_error_msg}"
        )
        if raise_on_error:
            raise FinancialSanityError(
                message=full_error_msg,
                field_errors=errors,
                scenario_type=calc_result.scenario_type,
            )

        return ValidationReport(
            is_valid=False,
            status=CalculationStatus.CALCULATION_FAILED,
            invariants_checked=list(STANDARD_SANITY_INVARIANTS),
            error_message=full_error_msg,
            field_errors=[err.model_dump(exclude_none=True) for err in errors],
        )

    return ValidationReport(
        is_valid=True,
        status=CalculationStatus.VALID,
        invariants_checked=list(STANDARD_SANITY_INVARIANTS),
        error_message=None,
        field_errors=[],
    )


@forbid_float
def validate_pricing_results(
    calc_target: ScenarioCalculationResult | PricingCalculationOutput | list[ScenarioCalculationResult],
    listed_price_vnd: int | None = None,
    vat_rate: Decimal = Decimal("0.1000"),
    maintenance_fee_rate: Decimal = Decimal("0.0200"),
    max_discount_rate: Decimal = Decimal("0.3500"),
    max_total_discount_cap_rate: Decimal = Decimal("0.4000"),
    raise_on_error: bool = False,
) -> ValidationReport:
    """Top-level validation tool conforming to TD-4.4 `validate_pricing_results`.

    Accepts a single ScenarioCalculationResult, a list of scenarios, or a
    complete PricingCalculationOutput envelope.
    """
    assert_no_float(calc_target)
    assert_no_float(listed_price_vnd)
    assert_no_float(vat_rate)
    assert_no_float(maintenance_fee_rate)
    assert_no_float(max_discount_rate)
    assert_no_float(max_total_discount_cap_rate)

    scenarios: list[ScenarioCalculationResult] = []
    effective_listed = listed_price_vnd

    if isinstance(calc_target, ScenarioCalculationResult):
        scenarios = [calc_target]
    elif isinstance(calc_target, PricingCalculationOutput):
        scenarios = calc_target.scenario_results
    elif isinstance(calc_target, list):
        scenarios = calc_target
    else:
        raise TypeError(
            f"calc_target không hợp lệ: kỳ vọng ScenarioCalculationResult, "
            f"PricingCalculationOutput hoặc list, nhận được {type(calc_target).__name__}"
        )

    all_errors: list[SanityFieldErrorDetail] = []
    for sc in scenarios:
        sc_errors = check_scenario_sanity(
            calc_result=sc,
            listed_price_vnd=effective_listed,
            vat_rate=vat_rate,
            maintenance_fee_rate=maintenance_fee_rate,
            max_discount_rate=max_discount_rate,
            max_total_discount_cap_rate=max_total_discount_cap_rate,
        )
        all_errors.extend(sc_errors)

    if all_errors:
        first_error_msg = all_errors[0].message
        full_error_msg = (
            f"FINANCIAL_SANITY_FAILED: Phát hiện {len(all_errors)} vi phạm kiểm duyệt tài chính "
            f"trên {len(scenarios)} kịch bản. Lỗi đầu tiên: {first_error_msg}"
        )
        if raise_on_error:
            raise FinancialSanityError(
                message=full_error_msg,
                field_errors=all_errors,
            )

        return ValidationReport(
            is_valid=False,
            status=CalculationStatus.CALCULATION_FAILED,
            invariants_checked=list(STANDARD_SANITY_INVARIANTS),
            error_message=full_error_msg,
            field_errors=[err.model_dump(exclude_none=True) for err in all_errors],
        )

    return ValidationReport(
        is_valid=True,
        status=CalculationStatus.VALID,
        invariants_checked=list(STANDARD_SANITY_INVARIANTS),
        error_message=None,
        field_errors=[],
    )
