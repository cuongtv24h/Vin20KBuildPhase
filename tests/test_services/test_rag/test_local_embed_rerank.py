"""Unit tests for Local Bi-Encoder, Cross-Encoder Re-ranker, and Hybrid RRF."""
from __future__ import annotations

from src.services.rag.retrieval.bi_encoder import LocalBiEncoder
from src.services.rag.retrieval.hybrid_fusion import HybridFusion
from src.services.rag.retrieval.reranker import LocalCrossEncoderReranker


def test_local_bi_encoder():
    """Test Local Bi-Encoder embedding output format and dimension."""
    encoder = LocalBiEncoder(dimension=384)
    texts = [
        "Chính sách ưu đãi lãi suất vay mua nhà",
        "Quy định về phí trả nợ trước hạn",
    ]
    embeddings = encoder.embed_documents(texts)
    assert len(embeddings) == 2
    assert len(embeddings[0]) == 384
    assert len(embeddings[1]) == 384

    query_vec = encoder.embed_query("vay mua nhà")
    assert len(query_vec) == 384


def test_hybrid_rrf_fusion():
    """Test Reciprocal Rank Fusion combining lexical and dense lists."""
    fusion = HybridFusion(k=60)
    lexical = [
        {"atom_id": "ATOM-001", "text": "Clause 1"},
        {"atom_id": "ATOM-002", "text": "Clause 2"},
    ]
    dense = [
        {"atom_id": "ATOM-002", "text": "Clause 2"},
        {"atom_id": "ATOM-003", "text": "Clause 3"},
    ]
    fused = fusion.reciprocal_rank_fusion(lexical, dense, id_key="atom_id")

    # ATOM-002 is in both, so it should rank highest
    assert len(fused) == 3
    assert fused[0]["atom_id"] == "ATOM-002"
    assert "rrf_score" in fused[0]


def test_cross_encoder_reranker():
    """Test Stage 2 Cross-Encoder reranking order."""
    reranker = LocalCrossEncoderReranker()
    candidates = [
        {"atom_id": "A", "retrieval_text": "Quy định về thẻ tín dụng quốc tế"},
        {"atom_id": "B", "retrieval_text": "Ưu đãi lãi suất vay mua nhà dành cho khách hàng VIP"},
        {"atom_id": "C", "retrieval_text": "Biểu phí chuyển tiền nội địa"},
    ]
    query = "Lãi suất vay mua nhà khách VIP"
    reranked = reranker.rerank(query, candidates, top_n=2, text_key="retrieval_text")

    assert len(reranked) == 2
    assert reranked[0]["atom_id"] == "B"
    assert "rerank_score" in reranked[0]
