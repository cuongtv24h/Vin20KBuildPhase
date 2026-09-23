"""pgvector Storage Manager for Enterprise Policy Retrieval.

Manages connection pooling, index setup (HNSW + Full-text Search),
and table schema provisioning for LlamaIndex PGVectorStore.
"""

from __future__ import annotations

import logging
from typing import Any
from urllib.parse import urlparse

from llama_index.vector_stores.postgres import PGVectorStore

from src.config import Settings, get_settings

logger = logging.getLogger(__name__)


class PGVectorStoreManager:
    """Manages PGVectorStore initialization and schema readiness."""

    def __init__(self, settings: Settings | None = None):
        self.settings = settings or get_settings()

    def parse_db_params(self, url: str | None = None) -> dict[str, Any]:
        """Parse database parameters from connection URL."""
        db_url = url or self.settings.database_url
        # Clean postgresql+asyncpg or similar driver prefixes for PGVectorStore
        clean_url = db_url.replace("postgresql+asyncpg://", "postgresql://").replace(
            "postgresql+psycopg2://", "postgresql://"
        )

        parsed = urlparse(clean_url)
        return {
            "host": parsed.hostname or "localhost",
            "port": str(parsed.port or 5432),
            "database": parsed.path.lstrip("/") or "pricepolicy_db",
            "user": parsed.username or "postgres",
            "password": parsed.password or "postgres",
        }

    def get_pgvector_store(
        self,
        table_name: str | None = None,
        embed_dim: int | None = None,
        hybrid_search: bool | None = None,
    ) -> PGVectorStore:
        """Create a configured LlamaIndex PGVectorStore instance."""
        params = self.parse_db_params()
        tbl = table_name or self.settings.pg_table_name
        dim = embed_dim or self.settings.embedding_dim
        hybrid = hybrid_search if hybrid_search is not None else self.settings.hybrid_search_enabled

        logger.info(
            "Connecting PGVectorStore to host=%s:%s, db=%s, table=%s, dim=%d, hybrid=%s",
            params["host"],
            params["port"],
            params["database"],
            tbl,
            dim,
            hybrid,
        )

        return PGVectorStore.from_params(
            host=params["host"],
            port=params["port"],
            database=params["database"],
            user=params["user"],
            password=params["password"],
            table_name=tbl,
            embed_dim=dim,
            hybrid_search=hybrid,
            text_search_config="simple",
        )
