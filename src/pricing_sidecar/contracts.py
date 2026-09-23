"""Domain Contracts, Enums, and Data Schemas for Financial Calculation.

FCS v2.6 Reference: Sections 3, 4, 7, 8, 9
TD-4.2 Reference: Section 2 (Domain-Driven Design)
TD-4.4 Reference: Section 4 (Tool & Governance Contracts)
"""

from datetime import date
from decimal import Decimal
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from src.pricing_sidecar.arithmetic import assert_no_float


class ScenarioType(StrEnum):
    """Canonical scenario types specified in FCS v2.6."""

    STANDARD_PROGRESS = "STANDARD_PROGRESS"
    EARLY_95 = "EARLY_95"
    BANK_LOAN_HTLS = "BANK_LOAN_HTLS"

    @property
    def canonical_code(self) -> str:
        """Return standard policy canonical code (e.g. PA-CHUDONG)."""
        return SCENARIO_ALIAS_MAP.get(self, self.value)


class OptimizationObjective(StrEnum):
    """5 Business Optimization Objectives (PRD v2.3 / FCS v2.6 §7)."""

    MIN_NET_PRICE = "MIN_NET_PRICE"
    MIN_CONTRACT_PRICE = "MIN_CONTRACT_PRICE"
    MIN_INITIAL_OUTFLOW = "MIN_INITIAL_OUTFLOW"
    MIN_CASH_OUTFLOW_TO_HANDOVER = "MIN_CASH_OUTFLOW_TO_HANDOVER"
    MAX_BENEFIT_VALUE = "MAX_BENEFIT_VALUE"


class BenefitCategory(StrEnum):
    """Commercial benefit category classification."""

    CASH_DISCOUNT = "CASH_DISCOUNT"      # Chiết khấu tiền mặt trực tiếp
    IN_KIND_GIFT = "IN_KIND_GIFT"        # Quà tặng hiện vật (Vàng SJC, Nội thất, Xe điện)
    VOUCHER = "VOUCHER"                  # Phiếu mua hàng / Voucher
    SERVICE_WAIVER = "SERVICE_WAIVER"    # Miễn phí dịch vụ quản lý vận hành


class BenefitType(StrEnum):
    """Mechanism by which a benefit is applied into calculations."""

    FIXED_CASH = "FIXED_CASH"            # Giảm trừ tiền mặt cố định vào Base_1
    PERCENTAGE = "PERCENTAGE"            # Chiết khấu tỷ lệ % cộng dồn (Additive)
    IN_KIND = "IN_KIND"                  # Quà tặng hiện vật
    VOUCHER = "VOUCHER"                  # Phiếu ưu đãi
    SERVICE_WAIVER = "SERVICE_WAIVER"    # Miễn phí quản lý dịch vụ


class CalculationBase(StrEnum):
    """Base price on which percentage discount is applied."""

    LISTED_PRICE = "LISTED_PRICE"
    PRICE_AFTER_FIXED = "PRICE_AFTER_FIXED"


class ValuationStatus(StrEnum):
    """Valuation status for in-kind gifts and non-cash incentives."""

    APPROVED = "APPROVED"       # Đã có chứng thư/hóa đơn định giá chính thức -> Tính vào benefit value & objective
    PENDING = "PENDING"         # Đang chờ thẩm định -> Hiển thị ghi chú, KHÔNG tính vào objective
    UNVALUED = "UNVALUED"       # Quà tặng thuần túy, chưa có giá trị quy đổi tiền tệ


class QuoteWorkflowStatus(StrEnum):
    """State machine status for Commercial Quotes (FCS §3 / TD-4.4)."""

    DRAFT = "DRAFT"
    VALIDATING = "VALIDATING"
    CALCULATING = "CALCULATING"
    READY_FOR_REVIEW = "READY_FOR_REVIEW"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    ABSTAINED = "ABSTAINED"
    BLOCKED = "BLOCKED"              # Phong tỏa do tranh chấp căn, double-booking
    PDF_ISSUED = "PDF_ISSUED"
    SUPERSEDED = "SUPERSEDED"        # Phiên bản cũ đã bị thay thế bởi phiên bản mới


class PolicyDecisionStatus(StrEnum):
    """Policy eligibility evaluation decision status."""

    ELIGIBLE = "ELIGIBLE"
    NOT_ELIGIBLE = "NOT_ELIGIBLE"
    CONFLICT = "CONFLICT"
    AMBIGUOUS = "AMBIGUOUS"


class CalculationStatus(StrEnum):
    """Status of the arithmetic calculation run."""

    VALID = "VALID"
    NOT_RUN = "NOT_RUN"
    CALCULATION_FAILED = "CALCULATION_FAILED"


# ---------------------------------------------------------------------------
# Business Rules and Mapping Constants
# ---------------------------------------------------------------------------
SCENARIO_ALIAS_MAP: dict[ScenarioType, str] = {
    ScenarioType.STANDARD_PROGRESS: "PA-CHUDONG",
    ScenarioType.EARLY_95: "PA-NHANH",
    ScenarioType.BANK_LOAN_HTLS: "PA-VAY",
}

CANONICAL_SCENARIO_ORDER: dict[ScenarioType, int] = {
    ScenarioType.STANDARD_PROGRESS: 1,
    ScenarioType.EARLY_95: 2,
    ScenarioType.BANK_LOAN_HTLS: 3,
}

VALID_BENEFIT_MAPPING: dict[BenefitCategory, set[BenefitType]] = {
    BenefitCategory.CASH_DISCOUNT: {BenefitType.FIXED_CASH, BenefitType.PERCENTAGE},
    BenefitCategory.IN_KIND_GIFT: {BenefitType.IN_KIND},
    BenefitCategory.VOUCHER: {BenefitType.VOUCHER},
    BenefitCategory.SERVICE_WAIVER: {BenefitType.SERVICE_WAIVER},
}


# ---------------------------------------------------------------------------
# Base Schema with Anti-Float Guard
# ---------------------------------------------------------------------------
class AntiFloatBaseModel(BaseModel):
    """Base Pydantic model enforcing zero-float policy at deserialization."""

    model_config = ConfigDict(validate_assignment=True)

    @model_validator(mode="before")
    @classmethod
    def check_zero_float(cls, data: Any) -> Any:
        assert_no_float(data)
        return data


# ---------------------------------------------------------------------------
# Input Contracts conforming to FCS v2.6 §3 & §4
# ---------------------------------------------------------------------------
class StructuredPolicyReference(AntiFloatBaseModel):
    """Immutable cryptographic coordinate linking calculations to approved legal policy."""

    policy_id: str = Field(..., min_length=1, description="Policy unique identifier e.g. POL-2026-VLF-GEN")
    policy_version: str = Field(..., min_length=1, description="Policy release version e.g. v2.6")
    clause_id: str = Field(..., min_length=1, description="Specific clause identifier e.g. Điều 4.2 Khoản 1")
    page_number: int = Field(default=1, ge=1, description="Page number in approved source document")
    source_file_sha256: str = Field(
        ...,
        min_length=64,
        max_length=64,
        pattern=r"^[0-9a-fA-F]{64}$",
        description="Immutable SHA-256 hash of legal policy PDF/Markdown file",
    )
    effective_from: date = Field(..., description="Start date of policy validity")
    effective_to: date = Field(..., description="End date of policy validity")

    @model_validator(mode="after")
    def validate_effective_dates(self) -> "StructuredPolicyReference":
        if self.effective_from > self.effective_to:
            raise ValueError(
                f"Policy effective_from ({self.effective_from}) cannot be after effective_to ({self.effective_to})."
            )
        return self


class InstallmentRule(AntiFloatBaseModel):
    """Configuration rule for a single milestone/installment payment in schedule."""

    installment_number: int = Field(..., ge=1, le=30, description="Thứ tự đợt thanh toán (1..30)")
    milestone_name: str = Field(..., min_length=1, description="Tên sự kiện / mốc thanh toán")
    days_from_deposit: int = Field(..., ge=0, description="Số ngày tính từ ngày đặt cọc (deposit_date)")

    customer_equity_ratio: Decimal = Field(default=Decimal("0.0000"), ge=0, le=1)
    bank_disbursement_ratio: Decimal = Field(default=Decimal("0.0000"), ge=0, le=1)
    maintenance_fee_ratio: Decimal = Field(default=Decimal("0.0000"), ge=0, le=1)

    is_handover: bool = Field(default=False, description="Đánh dấu mốc bàn giao nhà (thu 100% KPBT)")
    is_reconciliation: bool = Field(default=False, description="Đánh dấu mốc quyết toán cuối (triệt tiêu sai số lẻ)")

    @property
    def payment_ratio(self) -> Decimal:
        """Tổng tỷ lệ thanh toán tiền nhà (Equity + Bank disbursement)."""
        return self.customer_equity_ratio + self.bank_disbursement_ratio


class PaymentScenarioConfig(AntiFloatBaseModel):
    """Comprehensive payment scenario schedule and funding policy configuration."""

    scenario_type: ScenarioType
    scenario_name: str = Field(..., min_length=1)
    installment_rules: list[InstallmentRule]
    deposit_amount_vnd: int = Field(default=100_000_000, ge=0, description="Tiền cọc thực tế đã nộp")
    bank_financing_rate: Decimal = Field(default=Decimal("0.0000"), ge=0, le=1)
    customer_equity_rate: Decimal = Field(default=Decimal("1.0000"), ge=0, le=1)
    interest_support_months: int | None = Field(default=None, ge=0)
    principal_grace_months: int | None = Field(default=None, ge=0)
    policy_reference: StructuredPolicyReference | None = None

    @model_validator(mode="after")
    def validate_scenario_configuration(self) -> "PaymentScenarioConfig":
        # 1. Kiểm tra tổng tỷ lệ vốn
        total_funding_rate = self.bank_financing_rate + self.customer_equity_rate
        if total_funding_rate != Decimal("1.0000"):
            raise ValueError(
                f"Scenario {self.scenario_type}: Tổng bank_financing_rate ({self.bank_financing_rate}) + "
                f"customer_equity_rate ({self.customer_equity_rate}) phải bằng 1.0000 (hiện tại: {total_funding_rate})."
            )

        rules = self.installment_rules
        if not rules:
            raise ValueError(f"Scenario {self.scenario_type}: Danh sách installment_rules không được rỗng.")

        # 2. Invariant Reconciliation: Đúng 1 đợt reconciliation
        recon_rules = [r for r in rules if r.is_reconciliation]
        if len(recon_rules) != 1:
            raise ValueError(
                f"Scenario {self.scenario_type}: Bắt buộc phải có DUY NHẤT 1 đợt reconciliation (tìm thấy {len(recon_rules)})."
            )

        # 3. Invariant Handover: Đúng 1 đợt bàn giao
        handover_rules = [r for r in rules if r.is_handover]
        if len(handover_rules) != 1:
            raise ValueError(
                f"Scenario {self.scenario_type}: Bắt buộc phải có DUY NHẤT 1 đợt bàn giao nhà (tìm thấy {len(handover_rules)})."
            )

        # 4. Invariant Installment Numbering: Tăng liên tục 1..N
        numbers = [r.installment_number for r in rules]
        expected_numbers = list(range(1, len(rules) + 1))
        if numbers != expected_numbers:
            raise ValueError(
                f"Scenario {self.scenario_type}: Thứ tự installment_number phải liên tục từ 1 đến {len(rules)}, hiện tại: {numbers}."
            )

        # 5. Invariant Timeline Monotonicity: Ngày đợt sau >= đợt trước
        days_seq = [r.days_from_deposit for r in rules]
        if days_seq != sorted(days_seq):
            raise ValueError(
                f"Scenario {self.scenario_type}: Tiến độ days_from_deposit phải đơn điệu không giảm."
            )

        # 6. Invariant Maintenance Fee: Toàn bộ 100% KPBT phải được thu (thông thường tại handover)
        total_kpbt_ratio = sum(r.maintenance_fee_ratio for r in rules)
        if total_kpbt_ratio != Decimal("1.0000"):
            raise ValueError(
                f"Scenario {self.scenario_type}: Tổng maintenance_fee_ratio phải bằng 1.0000 (hiện tại: {total_kpbt_ratio})."
            )

        # 7. Invariant Equity Allocation: Tổng vốn tự có các đợt không reconciliation phải <= customer_equity_rate
        non_recon_equity = sum(r.customer_equity_ratio for r in rules if not r.is_reconciliation)
        if non_recon_equity > self.customer_equity_rate:
            raise ValueError(
                f"Scenario {self.scenario_type}: Tổng vốn tự có các đợt trước ({non_recon_equity}) vượt quá trần cấu hình ({self.customer_equity_rate})."
            )

        # 8. Invariant Bank Allocation: Tổng ngân hàng giải ngân các đợt không reconciliation phải <= bank_financing_rate
        non_recon_bank = sum(r.bank_disbursement_ratio for r in rules if not r.is_reconciliation)
        if non_recon_bank > self.bank_financing_rate:
            raise ValueError(
                f"Scenario {self.scenario_type}: Tổng giải ngân ngân hàng ({non_recon_bank}) vượt quá trần cấu hình ({self.bank_financing_rate})."
            )

        return self


class BenefitApplicationRule(AntiFloatBaseModel):
    """Commercial policy incentive rule to apply into price deduction and accounting."""

    benefit_id: str = Field(..., min_length=1)
    benefit_type: BenefitType
    category: BenefitCategory
    fixed_deduction_vnd: int = Field(default=0, ge=0)
    discount_rate: Decimal = Field(default=Decimal("0.0000"), ge=0, le=1)
    calculation_base: CalculationBase = CalculationBase.PRICE_AFTER_FIXED
    application_order: int = Field(default=1, ge=1, description="Thứ tự ưu tiên áp dụng hạn mức và kiểm toán")
    valuation_status: ValuationStatus
    price_deduction_authorized: bool  # CHỈ ĐƯỢC PHÉP TRỪ GIÁ KHI ĐƯỢC CHÍNH SÁCH ỦY QUYỀN
    source_policy_clause: StructuredPolicyReference

    @model_validator(mode="after")
    def validate_benefit_fields(self) -> "BenefitApplicationRule":
        # 1. Ma trận tương thích Category - Type
        allowed_types = VALID_BENEFIT_MAPPING.get(self.category, set())
        if self.benefit_type not in allowed_types:
            raise ValueError(
                f"Benefit {self.benefit_id}: category '{self.category}' "
                f"không tương thích với benefit_type '{self.benefit_type}'. "
                f"Các type hợp lệ: {allowed_types}"
            )

        # 2. Nếu không được ủy quyền trừ giá thì cấm có số tiền trừ hoặc tỷ lệ chiết khấu
        if not self.price_deduction_authorized:
            if self.fixed_deduction_vnd > 0 or self.discount_rate > Decimal("0.0000"):
                raise ValueError(
                    f"Benefit {self.benefit_id}: price_deduction_authorized=False "
                    f"nhưng lại có fixed_deduction_vnd={self.fixed_deduction_vnd} hoặc discount_rate={self.discount_rate}."
                )

        # 3. FIXED_CASH bắt buộc số tiền > 0
        if self.benefit_type == BenefitType.FIXED_CASH and self.fixed_deduction_vnd <= 0:
            raise ValueError(f"Benefit {self.benefit_id}: FIXED_CASH yêu cầu fixed_deduction_vnd > 0.")

        # 4. PERCENTAGE bắt buộc discount_rate > 0
        if self.benefit_type == BenefitType.PERCENTAGE and self.discount_rate <= Decimal("0.0000"):
            raise ValueError(f"Benefit {self.benefit_id}: PERCENTAGE yêu cầu discount_rate > 0.")

        # 5. Quà tặng hiện vật chỉ được trừ giá khi có ValuationStatus.APPROVED
        if self.benefit_type == BenefitType.IN_KIND and self.price_deduction_authorized:
            if self.valuation_status != ValuationStatus.APPROVED:
                raise ValueError(
                    f"Benefit {self.benefit_id}: Quà hiện vật chỉ được trừ giá khi có ValuationStatus.APPROVED."
                )

        return self


class PricingCalculationInput(AntiFloatBaseModel):
    """Complete calculation input payload for Deterministic Pricing Engine."""

    unit_code: str = Field(..., min_length=1, description="Mã căn hộ e.g. A-12-05")
    deposit_date: date = Field(..., description="Ngày ký thỏa thuận đặt cọc")
    contract_signing_date: date = Field(..., description="Ngày ký Hợp đồng Mua bán chính thức")
    listed_price_vnd: int = Field(..., gt=0, description="Giá niêm yết chưa thuế VAT (P_listed)")
    deposit_amount_vnd: int = Field(default=100_000_000, ge=0, description="Tiền cọc thực tế đã nộp")
    resolved_policy_snapshot_id: str = Field(..., min_length=1)
    source_policy_hash: str = Field(..., min_length=1)
    approved_benefits: list[BenefitApplicationRule] = Field(default_factory=list)
    scenario_configs: list[PaymentScenarioConfig] = Field(default_factory=list)
    tax_vat_rate: Decimal = Field(default=Decimal("0.1000"), ge=0, le=1)
    maintenance_fee_rate: Decimal = Field(default=Decimal("0.0200"), ge=0, le=1)
    max_discount_rate: Decimal = Field(default=Decimal("0.3500"), ge=0, le=1)
    max_total_discount_cap_rate: Decimal = Field(default=Decimal("0.4000"), ge=0, le=1)
    calculation_spec_version: str = Field(default="2.6")
    quote_id: str | None = None
    quote_version: int | None = None
    selected_scenarios: list[str] = Field(
        default_factory=lambda: ["PA-CHUDONG", "PA-NHANH", "PA-VAY"]
    )
    tiebreak_rule_id: str = Field(default="TB-RULE-2026-CHUDONG-V1")

    @model_validator(mode="after")
    def validate_dates(self) -> "PricingCalculationInput":
        if self.contract_signing_date < self.deposit_date:
            raise ValueError(
                f"Ngày ký HĐMB ({self.contract_signing_date}) không được sớm hơn ngày đặt cọc ({self.deposit_date})."
            )
        return self


# ---------------------------------------------------------------------------
# Canonical Scenario Builders (FCS v2.6 §3 / TD-4.2 §3.4)
# ---------------------------------------------------------------------------
def create_pa_chudong_config(
    deposit_amount_vnd: int = 100_000_000,
    policy_reference: StructuredPolicyReference | None = None,
) -> PaymentScenarioConfig:
    """Tạo cấu hình kịch bản PA-CHUDONG (Tiến độ chuẩn 9 đợt thanh toán)."""
    rules = [
        InstallmentRule(
            installment_number=1,
            milestone_name="Đợt 1: Ký HĐMB (đã kết chuyển cọc)",
            days_from_deposit=15,
            customer_equity_ratio=Decimal("0.1500"),
            bank_disbursement_ratio=Decimal("0.0000"),
            maintenance_fee_ratio=Decimal("0.0000"),
            is_handover=False,
            is_reconciliation=False,
        ),
        InstallmentRule(
            installment_number=2,
            milestone_name="Đợt 2: Xây thô tầng 5",
            days_from_deposit=60,
            customer_equity_ratio=Decimal("0.1000"),
            bank_disbursement_ratio=Decimal("0.0000"),
            maintenance_fee_ratio=Decimal("0.0000"),
            is_handover=False,
            is_reconciliation=False,
        ),
        InstallmentRule(
            installment_number=3,
            milestone_name="Đợt 3: Xây thô tầng 10",
            days_from_deposit=120,
            customer_equity_ratio=Decimal("0.1000"),
            bank_disbursement_ratio=Decimal("0.0000"),
            maintenance_fee_ratio=Decimal("0.0000"),
            is_handover=False,
            is_reconciliation=False,
        ),
        InstallmentRule(
            installment_number=4,
            milestone_name="Đợt 4: Xây thô tầng 15",
            days_from_deposit=180,
            customer_equity_ratio=Decimal("0.1000"),
            bank_disbursement_ratio=Decimal("0.0000"),
            maintenance_fee_ratio=Decimal("0.0000"),
            is_handover=False,
            is_reconciliation=False,
        ),
        InstallmentRule(
            installment_number=5,
            milestone_name="Đợt 5: Xây thô tầng 20",
            days_from_deposit=240,
            customer_equity_ratio=Decimal("0.1000"),
            bank_disbursement_ratio=Decimal("0.0000"),
            maintenance_fee_ratio=Decimal("0.0000"),
            is_handover=False,
            is_reconciliation=False,
        ),
        InstallmentRule(
            installment_number=6,
            milestone_name="Đợt 6: Cất nóc công trình",
            days_from_deposit=300,
            customer_equity_ratio=Decimal("0.1000"),
            bank_disbursement_ratio=Decimal("0.0000"),
            maintenance_fee_ratio=Decimal("0.0000"),
            is_handover=False,
            is_reconciliation=False,
        ),
        InstallmentRule(
            installment_number=7,
            milestone_name="Đợt 7: Hoàn thiện mặt ngoài",
            days_from_deposit=360,
            customer_equity_ratio=Decimal("0.1000"),
            bank_disbursement_ratio=Decimal("0.0000"),
            maintenance_fee_ratio=Decimal("0.0000"),
            is_handover=False,
            is_reconciliation=False,
        ),
        InstallmentRule(
            installment_number=8,
            milestone_name="Đợt 8: Thông báo bàn giao nhà",
            days_from_deposit=450,
            customer_equity_ratio=Decimal("0.2000"),
            bank_disbursement_ratio=Decimal("0.0000"),
            maintenance_fee_ratio=Decimal("1.0000"),
            is_handover=True,
            is_reconciliation=False,
        ),
        InstallmentRule(
            installment_number=9,
            milestone_name="Đợt 9: Nhận Giấy chứng nhận quyền sở hữu (Sổ hồng)",
            days_from_deposit=540,
            customer_equity_ratio=Decimal("0.0500"),
            bank_disbursement_ratio=Decimal("0.0000"),
            maintenance_fee_ratio=Decimal("0.0000"),
            is_handover=False,
            is_reconciliation=True,
        ),
    ]
    return PaymentScenarioConfig(
        scenario_type=ScenarioType.STANDARD_PROGRESS,
        scenario_name="Phương án Tiến độ Chuẩn (9 Đợt)",
        installment_rules=rules,
        deposit_amount_vnd=deposit_amount_vnd,
        bank_financing_rate=Decimal("0.0000"),
        customer_equity_rate=Decimal("1.0000"),
        policy_reference=policy_reference,
    )


def create_pa_nhanh_config(
    deposit_amount_vnd: int = 100_000_000,
    policy_reference: StructuredPolicyReference | None = None,
) -> PaymentScenarioConfig:
    """Tạo cấu hình kịch bản PA-NHANH (Thanh toán sớm 95%)."""
    rules = [
        InstallmentRule(
            installment_number=1,
            milestone_name="Đợt 1: Ký HĐMB và thanh toán sớm 95% (đã kết chuyển cọc)",
            days_from_deposit=15,
            customer_equity_ratio=Decimal("0.9500"),
            bank_disbursement_ratio=Decimal("0.0000"),
            maintenance_fee_ratio=Decimal("0.0000"),
            is_handover=False,
            is_reconciliation=False,
        ),
        InstallmentRule(
            installment_number=2,
            milestone_name="Đợt 2: Thông báo bàn giao nhà (thu 100% KPBT)",
            days_from_deposit=180,
            customer_equity_ratio=Decimal("0.0000"),
            bank_disbursement_ratio=Decimal("0.0000"),
            maintenance_fee_ratio=Decimal("1.0000"),
            is_handover=True,
            is_reconciliation=False,
        ),
        InstallmentRule(
            installment_number=3,
            milestone_name="Đợt 3: Nhận Giấy chứng nhận quyền sở hữu (Sổ hồng)",
            days_from_deposit=240,
            customer_equity_ratio=Decimal("0.0500"),
            bank_disbursement_ratio=Decimal("0.0000"),
            maintenance_fee_ratio=Decimal("0.0000"),
            is_handover=False,
            is_reconciliation=True,
        ),
    ]
    return PaymentScenarioConfig(
        scenario_type=ScenarioType.EARLY_95,
        scenario_name="Phương án Thanh toán Sớm 95%",
        installment_rules=rules,
        deposit_amount_vnd=deposit_amount_vnd,
        bank_financing_rate=Decimal("0.0000"),
        customer_equity_rate=Decimal("1.0000"),
        policy_reference=policy_reference,
    )


def create_pa_vay_config(
    deposit_amount_vnd: int = 100_000_000,
    interest_support_months: int = 24,
    principal_grace_months: int = 24,
    policy_reference: StructuredPolicyReference | None = None,
) -> PaymentScenarioConfig:
    """Tạo cấu hình kịch bản PA-VAY (Hỗ trợ lãi suất ngân hàng 70%)."""
    rules = [
        InstallmentRule(
            installment_number=1,
            milestone_name="Đợt 1: Ký HĐMB - Khách nộp 15% vốn tự có (đã kết chuyển cọc)",
            days_from_deposit=15,
            customer_equity_ratio=Decimal("0.1500"),
            bank_disbursement_ratio=Decimal("0.0000"),
            maintenance_fee_ratio=Decimal("0.0000"),
            is_handover=False,
            is_reconciliation=False,
        ),
        InstallmentRule(
            installment_number=2,
            milestone_name="Đợt 2: Ngân hàng giải ngân 70% giá trị hợp đồng (HTLS 0%)",
            days_from_deposit=30,
            customer_equity_ratio=Decimal("0.0000"),
            bank_disbursement_ratio=Decimal("0.7000"),
            maintenance_fee_ratio=Decimal("0.0000"),
            is_handover=False,
            is_reconciliation=False,
        ),
        InstallmentRule(
            installment_number=3,
            milestone_name="Đợt 3: Khách nộp 5% vốn tự có đợt 2",
            days_from_deposit=60,
            customer_equity_ratio=Decimal("0.0500"),
            bank_disbursement_ratio=Decimal("0.0000"),
            maintenance_fee_ratio=Decimal("0.0000"),
            is_handover=False,
            is_reconciliation=False,
        ),
        InstallmentRule(
            installment_number=4,
            milestone_name="Đợt 4: Khách nộp 5% vốn tự có đợt 3",
            days_from_deposit=90,
            customer_equity_ratio=Decimal("0.0500"),
            bank_disbursement_ratio=Decimal("0.0000"),
            maintenance_fee_ratio=Decimal("0.0000"),
            is_handover=False,
            is_reconciliation=False,
        ),
        InstallmentRule(
            installment_number=5,
            milestone_name="Đợt 5: Thông báo bàn giao nhà (thu 100% KPBT)",
            days_from_deposit=180,
            customer_equity_ratio=Decimal("0.0000"),
            bank_disbursement_ratio=Decimal("0.0000"),
            maintenance_fee_ratio=Decimal("1.0000"),
            is_handover=True,
            is_reconciliation=False,
        ),
        InstallmentRule(
            installment_number=6,
            milestone_name="Đợt 6: Nhận Giấy chứng nhận quyền sở hữu (Sổ hồng)",
            days_from_deposit=240,
            customer_equity_ratio=Decimal("0.0500"),
            bank_disbursement_ratio=Decimal("0.0000"),
            maintenance_fee_ratio=Decimal("0.0000"),
            is_handover=False,
            is_reconciliation=True,
        ),
    ]
    return PaymentScenarioConfig(
        scenario_type=ScenarioType.BANK_LOAN_HTLS,
        scenario_name="Phương án Hỗ trợ Lãi suất Ngân hàng (HTLS 70%)",
        installment_rules=rules,
        deposit_amount_vnd=deposit_amount_vnd,
        bank_financing_rate=Decimal("0.7000"),
        customer_equity_rate=Decimal("0.3000"),
        interest_support_months=interest_support_months,
        principal_grace_months=principal_grace_months,
        policy_reference=policy_reference,
    )


def create_canonical_scenario_config(
    scenario_type: ScenarioType,
    deposit_amount_vnd: int = 100_000_000,
    policy_reference: StructuredPolicyReference | None = None,
) -> PaymentScenarioConfig:
    """Factory dispatch tạo PaymentScenarioConfig chuẩn tắc cho bất kỳ ScenarioType nào."""
    if scenario_type == ScenarioType.STANDARD_PROGRESS:
        return create_pa_chudong_config(
            deposit_amount_vnd=deposit_amount_vnd, policy_reference=policy_reference
        )
    if scenario_type == ScenarioType.EARLY_95:
        return create_pa_nhanh_config(
            deposit_amount_vnd=deposit_amount_vnd, policy_reference=policy_reference
        )
    if scenario_type == ScenarioType.BANK_LOAN_HTLS:
        return create_pa_vay_config(
            deposit_amount_vnd=deposit_amount_vnd, policy_reference=policy_reference
        )
    raise ValueError(f"Unsupported scenario_type: {scenario_type}")


# ---------------------------------------------------------------------------
# Output Contracts conforming to FCS v2.6 §4.5 & §7
# ---------------------------------------------------------------------------
class CashflowInstallmentOutput(AntiFloatBaseModel):
    """Output installment execution milestone conforming to FCS v2.6 §4.5."""

    installment_number: int = Field(..., ge=1, le=30)
    milestone_name: str = Field(..., min_length=1)
    due_date: date
    customer_equity_paid_vnd: int = Field(..., ge=0)
    bank_disbursement_vnd: int = Field(..., ge=0)
    maintenance_fee_paid_vnd: int = Field(..., ge=0)
    installment_gross_obligation_vnd: int = Field(
        ..., ge=0, description="Tổng nghĩa vụ đợt này (Equity + Bank + KPBT)"
    )
    installment_additional_cash_due_vnd: int = Field(
        ..., ge=0, description="Tiền khách nộp thêm thực tế sau khi trừ cọc (Đợt 1)"
    )
    deposit_credited_vnd: int = Field(
        default=0, ge=0, description="Tiền cọc kết chuyển vào đợt này"
    )
    is_handover_milestone: bool = Field(default=False)
    is_reconciliation_installment: bool = Field(default=False)

    @model_validator(mode="after")
    def validate_installment_consistency(self) -> "CashflowInstallmentOutput":
        # 1. Gross obligation must equal equity + bank + maintenance fee
        expected_gross = (
            self.customer_equity_paid_vnd
            + self.bank_disbursement_vnd
            + self.maintenance_fee_paid_vnd
        )
        if self.installment_gross_obligation_vnd != expected_gross:
            raise ValueError(
                f"Installment {self.installment_number}: installment_gross_obligation_vnd "
                f"({self.installment_gross_obligation_vnd}) không khớp với tổng equity + bank + kpbt ({expected_gross})."
            )

        # 2. Deposit credited cannot exceed customer equity paid
        if self.deposit_credited_vnd > self.customer_equity_paid_vnd:
            raise ValueError(
                f"Installment {self.installment_number}: deposit_credited_vnd ({self.deposit_credited_vnd}) "
                f"vượt quá customer_equity_paid_vnd ({self.customer_equity_paid_vnd})."
            )

        # 3. Additional cash due must equal customer equity paid minus deposit credited + maintenance fee paid
        expected_additional_cash = (
            self.customer_equity_paid_vnd
            - self.deposit_credited_vnd
            + self.maintenance_fee_paid_vnd
        )
        if self.installment_additional_cash_due_vnd != expected_additional_cash:
            raise ValueError(
                f"Installment {self.installment_number}: installment_additional_cash_due_vnd "
                f"({self.installment_additional_cash_due_vnd}) không khớp với số tiền thực nộp dự kiến ({expected_additional_cash})."
            )

        return self


class ScenarioCalculationResult(AntiFloatBaseModel):
    """Complete financial calculation result for a single commercial scenario."""

    scenario_type: ScenarioType
    scenario_name: str = Field(..., min_length=1)
    listed_price_vnd: int = Field(..., gt=0, description="P_listed: Giá niêm yết chưa VAT")
    fixed_discount_vnd: int = Field(
        default=0, ge=0, description="D_fixed: Giảm trừ tiền mặt cố định"
    )
    base_after_fixed_vnd: int = Field(
        ..., ge=0, description="Base_1 = P_listed - D_fixed"
    )
    total_discount_rate: Decimal = Field(
        default=Decimal("0.0000"),
        ge=0,
        le=1,
        description="Sum_Rate: Tổng tỷ lệ chiết khấu %",
    )
    percentage_discount_vnd: int = Field(
        default=0, ge=0, description="Discount_Percent_Amount"
    )
    net_price_before_vat: int = Field(
        ..., gt=0, description="P_net = Base_1 - Discount_Percent_Amount"
    )
    vat_rate: Decimal = Field(default=Decimal("0.1000"), ge=0, le=1)
    vat_amount: int = Field(..., ge=0, description="A_vat = round_vnd(P_net * R_vat)")
    maintenance_fee_rate: Decimal = Field(default=Decimal("0.0200"), ge=0, le=1)
    maintenance_fee_amount: int = Field(
        ..., ge=0, description="A_kpbt = round_vnd(P_net * R_kpbt)"
    )
    final_contract_price: int = Field(
        ..., gt=0, description="P_contract = P_net + A_vat + A_kpbt"
    )
    initial_gross_obligation_vnd: int = Field(
        ..., ge=0, description="Tổng nghĩa vụ Đợt 1 (gồm cọc và ngân hàng nếu có)"
    )
    initial_cash_outflow_vnd: int = Field(
        ...,
        ge=0,
        description="Tổng tiền mặt thực tế khách phải bỏ ra từ cọc đến ký HĐMB (Hàm mục tiêu MIN_INITIAL_OUTFLOW)",
    )
    customer_cash_outflow_until_handover: int = Field(
        ...,
        ge=0,
        description="Tổng vốn tự có khách nộp đến bàn giao (Hàm mục tiêu MIN_CASH_OUTFLOW_TO_HANDOVER)",
    )
    total_benefit_value_vnd: int = Field(
        default=0,
        ge=0,
        description="Tổng giá trị ưu đãi thương mại được phê duyệt định giá",
    )
    cashflow_schedule: list[CashflowInstallmentOutput] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_scenario_financial_invariants(self) -> "ScenarioCalculationResult":
        # 1. Base_1 = P_listed - D_fixed
        if self.base_after_fixed_vnd != self.listed_price_vnd - self.fixed_discount_vnd:
            raise ValueError(
                f"base_after_fixed_vnd ({self.base_after_fixed_vnd}) != listed_price_vnd "
                f"({self.listed_price_vnd}) - fixed_discount_vnd ({self.fixed_discount_vnd})."
            )

        # 2. P_net = Base_1 - percentage_discount_vnd
        if self.net_price_before_vat != self.base_after_fixed_vnd - self.percentage_discount_vnd:
            raise ValueError(
                f"net_price_before_vat ({self.net_price_before_vat}) != base_after_fixed_vnd "
                f"({self.base_after_fixed_vnd}) - percentage_discount_vnd ({self.percentage_discount_vnd})."
            )

        # 3. P_contract = P_net + A_vat + A_kpbt
        expected_contract = self.net_price_before_vat + self.vat_amount + self.maintenance_fee_amount
        if self.final_contract_price != expected_contract:
            raise ValueError(
                f"final_contract_price ({self.final_contract_price}) != net ({self.net_price_before_vat}) "
                f"+ vat ({self.vat_amount}) + kpbt ({self.maintenance_fee_amount}) = {expected_contract}."
            )

        # 4. Cashflow schedule reconciliation (if schedule present)
        if self.cashflow_schedule:
            total_schedule_gross = sum(
                inst.installment_gross_obligation_vnd for inst in self.cashflow_schedule
            )
            if total_schedule_gross != self.final_contract_price:
                raise ValueError(
                    f"Tổng nghĩa vụ dòng tiền ({total_schedule_gross}) != final_contract_price ({self.final_contract_price})."
                )

        return self


class ValidationReport(AntiFloatBaseModel):
    """Sanity checks verification report for financial calculation results."""

    is_valid: bool = True
    status: CalculationStatus = CalculationStatus.VALID
    invariants_checked: list[str] = Field(default_factory=list)
    error_message: str | None = None
    field_errors: list[dict[str, Any]] = Field(default_factory=list)


class RecommendationResult(AntiFloatBaseModel):
    """Scenario recommendation result under a given optimization objective."""

    selected_objective: OptimizationObjective
    recommended_scenario: ScenarioType
    comparison_summary: list[dict[str, Any]] = Field(default_factory=list)
    quantitative_rationale: str = Field(..., min_length=1)
    is_tie_break_applied: bool = Field(default=False)
    tiebreak_rule_id: str | None = None
    tie_break_reason: str | None = None


class PricingCalculationOutput(AntiFloatBaseModel):
    """Top-level immutable calculation output envelope with RFC 8785 signature."""

    spec_version: str = Field(default="2.6")
    engine_version: str = Field(default="DeterministicPricingEngine_v2.6")
    calculation_timestamp: str = Field(
        ..., min_length=1, description="ISO-8601 UTC timestamp of calculation run"
    )
    unit_code: str = Field(..., min_length=1)
    scenario_results: list[ScenarioCalculationResult]
    recommended_result: RecommendationResult | None = None
    validation_report: ValidationReport = Field(default_factory=ValidationReport)
    canonical_snapshot_hash: str = Field(
        ...,
        min_length=64,
        max_length=64,
        pattern=r"^[0-9a-fA-F]{64}$",
        description="RFC 8785 Canonical JSON SHA-256 Hash of calculation output",
    )
    quote_id: str | None = None
    quote_version: int | None = None

    @model_validator(mode="after")
    def validate_recommended_scenario_exists(self) -> "PricingCalculationOutput":
        if self.recommended_result:
            available_types = {s.scenario_type for s in self.scenario_results}
            if self.recommended_result.recommended_scenario not in available_types:
                raise ValueError(
                    f"recommended_scenario '{self.recommended_result.recommended_scenario}' "
                    f"không nằm trong danh sách scenario_results ({available_types})."
                )
        return self
