"""Policy Ingestion Pipeline.

Orchestrates the conversion of Vietnamese policy markdown files into enriched
LlamaIndex TextNode objects with full cryptographic evidence metadata and temporal tags.
"""

from __future__ import annotations

import logging
from pathlib import Path

from llama_index.core.schema import TextNode

from src.services.rag.ingestion.hierarchical_parser import LegalHierarchicalParser
from src.services.rag.ingestion.metadata_enricher import PolicyMetadataEnricher

logger = logging.getLogger(__name__)


class PolicyIngestionPipeline:
    """Orchestrator for parsing, enriching, and generating LlamaIndex TextNodes."""

    def __init__(
        self,
        policies_json_path: str | Path | None = None,
        exclusions_json_path: str | Path | None = None,
    ):
        self.parser = LegalHierarchicalParser()
        self.enricher = PolicyMetadataEnricher(
            policies_path=policies_json_path,
            exclusions_path=exclusions_json_path,
        )

    def process_file(self, file_path: str | Path) -> list[TextNode]:
        """Ingest a single markdown policy file and return LlamaIndex TextNodes."""
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"Policy file not found: {path}")

        parsed_units = self.parser.parse_file(path)
        nodes: list[TextNode] = []

        for unit in parsed_units:
            metadata = self.enricher.enrich_unit(unit)

            # Construct clean deterministic node ID
            sanitized_art = unit.article.replace(" ", "_").replace(":", "")
            sanitized_cl = unit.clause.replace(" ", "_")
            node_id = f"{unit.policy_id}__{sanitized_art}__{sanitized_cl}__{unit.content_sha256[:8]}"

            node = TextNode(
                id_=node_id,
                text=unit.full_searchable_text,
                metadata=metadata,
                excluded_embed_metadata_keys=[
                    "line_start",
                    "line_end",
                    "content_sha256",
                    "exclusion_conflicts",
                    "supersedes",
                ],
                excluded_llm_metadata_keys=[
                    "content_sha256",
                    "line_start",
                    "line_end",
                ],
            )
            nodes.append(node)

        logger.info("Processed %s into %d legal clause nodes", path.name, len(nodes))
        return nodes

    def process_directory(self, dir_path: str | Path, pattern: str = "*.md") -> list[TextNode]:
        """Ingest all markdown files in a directory."""
        directory = Path(dir_path)
        if not directory.exists() or not directory.is_dir():
            raise NotADirectoryError(f"Directory not found: {directory}")

        all_nodes: list[TextNode] = []
        for file_path in sorted(directory.glob(pattern)):
            nodes = self.process_file(file_path)
            all_nodes.extend(nodes)

        logger.info(
            "Completed ingestion of directory %s: %d total clause nodes from %d files",
            directory,
            len(all_nodes),
            len(list(directory.glob(pattern))),
        )
        return all_nodes
