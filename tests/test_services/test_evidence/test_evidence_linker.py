"""Unit tests for Claim-Level Evidence Linker & 5 Invariant Checks (C-04 / F4 / N-14B)."""

from src.models.rag_schemas import AttributedPolicyEvidence, EvidenceCoordinate
from src.services.evidence.linker import EvidenceLinker


def test_evidence_linker_verified_flow():
    linker = EvidenceLinker()
    verbatim = "Chiết khấu 8% giá trị căn hộ trước VAT khi thanh toán bằng vốn tự có."
    import hashlib

    content_hash = hashlib.sha256(verbatim.strip().encode("utf-8")).hexdigest()

    coord = EvidenceCoordinate(
        policy_id="POL-02",
        chapter="Chương II",
        article="Điều 3",
        clause="Khoản 1",
        point="Điểm a",
        line_span=(10, 15),
        content_sha256=content_hash,
    )
    evidence = AttributedPolicyEvidence(
        coordinate=coord,
        policy_title="Chính sách chiết khấu thanh toán sớm",
        verbatim_text=verbatim,
        valid_from="2025-01-01",
        valid_to="2025-12-31",
        applicability_conditions={"status": "ACTIVE"},
        similarity_score=0.92,
        is_superseded=False,
    )

    result = linker.link_claim(
        claim_id="CLM-01",
        claim_text="Khách hàng được chiết khấu 8% khi trả sớm.",
        candidate_evidences=[evidence],
        transaction_date="2025-06-15",
    )

    assert result.is_verified is True
    assert result.status == "VERIFIED"
    assert len(result.anchors) == 1
    assert result.anchors[0].doc_id == "POL-02"
    assert result.anchors[0].verify_hash() is True


def test_evidence_linker_rejects_expired_policy():
    linker = EvidenceLinker()
    verbatim = "Ưu đãi tặng gói nội thất 100 triệu."
    import hashlib

    content_hash = hashlib.sha256(verbatim.strip().encode("utf-8")).hexdigest()

    coord = EvidenceCoordinate(
        policy_id="POL-05",
        chapter="Chương I",
        article="Điều 1",
        clause="Khoản 1",
        content_sha256=content_hash,
    )
    evidence = AttributedPolicyEvidence(
        coordinate=coord,
        policy_title="Chính sách tặng nội thất",
        verbatim_text=verbatim,
        valid_from="2024-01-01",
        valid_to="2024-12-31",
        applicability_conditions={"status": "EXPIRED"},
        similarity_score=0.88,
        is_superseded=True,
    )

    result = linker.link_claim(
        claim_id="CLM-02",
        claim_text="Khách hàng được tặng nội thất 100 triệu.",
        candidate_evidences=[evidence],
        transaction_date="2025-06-15",
    )

    assert result.is_verified is False
    assert result.status == "REJECTED"
    assert any("POLICY_SUPERSEDED" in r or "TEMPORAL_EXPIRED" in r for r in result.reasons)
