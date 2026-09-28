"""Hybrid Fusion using Reciprocal Rank Fusion (RRF)."""

from __future__ import annotations

from typing import Any


class HybridFusion:
    """D1-2: Hybrid Fusion using Reciprocal Rank Fusion (RRF).

    Kết hợp kết quả từ Lexical Search (FTS/BM25) + Dense Vector Search (pgvector).
    """

    def __init__(self, k: int = 60):
        self.k = k

    def reciprocal_rank_fusion(
        self,
        lexical_results: list[dict[str, Any]],
        dense_results: list[dict[str, Any]],
        id_key: str = "atom_id",
    ) -> list[dict[str, Any]]:
        """Merge lexical và dense rankings không phụ thuộc raw score bằng công thức RRF."""
        scores: dict[str, float] = {}
        doc_map: dict[str, dict[str, Any]] = {}

        def _get_id(item: dict[str, Any]) -> str:
            val = item.get(id_key) or item.get("atom_id") or item.get("node_id") or item.get("id")
            return str(val) if val else str(hash(str(item)))

        for rank, item in enumerate(lexical_results):
            doc_id = _get_id(item)
            scores[doc_id] = scores.get(doc_id, 0.0) + 1.0 / (self.k + rank + 1)
            if doc_id not in doc_map:
                doc_map[doc_id] = dict(item)

        for rank, item in enumerate(dense_results):
            doc_id = _get_id(item)
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
