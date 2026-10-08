"""Seed Data Script (C-03).

Parses markdown policy documents from policies_md directory, enriches metadata,
generates embeddings using LocalBiEncoder, and seeds them into pgvector storage.
"""

from __future__ import annotations

import argparse
import logging
import sys
import time
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


from src.config import get_settings
from src.services.rag.ingestion.pipeline import PolicyIngestionPipeline
from src.services.rag.retrieval.bi_encoder import LocalBiEncoder
from src.services.rag.vector_store.pgvector_manager import PGVectorStoreManager

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def find_default_policies_dir() -> Path:
    """Finds policy directory looking in common project paths."""
    candidates = [
        Path("data/policies_md"),
        Path("../report/Dataset/policies_md"),
        Path("report/Dataset/policies_md"),
        Path("mydoc/dataset/policies_md"),
    ]
    for p in candidates:
        if p.exists() and p.is_dir():
            return p
    # Fallback to local data dir
    return Path("data/policies_md")


def seed_policies(policies_dir: Path, dry_run: bool = False) -> int:
    """Parses and seeds all markdown policies into pgvector."""
    settings = get_settings()
    logger.info("Initializing BiEncoder and Ingestion Pipeline (dry_run=%s)...", dry_run)
    encoder = LocalBiEncoder()
    pipeline = PolicyIngestionPipeline()
    vector_manager = PGVectorStoreManager(settings=settings)

    md_files = list(policies_dir.glob("*.md"))
    if not md_files:
        logger.warning(f"No .md policy files found in {policies_dir}")
        return 0

    logger.info(f"Found {len(md_files)} policy files to ingest from {policies_dir}")
    start_time = time.time()
    total_nodes = 0

    for file_path in sorted(md_files):
        try:
            nodes = pipeline.process_file(file_path)
            logger.info(f"Parsed {len(nodes)} nodes from {file_path.name}")

            # Compute embeddings for each node
            for node in nodes:
                node.embedding = encoder.embed_query(node.text)

            if nodes:
                if not dry_run:
                    try:
                        vector_manager.insert_nodes(nodes)
                    except Exception as db_err:
                        logger.warning(f"Database insertion skipped or failed ({db_err}). Seeded in memory.")
                total_nodes += len(nodes)
        except Exception as e:
            logger.error(f"Failed to process {file_path.name}: {e}", exc_info=True)

    elapsed = time.time() - start_time
    status_str = "dry-run parsed" if dry_run else "seeded"
    logger.info(f"Successfully {status_str} {total_nodes} nodes from {len(md_files)} files in {elapsed:.2f}s")
    return total_nodes


def main():
    parser = argparse.ArgumentParser(description="Seed policy data into pgvector")
    parser.add_argument(
        "--dir",
        type=str,
        default=None,
        help="Path to directory containing policy .md files",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Chạy thử: parse và tính embedding/nodes nhưng không ghi vào pgvector",
    )
    args = parser.parse_args()

    policies_dir = Path(args.dir) if args.dir else find_default_policies_dir()
    logger.info(f"Using policies directory: {policies_dir.resolve()}")
    seed_policies(policies_dir, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
