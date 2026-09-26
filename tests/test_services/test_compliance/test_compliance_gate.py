"""Unit tests for Message Compliance Gate (C-11 / F8)."""

from src.services.compliance.gate import (
    ComplianceCheckRequest,
    ComplianceGate,
)


def test_compliance_gate_blocks_prohibited_profit_guarantee():
    gate = ComplianceGate()
    req = ComplianceCheckRequest(
        message="Dự án này cam kết sinh lời 15% mỗi năm chắc chắn không rủi ro.",
        mode="FINAL_SEND",
    )
    res = gate.check(req)
    assert res.overall_status == "PROHIBITED"
    assert res.required_action == "BLOCK_MESSAGE_COMPLIANCE_VIOLATION"
    assert len(res.claims) >= 1
    assert any(c.tier == "PROHIBITED" for c in res.claims)


def test_compliance_gate_blocks_prohibited_loan_guarantee():
    gate = ComplianceGate()
    req = ComplianceCheckRequest(
        message="Bên em bao duyệt vay ngân hàng 100% không cần chứng minh thu nhập.",
        mode="FINAL_SEND",
    )
    res = gate.check(req)
    assert res.overall_status == "PROHIBITED"
    assert res.required_action == "BLOCK_MESSAGE_COMPLIANCE_VIOLATION"


def test_compliance_gate_conditional_draft_on_unsupported_discount():
    gate = ComplianceGate()
    # In draft mode, an unreferenced discount claim is conditional/warning
    req = ComplianceCheckRequest(
        message="Anh sẽ được chiết khấu 8% khi thanh toán sớm.",
        mode="ON_DRAFT",
    )
    res = gate.check(req)
    assert res.overall_status == "CONDITIONAL"
    assert res.required_action == "SUGGEST_LINKING_EVIDENCE"


def test_compliance_gate_supported_with_policy_reference():
    gate = ComplianceGate()
    req = ComplianceCheckRequest(
        message="Căn hộ áp dụng chiết khấu 8% theo chính sách ban hành.",
        mode="FINAL_SEND",
        policy_version_refs=["POL-02:v1"],
        claimed_evidence_ids=["EV-POL-02-ART-3"],
    )
    res = gate.check(req)
    assert res.overall_status == "SUPPORTED"
    assert res.required_action == "ALLOW_SEND"
