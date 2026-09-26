"""Local Bi-Encoder for Stage 1 Dense Vector Generation."""
from __future__ import annotations

import hashlib
import logging
from collections.abc import Sequence

import numpy as np

from src.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class LocalBiEncoder:
    """Mô hình Bi-Encoder chạy cục bộ dùng để sinh embedding vector cho văn bản."""

    def __init__(self, model_name: str | None = None, dimension: int | None = None):
        self.model_name = model_name or settings.embedding_model_id
        self.dimension = dimension or settings.embedding_dim
        self._st_model = None

        # Thử nạp SentenceTransformer nếu thư viện sẵn có
        try:
            import torch
            from sentence_transformers import SentenceTransformer
            device = "cuda" if torch.cuda.is_available() else ("mps" if torch.backends.mps.is_available() else "cpu")
            logger.info("Initializing SentenceTransformer '%s' on device '%s'...", self.model_name, device)
            self._st_model = SentenceTransformer(self.model_name, device=device)
            self.dimension = self._st_model.get_sentence_embedding_dimension()
        except Exception as e:
            logger.info("SentenceTransformer not loaded (%s). Using deterministic local fallback encoder.", e)

    def embed_documents(self, texts: Sequence[str], batch_size: int = 64) -> list[list[float]]:
        """Vector hóa danh sách tài liệu."""
        if not texts:
            return []

        if self._st_model is not None:
            embeddings = self._st_model.encode(
                list(texts),
                batch_size=batch_size,
                show_progress_bar=len(texts) > 200,
                normalize_embeddings=True,
                convert_to_numpy=True,
            )
            return embeddings.tolist()

        # Deterministic feature hashing fallback
        return [self._hash_embed(t) for t in texts]

    def embed_query(self, query: str) -> list[float]:
        """Vector hóa câu hỏi truy vấn của người dùng."""
        if self._st_model is not None:
            embedding = self._st_model.encode(
                query,
                normalize_embeddings=True,
                convert_to_numpy=True,
            )
            return embedding.tolist()

        return self._hash_embed(query)

    def encode_query(self, query: str) -> list[float]:
        """Alias for embed_query."""
        return self.embed_query(query)

    def encode(self, texts: Sequence[str] | str, **kwargs) -> list[list[float]] | list[float]:
        """SentenceTransformer style encode method."""
        if isinstance(texts, str):
            return self.embed_query(texts)
        return self.embed_documents(texts)

    def _hash_embed(self, text: str) -> list[float]:
        """Sinh vector giả lập xác định (deterministic) dựa trên n-gram hashing."""
        vec = np.zeros(self.dimension, dtype=np.float32)
        tokens = text.lower().split()
        if not tokens:
            return vec.tolist()

        for token in tokens:
            h = int(hashlib.md5(token.encode("utf-8")).hexdigest(), 16)
            idx = h % self.dimension
            val = ((h >> 8) % 100) / 100.0 - 0.5
            vec[idx] += val

        norm = np.linalg.norm(vec)
        if norm > 0:
            vec = vec / norm
        return vec.tolist()
