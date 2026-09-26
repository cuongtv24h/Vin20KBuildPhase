"""Unit tests for Policy Atomizer, TDEC Closure, and EvidenceBundle Emission."""
from __future__ import annotations

from src.models.pec_contracts import (
    EvidenceDecisionStatus,
)
from src.services.evidence.closure.tdec import TDECClosure
from src.services.evidence.verification.evidence_verifier import EvidenceVerifier
from src.services.rag.compiler.atomizer import PolicyAtomizer


def test_policy_atomizer_markdown_parsing():
    """Test parsing markdown document into structured policy atoms."""
    atomizer = PolicyAtomizer()
    md_content = """# Chương I: Quy định chung
## Điều 1: Phạm vi điều chỉnh
1. Chính sách này áp dụng cho toàn bộ khách hàng cá nhân vay mua nhà.
2. Lãi suất ưu đãi cố định 6.5%/năm trong 12 tháng đầu.

## Điều 2: Điều khoản loại trừ
1. Không áp dụng đồng thời với gói hỗ trợ lãi suất của chủ đầu tư.
[*] Ghi chú: Yêu cầu mở tài khoản thanh toán trước khi giải ngân.
"""
    atoms = atomizer.parse_markdown_to_atoms(
        markdown_text=md_content,
        policy_metadata={"policy_id": "POL-LS-01", "policy_name": "Lãi suất 2026"},
    )
    assert len(atoms) >= 3
    # Check that canonical_text and retrieval_text are generated
    for atom in atoms:
        assert "canonical_text" in atom
        assert "retrieval_text" in atom
        assert "content_hash" in atom
        assert len(atom["embedding"]) == 384


def test_tdec_closure_and_conflict_detection():
    """Test TDEC expanding from seed to conflict partner via EXCLUDES edge."""
    closure = TDECClosure(max_hops=1)

    pos_seeds = [{"atom_id": "ATOM-001", "canonical_text": "Ưu đãi gói A 1%"}]
    neg_seeds = []

    available_edges = [
        {
            "edge_id": "EDGE-01",
            "source_atom_id": "ATOM-001",
            "target_atom_id": "ATOM-EXCL-02",
            "edge_type": "EXCLUDES",
            "validation_status": "APPROVED_FOR_USE",
            "description": "Không áp dụng đồng thời gói A và gói B",
        }
    ]
    atom_lookup = {
        "ATOM-001": {"atom_id": "ATOM-001", "canonical_text": "Ưu đãi gói A 1%"},
        "ATOM-EXCL-02": {"atom_id": "ATOM-EXCL-02", "canonical_text": "Gói B hỗ trợ 2%"},
    }

    closed_atoms, applied_edges, conflicts = closure.expand_closure(
        positive_seeds=pos_seeds,
        negative_seeds=neg_seeds,
        available_edges=available_edges,
        atom_lookup=atom_lookup,
    )

    assert len(closed_atoms) == 2
    assert len(conflicts) == 1
    assert conflicts[0]["relation"] == "EXCLUDES"
    assert conflicts[0]["target_atom_id"] == "ATOM-EXCL-02"


def test_evidence_verifier_verified_bundle():
    """Test EvidenceVerifier emitting verified EvidenceBundle with SHA-256 hash."""
    verifier = EvidenceVerifier()
    closed_atoms = [
        {"atom_id": "ATOM-001", "canonical_text": "Lãi suất 6.5%"},
        {"atom_id": "ATOM-002", "canonical_text": "Loại trừ gói C"},
    ]
    applied_edges = [{"edge_id": "E1", "target_atom_id": "ATOM-002"}]
    conflicts = [{"source_atom_id": "ATOM-001", "target_atom_id": "ATOM-002", "relation": "EXCLUDES"}]

    bundle, cert = verifier.verify_and_emit(
        query_text="Lãi suất vay mua nhà",
        transaction_date="2026-05-01",
        closed_atoms=closed_atoms,
        applied_edges=applied_edges,
        conflicts=conflicts,
    )

    assert cert is None
    assert bundle is not None
    assert bundle.decision_status == EvidenceDecisionStatus.VERIFIED
    assert bundle.canonical_bundle_hash.startswith("sha256:")
    assert len(bundle.applied_rules) == 1
    assert len(bundle.excluded_rules) == 1
    assert bundle.conflict_report.status == "CONFLICT_DETECTED"


def test_evidence_verifier_abstention_on_unresolved_footnote():
    """Test EvidenceVerifier emitting AbstentionCertificate when a required footnote is unresolved."""
    verifier = EvidenceVerifier()
    closed_atoms = [
        {
            "atom_id": "FN-001",
            "atom_type": "FOOTNOTE",
            "canonical_text": "Điều kiện áp dụng chưa xác định rõ danh mục dự án liên kết",
        }
    ]

    bundle, cert = verifier.verify_and_emit(
        query_text="Lãi suất ưu đãi dự án X",
        transaction_date="2026-05-01",
        closed_atoms=closed_atoms,
        applied_edges=[],
        conflicts=[],
    )

    assert bundle is None
    assert cert is not None
    assert cert.decision_status == EvidenceDecisionStatus.ABSTAINED
    assert "UNRESOLVED_FOOTNOTE_DEPENDENCY" in cert.reason_codes
    assert cert.canonical_certificate_hash.startswith("sha256:")
