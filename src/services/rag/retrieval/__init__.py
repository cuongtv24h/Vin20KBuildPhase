"""Time-Travel & Policy Retrieval Package (C-02).

Exports TimeTravelPolicyRetriever, DualPolarityRetriever, and retrieval algorithms.
"""

from src.services.rag.retrieval.bi_encoder import LocalBiEncoder
from src.services.rag.retrieval.dual_polarity import DualPolarityRetriever
from src.services.rag.retrieval.hybrid_fusion import HybridFusion
from src.services.rag.retrieval.reranker import LocalCrossEncoderReranker
from src.services.rag.retrieval.temporal_scope_filter import TemporalScopeFilter
from src.services.rag.retriever.pruner import ExclusionDecision, MutualExclusionPruner
from src.services.rag.retriever.time_travel_retriever import TimeTravelPolicyRetriever

__all__ = [
    "TimeTravelPolicyRetriever",
    "DualPolarityRetriever",
    "MutualExclusionPruner",
    "ExclusionDecision",
    "LocalBiEncoder",
    "LocalCrossEncoderReranker",
    "HybridFusion",
    "TemporalScopeFilter",
]
