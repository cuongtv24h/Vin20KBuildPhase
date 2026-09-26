"""Bộ enum chuẩn hóa hệ thống — nguồn chân lý: TD-4.3 §2.

Nguyên tắc "Triple Enum Isolation": vòng đời Báo giá (QuoteWorkflowStatus),
trạng thái Phê duyệt (ApprovalStatus) và trạng thái sinh PDF (PdfStatus) là
BA hệ trạng thái ĐỘC LẬP, tuyệt đối không ghép trạng thái với mã lỗi thành
một chuỗi (ví dụ tách rõ `SUPERSEDED` và mã lỗi `STALE_QUOTE_VERSION`).
"""

from enum import StrEnum


class PolicyEvaluationStatus(StrEnum):
    """Kết quả thẩm định từng điều khoản chính sách (node N-06)."""

    ELIGIBLE = "ELIGIBLE"
    NOT_ELIGIBLE = "NOT_ELIGIBLE"
    CONFLICT = "CONFLICT"
    AMBIGUOUS = "AMBIGUOUS"
    EXPIRED = "EXPIRED"


class QuoteWorkflowStatus(StrEnum):
    """Vòng đời báo giá chính thức (C-01 Official Quote StateGraph)."""

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
    """Trạng thái phê duyệt HITL (C-05) — độc lập với QuoteWorkflowStatus."""

    NOT_REQUIRED = "NOT_REQUIRED"
    PENDING = "PENDING"
    ATTESTED = "ATTESTED"
    APPROVED = "APPROVED"
    APPROVAL_FAILED = "APPROVAL_FAILED"
    REJECTED = "REJECTED"
    REVISION_REQUESTED = "REVISION_REQUESTED"


class PdfStatus(StrEnum):
    """Trạng thái sinh tệp PDF bất đồng bộ — quản lý qua Transactional Outbox."""

    NOT_REQUESTED = "NOT_REQUESTED"
    PENDING = "PENDING"
    GENERATING = "GENERATING"
    ISSUED = "ISSUED"
    FAILED = "FAILED"
    RETRYING = "RETRYING"
    MANUAL_INTERVENTION = "MANUAL_INTERVENTION"


class OptimizationObjective(StrEnum):
    """6 mục tiêu tối ưu chuẩn tắc cho ranking phương án (node N-12, C-06)."""

    MIN_NET_PRICE = "MIN_NET_PRICE"
    MIN_INITIAL_CASH = "MIN_INITIAL_CASH"
    MIN_MONTHLY_BURDEN = "MIN_MONTHLY_BURDEN"
    MIN_TOTAL_CASH_OUTFLOW = "MIN_TOTAL_CASH_OUTFLOW"
    MAX_BENEFIT_VALUE = "MAX_BENEFIT_VALUE"
    EARLY_HANDOVER = "EARLY_HANDOVER"


class PreSalesSessionStatus(StrEnum):
    """Vòng đời phiên Pre-Sales (C-09) — namespace tách biệt Official Quote."""

    ACTIVE = "ACTIVE"
    WAITING_FOR_CUSTOMER_INPUT = "WAITING_FOR_CUSTOMER_INPUT"
    WAITING_FOR_CONSTRAINT_CONFIRMATION = "WAITING_FOR_CONSTRAINT_CONFIRMATION"
    WAITING_FOR_HANDOFF_CONSENT = "WAITING_FOR_HANDOFF_CONSENT"
    HANDED_OFF = "HANDED_OFF"
    EXPIRED = "EXPIRED"
    ABANDONED = "ABANDONED"


class LeadDossierStatus(StrEnum):
    """Vòng đời Lead Dossier bàn giao Sale (C-10, F6/F7)."""

    NEW = "NEW"
    ASSIGNED = "ASSIGNED"
    CONTACTED = "CONTACTED"
    QUALIFIED = "QUALIFIED"
    CONVERTED_TO_QUOTE = "CONVERTED_TO_QUOTE"
    EXPIRED = "EXPIRED"
    DISQUALIFIED = "DISQUALIFIED"


class ComplianceStatus(StrEnum):
    """Kết quả kiểm tra tin nhắn Sale (C-11, F8)."""

    DRAFT = "DRAFT"
    CHECKING = "CHECKING"
    SUPPORTED = "SUPPORTED"
    CONDITIONAL = "CONDITIONAL"
    UNSUPPORTED = "UNSUPPORTED"
    PROHIBITED = "PROHIBITED"
    EXPIRED = "EXPIRED"
    SUPERSEDED = "SUPERSEDED"


class ComplianceTier(StrEnum):
    """4 tầng cảnh báo rủi ro của Compliance Gate (Đỏ/Vàng/Xanh + Black)."""

    TIER_1_GREEN = "TIER_1_GREEN"
    TIER_2_YELLOW = "TIER_2_YELLOW"
    TIER_3_RED = "TIER_3_RED"
    TIER_4_BLACK = "TIER_4_BLACK"


class ComplianceCheckTrigger(StrEnum):
    """3 checkpoint bắt buộc kiểm tra của F8 (ON_FINAL_SEND là chốt chặn bắt buộc)."""

    ON_PREVIEW = "ON_PREVIEW"
    ON_COPY = "ON_COPY"
    ON_FINAL_SEND = "ON_FINAL_SEND"


class SecurityEventType(StrEnum):
    """Sự kiện bảo mật — guardrail chặn tại N-02/N-05/N-10A/N-14A (TD-4.3)."""

    PROMPT_INJECTION_BLOCKED = "PROMPT_INJECTION_BLOCKED"
    SOURCE_UNTRUSTED_BLOCKED = "SOURCE_UNTRUSTED_BLOCKED"
    TOOL_CALL_BLOCKED = "TOOL_CALL_BLOCKED"
    OUTPUT_LEAKAGE_BLOCKED = "OUTPUT_LEAKAGE_BLOCKED"
    SOD_VIOLATION_BLOCKED = "SOD_VIOLATION_BLOCKED"
    STALE_VERSION_APPROVAL_BLOCKED = "STALE_VERSION_APPROVAL_BLOCKED"
    UNAUTHORIZED_ACTION_BLOCKED = "UNAUTHORIZED_ACTION_BLOCKED"


class ExceptionScope(StrEnum):
    """Phạm vi áp dụng báo giá ngoại lệ do TGĐ ủy quyền (node N-18)."""

    QUOTE_ONLY = "QUOTE_ONLY"
    CUSTOMER_ONLY = "CUSTOMER_ONLY"
    POLICY_SPECIFIC = "POLICY_SPECIFIC"
