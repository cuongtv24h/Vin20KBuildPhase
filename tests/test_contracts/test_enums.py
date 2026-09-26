"""Khóa bộ enum hợp đồng — chống trôi khi team mở rộng (nguồn TD-4.3)."""

from src.contracts.enums import (
    ApprovalStatus,
    ComplianceStatus,
    ComplianceTier,
    OptimizationObjective,
    PdfStatus,
    QuoteWorkflowStatus,
    SecurityEventType,
)


def test_six_optimization_objectives():
    assert {o.value for o in OptimizationObjective} == {
        "MIN_NET_PRICE",
        "MIN_INITIAL_CASH",
        "MIN_MONTHLY_BURDEN",
        "MIN_TOTAL_CASH_OUTFLOW",
        "MAX_BENEFIT_VALUE",
        "EARLY_HANDOVER",
    }


def test_triple_enum_isolation_status_sets_do_not_merge():
    """3 hệ trạng thái là 3 enum ĐỘC LẬP (TD-4.3) — không gộp chung, không
    trộn mã lỗi vào trạng thái. Giá trị trùng như APPROVED/REJECTED giữa
    workflow và approval là chủ đích; nhưng các trạng thái đặc thù phải ở
    đúng enum của nó."""
    workflow = {s.value for s in QuoteWorkflowStatus}
    approval = {s.value for s in ApprovalStatus}
    pdf = {s.value for s in PdfStatus}
    # SUPERSEDED thuộc vòng đời quote, không thuộc approval/pdf
    assert "SUPERSEDED" in workflow
    assert "SUPERSEDED" not in approval
    assert "SUPERSEDED" not in pdf
    # Trạng thái tính toán chỉ tồn tại ở vòng đời quote
    for calc_only in ("ANALYZING", "CALCULATING", "ABSTAINED"):
        assert calc_only in workflow
        assert calc_only not in approval
        assert calc_only not in pdf
    # Trạng thái sinh PDF độc lập với 2 hệ trên
    for pdf_only in ("GENERATING", "RETRYING", "MANUAL_INTERVENTION"):
        assert pdf_only in pdf
        assert pdf_only not in workflow
        assert pdf_only not in approval


def test_compliance_tiers_four_levels():
    assert len(ComplianceTier) == 4
    assert len(ComplianceStatus) >= 8
    assert len(SecurityEventType) >= 7
