"""Unified Policy RAG Service.

Serves as the high-level facade for the Core RAG module, orchestrating:
1. Hierarchical document ingestion & metadata enrichment.
2. Temporal time-travel retrieval.
3. 3-Tier mutual exclusion pruning.
4. Cryptographic zero-hallucination evidence binding.
"""

from __future__ import annotations

import logging
from datetime import date
from pathlib import Path

from llama_index.core.schema import TextNode

from src.config import Settings, get_settings
from src.models.rag_schemas import (
    AttributedPolicyEvidence,
    RetrievedClause,
    TimeTravelFilter,
)
from src.rag.ingestion.pipeline import PolicyIngestionPipeline
from src.rag.retriever.evidence_binder import EvidenceBinder
from src.rag.retriever.pruner import ExclusionDecision, MutualExclusionPruner
from src.rag.retriever.time_travel_retriever import TimeTravelPolicyRetriever
from src.rag.vector_store.pgvector_manager import PGVectorStoreManager

logger = logging.getLogger(__name__)


class PolicyRAGService:
    """Enterprise RAG Service facade for PricePolicy AI Agent."""

    def __init__(
        self,
        settings: Settings | None = None,
        policies_dir: str | Path | None = None,
        canonical_dir: str | Path | None = None,
    ):
        self.settings = settings or get_settings()
        self.canonical_dir = Path(canonical_dir) if canonical_dir else Path("data/canonical")
        self.policies_dir = Path(policies_dir) if policies_dir else Path("data/policies_md")

        # Initialize components
        policies_json = self.canonical_dir / "policies.json"
        exclusions_json = self.canonical_dir / "mutual_exclusions.json"

        self.ingestion_pipeline = PolicyIngestionPipeline(
            policies_json_path=policies_json if policies_json.exists() else None,
            exclusions_json_path=exclusions_json if exclusions_json.exists() else None,
        )
        self.pruner = MutualExclusionPruner(
            exclusions_path=exclusions_json if exclusions_json.exists() else None
        )
        self.vector_manager = PGVectorStoreManager(settings=self.settings)

        self.nodes: list[TextNode] = []
        self._retriever: TimeTravelPolicyRetriever | None = None

    def load_nodes(self, nodes: list[TextNode]) -> None:
        """Directly register pre-parsed TextNodes into retriever."""
        self.nodes = nodes
        self._retriever = TimeTravelPolicyRetriever(nodes=self.nodes)

    def ingest_from_directory(
        self,
        policies_path: str | Path | None = None,
    ) -> int:
        """Ingest policy markdown documents from a directory into memory/retriever."""
        target_dir = Path(policies_path) if policies_path else self.policies_dir
        if not target_dir.exists():
            logger.warning("Policies directory not found: %s", target_dir)
            return 0

        self.nodes = self.ingestion_pipeline.process_directory(target_dir)
        self._retriever = TimeTravelPolicyRetriever(nodes=self.nodes)
        return len(self.nodes)

    def search_policies(
        self,
        query: str,
        transaction_date: date,
        customer_tier: str | None = None,
        service_code: str | None = None,
        preferred_policy: str | None = None,
        top_k: int = 5,
    ) -> tuple[list[AttributedPolicyEvidence], list[ExclusionDecision]]:
        """Perform end-to-end Time-Travel retrieval, pruning, and evidence binding.

        Args:
            query: Natural language question or policy search terms
            transaction_date: Evaluation date for temporal enforcement
            customer_tier: Optional customer classification (e.g. VIP, STANDARD)
            service_code: Optional unit type or product (e.g. 1BR, 2BR, 3BR)
            preferred_policy: Optional policy ID to give preference in hard conflicts
            top_k: Maximum candidate clauses to retrieve

        Returns:
            Tuple of (List of AttributedPolicyEvidence, List of ExclusionDecisions)
        """
        if not self._retriever:
            if self.nodes:
                self._retriever = TimeTravelPolicyRetriever(nodes=self.nodes)
            else:
                logger.warning("No retriever or nodes available in PolicyRAGService")
                return [], []

        time_filter = TimeTravelFilter(
            transaction_date=transaction_date,
            customer_tier=customer_tier,
            service_code=service_code,
        )

        # 1. Time-Travel Retrieval
        raw_candidates: list[RetrievedClause] = self._retriever.retrieve(
            query=query,
            time_filter=time_filter,
            top_k=top_k * 2,  # retrieve extra for pruning
        )

        # 2. Mutual Exclusion Pruning
        pruned_candidates, decisions = self.pruner.prune(
            clauses=raw_candidates,
            preferred_policy_id=preferred_policy,
        )

        # 3. Cryptographic Evidence Binding
        evidences = EvidenceBinder.bind_all(
            clauses=pruned_candidates[:top_k],
            min_score=0.0,
        )

        return evidences, decisions
