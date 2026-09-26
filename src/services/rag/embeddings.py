"""Embedding client cho pgvector (HNSW, 1536 dims — theo ARCHITECTURE.md)."""

EMBEDDING_DIMENSIONS = 1536


class EmbeddingClient:
    """Sinh vector nhúng cho chunk truy vấn và chunk chính sách."""

    async def embed(self, texts: list[str]) -> list[list[float]]:
        raise NotImplementedError("C-03: embedding client")
