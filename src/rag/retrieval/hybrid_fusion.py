"""Hybrid Fusion using Reciprocal Rank Fusion (RRF)."""
from __future__ import annotations

from typing import Any, Dict, List


class HybridFusion:
    """D1-2: Hybrid Fusion using Reciprocal Rank Fusion (RRF).
    
    Kết hợp kết quả từ Lexical Search (FTS/BM25) + Dense Vector Search (pgvector).
    """

    def __init__(self, k: int = 60):
        self.k = k

    def reciprocal_rank_fusion(
        self,
        lexical_results: List[Dict[str, Any]],
        dense_results: List[Dict[str, Any]],
        id_key: str = "atom_id",
    ) -> List[Dict[str, Any]]:
        """Merge lexical và dense rankings không phụ thuộc raw score bằng công thức RRF."""
        scores: Dict[str, float] = {}
        doc_map: Dict[str, Dict[str, Any]] = {}

        for rank, item in enumerate(lexical_results):
            doc_id = item[id_key]
            scores[doc_id] = scores.get(doc_id, 0.0) + 1.0 / (self.k + rank + 1)
            if doc_id not in doc_map:
                doc_map[doc_id] = dict(item)

        for rank, item in enumerate(dense_results):
            doc_id = item[id_key]
            scores[doc_id] = scores.get(doc_id, 0.0) + 1.0 / (self.k + rank + 1)
            if doc_id not in doc_map:
                doc_map[doc_id] = dict(item)

        sorted_ids = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        
        fused_results = []
        for doc_id, rrf_score in sorted_ids:
            doc = doc_map[doc_id]
            doc["rrf_score"] = float(rrf_score)
            fused_results.append(doc)

        return fused_results
