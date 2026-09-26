"""Database initialization and schema migration runner."""
from __future__ import annotations

import asyncio
import logging

from sqlalchemy import text

from src.db.models import Base
from src.db.session import engine

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def init_database():
    """Ensure pgvector extension, create all tables, and build HNSW & GIN indexes."""
    logger.info("Starting Database Schema Initialization on Supabase...")

    async with engine.begin() as conn:
        # 1. Enable pgvector extension
        logger.info("Ensuring 'vector' extension is enabled...")
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector;"))

        # 2. Create tables
        logger.info("Creating tables from SQLAlchemy models...")
        await conn.run_sync(Base.metadata.create_all)

        # 3. Create HNSW Vector Index on policy_atoms.embedding
        logger.info("Creating HNSW Cosine vector index on policy_atoms...")
        await conn.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_atoms_hnsw
            ON policy_atoms USING hnsw (embedding vector_cosine_ops)
            WITH (m = 16, ef_construction = 64);
        """))

        # 4. Create B-Tree Index for Temporal Querying
        logger.info("Creating Temporal B-Tree index on policy_atoms...")
        await conn.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_atoms_temporal
            ON policy_atoms (valid_from, valid_to);
        """))

        # 5. Create Full-Text Search (FTS) Index for Lexical Retrieval
        logger.info("Creating Full-Text Search index on policy_atoms...")
        await conn.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_atoms_fts
            ON policy_atoms USING gin (to_tsvector('simple', retrieval_text));
        """))

        # 6. Create Indexes for Policy Edges
        logger.info("Creating indexes on policy_edges...")
        await conn.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_edges_source_status
            ON policy_edges (source_atom_id, validation_status);
        """))
        await conn.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_edges_target
            ON policy_edges (target_atom_id);
        """))

    logger.info("✅ Database schema and indexes successfully initialized!")


if __name__ == "__main__":
    asyncio.run(init_database())
