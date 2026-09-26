"""End-to-End Integration Tests for Core RAG with real Dataset."""

from datetime import date
from pathlib import Path

from src.services.rag.service import PolicyRAGService


def test_end_to_end_rag_with_real_dataset():
    canonical_dir = Path("/Users/mac/AITC/PROJECT/report/Dataset/canonical")
    policies_dir = Path("/Users/mac/AITC/PROJECT/report/Dataset/policies_md")

    if not policies_dir.exists():
        return

    rag_service = PolicyRAGService(
        policies_dir=policies_dir,
        canonical_dir=canonical_dir,
    )

    total_ingested = rag_service.ingest_from_directory()
    assert total_ingested > 0

    # Test 1: Search for early payment discount during active period (2026-03-01)
    evidences, decisions = rag_service.search_policies(
        query="chiết khấu thanh toán sớm 95%",
        transaction_date=date(2026, 3, 1),
        service_code="2BR",
        top_k=3,
    )

    assert len(evidences) > 0
    # Every evidence must pass cryptographic integrity check
    for ev in evidences:
        assert ev.verify_integrity() is True
        assert ev.valid_from <= date(2026, 3, 1) <= ev.valid_to

    # Test 2: Search for early payment in 2025 (should exclude 2026 policy)
    evidences_2025, _ = rag_service.search_policies(
        query="chiết khấu thanh toán sớm 95%",
        transaction_date=date(2025, 3, 1),
        service_code="2BR",
        top_k=3,
    )
    # Ensure POL-2026-VLF-EARLY is NOT in 2025 results
    assert not any(ev.coordinate.policy_id == "POL-2026-VLF-EARLY" for ev in evidences_2025)

    # Test 3: Hard Mutual Exclusion test: query triggering both Early payment and Bank loan
    evidences_conflict, conflict_decisions = rag_service.search_policies(
        query="thanh toán sớm 95% hoặc hỗ trợ lãi suất ngân hàng 0%",
        transaction_date=date(2026, 3, 1),
        service_code="2BR",
        preferred_policy="POL-2026-VLF-EARLY",
        top_k=5,
    )

    # Since preferred_policy is EARLY, BANK must be pruned if a conflict was detected
    if any(d.conflict_id == "CONF-01" for d in conflict_decisions):
        assert not any(ev.coordinate.policy_id == "POL-2026-VLF-BANK" for ev in evidences_conflict)
