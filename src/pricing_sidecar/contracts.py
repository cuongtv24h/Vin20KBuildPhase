"""Domain Contracts, Enums, and Data Schemas for Financial Calculation.

FCS v2.6 Reference: Sections 3, 4, 7, 8, 9
TD-4.2 Reference: Section 2 (Domain-Driven Design)
TD-4.4 Reference: Section 4 (Tool & Governance Contracts)
"""

from enum import StrEnum


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
