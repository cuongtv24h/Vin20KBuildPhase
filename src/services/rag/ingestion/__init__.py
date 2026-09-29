"""Ingestion module for hierarchical legal parsing and metadata enrichment."""

from src.services.rag.ingestion.hierarchical_parser import LegalHierarchicalParser, ParsedLegalUnit
from src.services.rag.ingestion.metadata_enricher import PolicyMetadataEnricher
from src.services.rag.ingestion.pipeline import PolicyIngestionPipeline

__all__ = [
    "LegalHierarchicalParser",
    "ParsedLegalUnit",
    "PolicyMetadataEnricher",
    "PolicyIngestionPipeline",
]
