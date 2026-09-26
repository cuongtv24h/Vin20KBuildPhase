"""Local Cross-Encoder Re-ranker for Stage 2 Fine Ranking."""
from __future__ import annotations

import logging
from typing import Any
from src.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class LocalCrossEncoderReranker:
    """Mô hình Cross-Encoder chấm điểm tương quan trực tiếp giữa (Query, Doc)."""

    def __init__(
        self,
        model_name: str | None = None,
        max_length: int = 512,
    ):
        self.model_name = model_name or settings.reranker_model_id
        self.max_length = max_length
        self._ce_model = None

        try:
            import torch
            from sentence_transformers import CrossEncoder
            device = "cuda" if torch.cuda.is_available() else ("mps" if torch.backends.mps.is_available() else "cpu")
            logger.info("Initializing CrossEncoder '%s' on device '%s'...", self.model_name, device)
            self._ce_model = CrossEncoder(self.model_name, max_length=max_length, device=device)
        except Exception as e:
            logger.info("CrossEncoder not loaded (%s). Using deterministic local fallback reranker.", e)

    def rerank(
        self,
        query: str,
        documents: list[dict[str, Any]],
        top_n: int = 5,
        text_key: str = "content",
    ) -> list[dict[str, Any]]:
        """Nhận vào danh sách ứng viên từ Stage 1, chấm điểm lại và trả về Top-N chính xác nhất."""
        if not documents:
            return []

        if self._ce_model is not None:
            pairs = [[query, doc.get(text_key, "")] for doc in documents]
            scores = self._ce_model.predict(pairs, show_progress_bar=False)
            
            ranked_docs = []
            for doc, score in zip(documents, scores):
                doc_copy = dict(doc)
                doc_copy["rerank_score"] = float(score)
                ranked_docs.append(doc_copy)
                
            ranked_docs.sort(key=lambda x: x["rerank_score"], reverse=True)
            return ranked_docs[:top_n]

        # Deterministic token overlap & sequence matching fallback
        q_tokens = set(query.lower().split())
        ranked_docs = []
        for doc in documents:
            text = str(doc.get(text_key, "")).lower()
            d_tokens = set(text.split())
            if not q_tokens:
                score = 0.0
            else:
                overlap = len(q_tokens.intersection(d_tokens))
                # Coverage ratio + density bonus
                coverage = overlap / len(q_tokens)
                density = overlap / max(len(d_tokens), 1)
                score = 0.7 * coverage + 0.3 * density
                
            doc_copy = dict(doc)
            doc_copy["rerank_score"] = float(score)
            ranked_docs.append(doc_copy)

        ranked_docs.sort(key=lambda x: x["rerank_score"], reverse=True)
        return ranked_docs[:top_n]
