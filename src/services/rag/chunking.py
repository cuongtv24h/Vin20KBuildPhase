"""Hierarchical Chunking & Coordinate Preservation (C-03 / F4).

Provides coordinate-preserving parser for legal documents and markdown tables/headings.
"""

from src.services.rag.ingestion.hierarchical_parser import (
    LegalHierarchicalParser,
    ParsedLegalUnit,
)

__all__ = [
    "LegalHierarchicalParser",
    "ParsedLegalUnit",
]
