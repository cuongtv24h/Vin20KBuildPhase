"""Dual-Polarity Two-Stage Retriever: Positive (Why) and Negative (Why-not) Lanes."""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Tuple
import numpy as np

from src.config import get_settings
from src.models.pec_contracts import PolicyQuery
from src.rag.retrieval.bi_encoder import LocalBiEncoder
from src.rag.retrieval.hybrid_fusion import HybridFusion
from src.rag.retrieval.reranker import LocalCrossEncoderReranker
from src.rag.retrieval.temporal_scope_filter import TemporalScopeFilter

logger = logging.getLogger(__name__)
settings = get_settings()


class DualPolarityRetriever:
    """D1-2: Dual-polarity Two-Stage retrieval: Why và Why-not lanes."""

    def __init__(
        self,
        bi_encoder: LocalBiEncoder | None = None,
        reranker: LocalCrossEncoderReranker | None = None,
        fusion: HybridFusion | None = None,
    ):
        self.bi_encoder = bi_encoder or LocalBiEncoder()
        self.reranker = reranker or LocalCrossEncoderReranker()
        self.fusion = fusion or HybridFusion(k=60)
        self.temporal_filter = TemporalScopeFilter()

    def retrieve_seeds(
        self,
        query: PolicyQuery,
        candidate_pool: List[Dict[str, Any]],
        coarse_top_k: int = 20,
        fine_top_n: int = 5,
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """Thực hiện truy xuất hai giai đoạn (Coarse Hybrid + Fine Re-ranking) trên 2 cực:
        1. Positive Lane: Tìm kiếm quy tắc thỏa mãn ưu đãi (Why).
        2. Negative Lane: Tìm kiếm điều khoản loại trừ, xung đột, điều kiện phụ (Why-not).
        """
        # Bước 1: Lọc cứng Temporal / Scope
        valid_pool = self.temporal_filter.filter_memory_candidates(
            atoms=candidate_pool,
            transaction_date=query.transaction_date,
            customer_tier=query.project_scope,
        )
        if not valid_pool:
            return [], []

        # Bước 2: Tạo Negative Query (Exclusion/Prerequisite focus)
        pos_query_text = query.query_text
        neg_query_text = f"{query.query_text} điều kiện loại trừ không áp dụng đồng thời hạn chế bắt buộc"

        # Bước 3: Chạy Stage 1 Coarse Retrieval (Lexical + Dense + RRF) cho từng cực
        pos_coarse = self._stage1_coarse_search(pos_query_text, valid_pool, top_k=coarse_top_k)
        neg_coarse = self._stage1_coarse_search(neg_query_text, valid_pool, top_k=coarse_top_k)

        # Bước 4: Chạy Stage 2 Fine Re-ranking (Cross-Encoder)
        if settings.reranker_enabled:
            pos_final = self.reranker.rerank(
                query=pos_query_text,
                documents=pos_coarse,
                top_n=fine_top_n,
                text_key="retrieval_text",
            )
            neg_final = self.reranker.rerank(
                query=neg_query_text,
                documents=neg_coarse,
                top_n=fine_top_n,
                text_key="retrieval_text",
            )
        else:
            pos_final = pos_coarse[:fine_top_n]
            neg_final = neg_coarse[:fine_top_n]

        return pos_final, neg_final

    def _stage1_coarse_search(
        self,
        query_text: str,
        pool: List[Dict[str, Any]],
        top_k: int,
    ) -> List[Dict[str, Any]]:
        """Giai đoạn 1: Quét nhanh Vector Dense Cosine và Lexical FTS, hợp nhất bằng RRF."""
        # 1. Lexical Search
        q_tokens = set(query_text.lower().split())
        lex_scored = []
        for doc in pool:
            text = str(doc.get("retrieval_text", "")).lower()
            d_tokens = set(text.split())
            overlap = len(q_tokens.intersection(d_tokens))
            score = overlap / max(len(q_tokens), 1)
            item = dict(doc)
            item["lex_score"] = float(score)
            lex_scored.append(item)
        lex_scored.sort(key=lambda x: x["lex_score"], reverse=True)
        lex_top = lex_scored[:top_k]

        # 2. Dense Vector Search
        q_vector = np.array(self.bi_encoder.embed_query(query_text), dtype=np.float32)
        dense_scored = []
        for doc in pool:
            emb = doc.get("embedding")
            if emb is not None:
                d_vec = np.array(emb, dtype=np.float32)
                sim = float(np.dot(q_vector, d_vec) / (np.linalg.norm(q_vector) * np.linalg.norm(d_vec) + 1e-9))
            else:
                sim = 0.0
            item = dict(doc)
            item["dense_score"] = sim
            dense_scored.append(item)
        dense_scored.sort(key=lambda x: x["dense_score"], reverse=True)
        dense_top = dense_scored[:top_k]

        # 3. RRF Fusion
        fused = self.fusion.reciprocal_rank_fusion(lex_top, dense_top, id_key="atom_id")
        return fused[:top_k]
