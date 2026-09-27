"""
Test suite to lock down domain enums, 6 canonical objectives, and Triple Enum Isolation.
"""

from src.contracts.enums import (
    ApprovalStatus,
    ComplianceStatus,
    ComplianceTier,
    LeadDossierStatus,
    OptimizationObjective,
    PdfStatus,
    PolicyRuleStatus,
    PreSalesSessionStatus,
    QuoteWorkflowStatus,
    SecurityEventType,
)


def test_canonical_six_optimization_objectives():
    """Khóa cứng đúng 6 mục tiêu tối ưu hóa chuẩn tắc theo ADR-021."""
    expected_objectives = {
        "MIN_NET_PRICE",
        "MIN_INITIAL_CASH",
        "MIN_MONTHLY_BURDEN",
        "MIN_TOTAL_CASH_OUTFLOW",
        "MAX_BENEFIT_VALUE",
        "EARLY_HANDOVER",
    }
    actual_objectives = {obj.value for obj in OptimizationObjective}
    assert actual_objectives == expected_objectives
    assert len(OptimizationObjective) == 6


def test_triple_enum_isolation():
    """Triple Enum Isolation: QuoteWorkflowStatus, ApprovalStatus, PdfStatus độc lập tuyệt đối."""
    quote_statuses = {s.value for s in QuoteWorkflowStatus}
    approval_statuses = {s.value for s in ApprovalStatus}
    pdf_statuses = {s.value for s in PdfStatus}

    # Báo giá có 14 trạng thái
    assert len(QuoteWorkflowStatus) == 14
    assert "DRAFT" in quote_statuses
    assert "READY_FOR_REVIEW" in quote_statuses
    assert "SUPERSEDED" in quote_statuses

    # Phê duyệt HITL có 7 trạng thái
    assert len(ApprovalStatus) == 7
    assert "ATTESTED" in approval_statuses
    assert "REVISION_REQUESTED" in approval_statuses

    # PDF Outbox có 7 trạng thái
    assert len(PdfStatus) == 7
    assert "GENERATING" in pdf_statuses
    assert "MANUAL_INTERVENTION" in pdf_statuses

    # Không được có trạng thái PDF nằm trong QuoteWorkflowStatus
    assert "GENERATING" not in quote_statuses
    assert "MANUAL_INTERVENTION" not in quote_statuses


def test_compliance_enums():
    """Khóa 8 trạng thái tuân thủ và 4 phân hạng rủi ro (F8)."""
    assert len(ComplianceTier) == 4
    expected_tiers = {"TIER_1_GREEN", "TIER_2_YELLOW", "TIER_3_RED", "TIER_4_BLACK"}
    assert {t.value for t in ComplianceTier} == expected_tiers

    assert len(ComplianceStatus) == 8
    expected_statuses = {
        "DRAFT", "CHECKING", "SUPPORTED", "CONDITIONAL",
        "UNSUPPORTED", "PROHIBITED", "EXPIRED", "SUPERSEDED"
    }
    assert {s.value for s in ComplianceStatus} == expected_statuses


def test_pre_sales_and_dossier_enums():
    """Khóa các trạng thái của phễu Pre-Sales và Lead Handoff."""
    assert len(PreSalesSessionStatus) == 7
    assert "WAITING_FOR_CONSTRAINT_CONFIRMATION" in PreSalesSessionStatus
    assert "WAITING_FOR_HANDOFF_CONSENT" in PreSalesSessionStatus

    assert len(LeadDossierStatus) == 7
    assert "CONVERTED_TO_QUOTE" in LeadDossierStatus
    assert "DISQUALIFIED" in LeadDossierStatus


def test_policy_and_security_enums():
    """Khóa các trạng thái chính sách F9 và sự kiện bảo mật."""
    assert len(PolicyRuleStatus) == 4
    assert {s.value for s in PolicyRuleStatus} == {"DRAFT", "APPROVED_FOR_USE", "ACTIVE", "RETIRED"}

    assert len(SecurityEventType) == 5
    assert "SOD_VIOLATION_DETECTED" in SecurityEventType
    assert "PROMPT_INJECTION_DETECTED" in SecurityEventType
