"""
Canonical domain enums for PricePolicy AI Agent.
Triple Enum Isolation: QuoteWorkflowStatus, ApprovalStatus, and PdfStatus are strictly separated.
"""

from enum import StrEnum


class QuoteWorkflowStatus(StrEnum):
    """Vòng đời trạng thái Báo giá chính thức (14 trạng thái)."""
    DRAFT = "DRAFT"
    NEEDS_INPUT = "NEEDS_INPUT"
    ANALYZING = "ANALYZING"
    EXCEPTION_INPUT = "EXCEPTION_INPUT"
    CALCULATING = "CALCULATING"
    CALCULATION_FAILED = "CALCULATION_FAILED"
    READY_FOR_REVIEW = "READY_FOR_REVIEW"
    NEEDS_REVISION = "NEEDS_REVISION"
    ABSTAINED = "ABSTAINED"
    BLOCKED = "BLOCKED"
    REJECTED = "REJECTED"
    APPROVED = "APPROVED"
    SUPERSEDED = "SUPERSEDED"
    REVOKED = "REVOKED"


class ApprovalStatus(StrEnum):
    """Trạng thái phê duyệt kiểm soát con người HITL (7 trạng thái)."""
    NOT_REQUIRED = "NOT_REQUIRED"
    PENDING = "PENDING"
    ATTESTED = "ATTESTED"
    APPROVED = "APPROVED"
    APPROVAL_FAILED = "APPROVAL_FAILED"
    REJECTED = "REJECTED"
    REVISION_REQUESTED = "REVISION_REQUESTED"


class PdfStatus(StrEnum):
    """Trạng thái phát hành Báo giá chính thức PDF Outbox (7 trạng thái)."""
    NOT_REQUESTED = "NOT_REQUESTED"
    PENDING = "PENDING"
    GENERATING = "GENERATING"
    ISSUED = "ISSUED"
    FAILED = "FAILED"
    RETRYING = "RETRYING"
    MANUAL_INTERVENTION = "MANUAL_INTERVENTION"


class OptimizationObjective(StrEnum):
    """
    Canonical 6-Objective Enum (ADR-021).
    Chuẩn hóa đồng bộ trên PRD, Architecture, Schemas và Pricing Engine.
    """
    MIN_NET_PRICE = "MIN_NET_PRICE"
    MIN_INITIAL_CASH = "MIN_INITIAL_CASH"
    MIN_MONTHLY_BURDEN = "MIN_MONTHLY_BURDEN"
    MIN_TOTAL_CASH_OUTFLOW = "MIN_TOTAL_CASH_OUTFLOW"
    MAX_BENEFIT_VALUE = "MAX_BENEFIT_VALUE"
    EARLY_HANDOVER = "EARLY_HANDOVER"

    # Backward compatibility aliases
    MIN_INITIAL_OUTFLOW = "MIN_INITIAL_CASH"
    MIN_CASH_OUTFLOW_TO_HANDOVER = "MIN_TOTAL_CASH_OUTFLOW"
    MIN_CONTRACT_PRICE = "MIN_NET_PRICE"

    @classmethod
    def _missing_(cls, value: object):
        if isinstance(value, str):
            val_upper = value.upper()
            mapping = {
                "MIN_INITIAL_OUTFLOW": cls.MIN_INITIAL_CASH,
                "MIN_CASH_OUTFLOW_TO_HANDOVER": cls.MIN_TOTAL_CASH_OUTFLOW,
                "MIN_CONTRACT_PRICE": cls.MIN_NET_PRICE,
            }
            if val_upper in mapping:
                return mapping[val_upper]
        return super()._missing_(value)


class PolicyDecisionStatus(StrEnum):
    """Trạng thái thẩm định hiệu lực và tương thích chính sách."""
    ELIGIBLE = "ELIGIBLE"
    NOT_ELIGIBLE = "NOT_ELIGIBLE"
    CONFLICT = "CONFLICT"
    AMBIGUOUS = "AMBIGUOUS"
    EXPIRED = "EXPIRED"


class PolicyRuleStatus(StrEnum):
    """Vòng đời quy tắc chính sách F9 có cấu trúc (ADR-022)."""
    DRAFT = "DRAFT"
    APPROVED_FOR_USE = "APPROVED_FOR_USE"
    ACTIVE = "ACTIVE"
    RETIRED = "RETIRED"


class ComplianceStatus(StrEnum):
    """Vòng đời trạng thái kiểm duyệt thông điệp tuân thủ F8."""
    DRAFT = "DRAFT"
    CHECKING = "CHECKING"
    SUPPORTED = "SUPPORTED"
    CONDITIONAL = "CONDITIONAL"
    UNSUPPORTED = "UNSUPPORTED"
    PROHIBITED = "PROHIBITED"
    EXPIRED = "EXPIRED"
    SUPERSEDED = "SUPERSEDED"


class ComplianceTier(StrEnum):
    """Phân hạng rủi ro tuân thủ thông điệp F8."""
    TIER_1_GREEN = "TIER_1_GREEN"
    TIER_2_YELLOW = "TIER_2_YELLOW"
    TIER_3_RED = "TIER_3_RED"
    TIER_4_BLACK = "TIER_4_BLACK"


class ComplianceCheckTrigger(StrEnum):
    """Thời điểm kích hoạt kiểm tra tuân thủ."""
    ON_DRAFT = "ON_DRAFT"
    ON_DEBOUNCE = "ON_DEBOUNCE"
    ON_FINAL_SEND = "ON_FINAL_SEND"


class PreSalesSessionStatus(StrEnum):
    """Vòng đời phiên tư vấn Pre-Sales khách hàng (C-09)."""
    ACTIVE = "ACTIVE"
    WAITING_FOR_CUSTOMER_INPUT = "WAITING_FOR_CUSTOMER_INPUT"
    WAITING_FOR_CONSTRAINT_CONFIRMATION = "WAITING_FOR_CONSTRAINT_CONFIRMATION"
    WAITING_FOR_HANDOFF_CONSENT = "WAITING_FOR_HANDOFF_CONSENT"
    HANDED_OFF = "HANDED_OFF"
    EXPIRED = "EXPIRED"
    ABANDONED = "ABANDONED"


class LeadDossierStatus(StrEnum):
    """Vòng đời hồ sơ khách hàng bàn giao sang Sales (C-10)."""
    NEW = "NEW"
    ASSIGNED = "ASSIGNED"
    CONTACTED = "CONTACTED"
    QUALIFIED = "QUALIFIED"
    CONVERTED_TO_QUOTE = "CONVERTED_TO_QUOTE"
    EXPIRED = "EXPIRED"
    DISQUALIFIED = "DISQUALIFIED"


class SecurityEventType(StrEnum):
    """Loại sự kiện vi phạm an toàn bảo mật và phân quyền."""
    PROMPT_INJECTION_DETECTED = "PROMPT_INJECTION_DETECTED"
    DATA_LEAKAGE_DETECTED = "DATA_LEAKAGE_DETECTED"
    SOD_VIOLATION_DETECTED = "SOD_VIOLATION_DETECTED"
    TAMPER_DETECTED = "TAMPER_DETECTED"
    UNAUTHORIZED_ACCESS = "UNAUTHORIZED_ACCESS"
