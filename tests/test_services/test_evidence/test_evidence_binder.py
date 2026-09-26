"""Unit tests for EvidenceBinder."""

import hashlib
from datetime import date

from src.models.rag_schemas import RetrievedClause
from src.services.rag.retriever.evidence_binder import EvidenceBinder


def test_evidence_binding_and_integrity_check():
    text = "Văn bản này quy định mức chiết khấu thanh toán sớm 8.0%."
    sha = hashlib.sha256(text.encode("utf-8")).hexdigest()

    clause = RetrievedClause(
        node_id="node_123",
        policy_id="POL-2026-VLF-EARLY",
        policy_title="Chương trình Chiết khấu Thanh toán Sớm 95%",
        chapter="Chương I",
        article="Điều 2: Mức Ưu đãi Chiết khấu",
        clause="Khoản 1",
        point="Điểm a",
        text=f"[POL-2026-VLF-EARLY] Điều 2 - Khoản 1\nNội dung: {text}",
        valid_from=date(2026, 1, 1),
        valid_to=date(2026, 6, 30),
        score=0.92,
        metadata={
            "content_sha256": sha,
            "line_start": 15,
            "line_end": 16,
            "applicable_units": ["1BR", "2BR", "3BR"],
        },
    )

    evidence = EvidenceBinder.bind_clause(clause)

    # 1. Verify coordinate structure
    assert evidence.coordinate.policy_id == "POL-2026-VLF-EARLY"
    assert evidence.coordinate.chapter == "Chương I"
    assert evidence.coordinate.article == "Điều 2: Mức Ưu đãi Chiết khấu"
    assert evidence.coordinate.clause == "Khoản 1"
    assert evidence.coordinate.point == "Điểm a"
    assert evidence.coordinate.line_span == (15, 16)
    assert evidence.coordinate.citation_path == "POL-2026-VLF-EARLY > Chương I > Điều 2: Mức Ưu đãi Chiết khấu > Khoản 1 > Điểm a"

    # 2. Verify verbatim text extraction
    assert evidence.verbatim_text == text

    # 3. Verify cryptographic integrity check succeeds
    assert evidence.verify_integrity() is True

    # 4. Verify tampering detection (if someone alters the verbatim text)
    evidence.verbatim_text = "Văn bản này quy định mức chiết khấu bịa đặt 50%."
    assert evidence.verify_integrity() is False
