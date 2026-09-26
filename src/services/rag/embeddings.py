"""Policy Embeddings & Vector Store Client (C-03).

Provides local bi-encoder embeddings and PostgreSQL/pgvector client.
"""

from src.services.rag.retrieval.bi_encoder import LocalBiEncoder
from src.services.rag.vector_store.pgvector_manager import PGVectorStoreManager

__all__ = [
    "LocalBiEncoder",
    "PGVectorStoreManager",
]
