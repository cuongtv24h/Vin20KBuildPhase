"""Smoke test dịch vụ scaffold: đúng class/hàm, NotImplemented khi chưa build."""

import pytest

from src.services.approval.review import ApprovalService
from src.services.approval.signing import Ed25519AttestationService, payload_fingerprint
from src.services.audit.chain import AuditTrailService
from src.services.audit.verifier import AuditVerifier
from src.services.compliance.gate import ComplianceGate
from src.services.dossier.service import DossierService
from src.services.pricing.client import PricingSidecarClient
from src.services.pricing.validation import SANITY_CHECKS
from src.services.snapshot.freezer import PolicySnapshotService


def test_sanity_checks_has_six_items():
    assert len(SANITY_CHECKS) == 6


def test_payload_fingerprint_is_deterministic():
    payload = {"quote_id": "Q-1", "amount": 1000}
    assert payload_fingerprint(payload) == payload_fingerprint(dict(reversed(list(payload.items()))))


def test_compliance_gate_defaults_to_final_send_trigger():
    from src.contracts.enums import ComplianceCheckTrigger

    gate = ComplianceGate()
    assert gate.triggers == (ComplianceCheckTrigger.ON_FINAL_SEND,)


@pytest.mark.asyncio
async def test_services_raise_not_implemented():
    with pytest.raises(NotImplementedError):
        await AuditTrailService().append_event("Q-1", {"type": "TEST"})
    with pytest.raises(NotImplementedError):
        AuditVerifier().verify_chain("Q-1", [])
    with pytest.raises(NotImplementedError):
        await ApprovalService().submit_for_review("Q-1", 1, {})
    with pytest.raises(NotImplementedError):
        await Ed25519AttestationService().request_attestation("hash", "otp")
    with pytest.raises(NotImplementedError):
        await ComplianceGate().check("msg", {})
    with pytest.raises(NotImplementedError):
        await DossierService().create_from_session("s1", {})
    with pytest.raises(NotImplementedError):
        await PricingSidecarClient().calculate({})
    with pytest.raises(NotImplementedError):
        await PolicySnapshotService().freeze("2026-03-10", "PROJECT-VLF-001", [])
