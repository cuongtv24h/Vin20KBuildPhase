"""RAG & Policy Intelligence Services (C-02, C-03).

Exports PolicyRAGService facade, retrieval engines, ingestion pipelines, and parsers.
"""

from src.services.rag.compiler.atomizer import PolicyAtomizer
from src.services.rag.ingestion.hierarchical_parser import LegalHierarchicalParser, ParsedLegalUnit
from src.services.rag.ingestion.pipeline import PolicyIngestionPipeline
from src.services.rag.retrieval.dual_polarity import DualPolarityRetriever
from src.services.rag.retriever.time_travel_retriever import TimeTravelPolicyRetriever
from src.services.rag.service import PolicyRAGService

__all__ = [
    "PolicyRAGService",
    "TimeTravelPolicyRetriever",
    "DualPolarityRetriever",
    "PolicyIngestionPipeline",
    "LegalHierarchicalParser",
    "ParsedLegalUnit",
    "PolicyAtomizer",
]
