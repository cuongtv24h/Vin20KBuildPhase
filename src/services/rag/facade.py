"""Unified Policy RAG Service.

Serves as the high-level facade for the Core RAG module, orchestrating:
1. Hierarchical document ingestion & metadata enrichment.
2. Temporal time-travel retrieval.
3. 3-Tier mutual exclusion pruning & TDEC graph closure.
4. Cryptographic zero-hallucination evidence binding & EvidenceBundle emission.
"""

from __future__ import annotations

import logging
from datetime import date
from pathlib import Path
from typing import Any

from llama_index.core.schema import TextNode

from src.config import Settings, get_settings
from src.models.pec_contracts import (
    AbstentionCertificate,
    EvidenceBundle,
    PolicyQuery,
    RetrievalRoute,
)
from src.models.rag_schemas import (
    AttributedPolicyEvidence,
    RetrievedClause,
    TimeTravelFilter,
)
from src.services.evidence.closure.tdec import TDECClosure
from src.services.evidence.verification.evidence_verifier import EvidenceVerifier
from src.services.rag.compiler.atomizer import PolicyAtomizer
from src.services.rag.ingestion.pipeline import PolicyIngestionPipeline
from src.services.rag.retrieval.dual_polarity import DualPolarityRetriever
from src.services.rag.retriever.evidence_binder import EvidenceBinder
from src.services.rag.retriever.pruner import ExclusionDecision, MutualExclusionPruner
from src.services.rag.retriever.time_travel_retriever import TimeTravelPolicyRetriever
from src.services.rag.vector_store.pgvector_manager import PGVectorStoreManager

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

        # Initialize existing pipeline components
        policies_json = self.canonical_dir / "policies.json"
        exclusions_json = self.canonical_dir / "mutual_exclusions.json"

        self.ingestion_pipeline = PolicyIngestionPipeline(
            policies_json_path=policies_json if policies_json.exists() else None,
            exclusions_json_path=exclusions_json if exclusions_json.exists() else None,
        )
        self.pruner = MutualExclusionPruner(exclusions_path=exclusions_json if exclusions_json.exists() else None)
        self.vector_manager = PGVectorStoreManager(settings=self.settings)

        # Initialize PEC-RAG & Two-Stage components
        self.atomizer = PolicyAtomizer()
        self.dual_retriever = DualPolarityRetriever()
        self.tdec_closure = TDECClosure(max_hops=1)
        self.evidence_verifier = EvidenceVerifier()

        self.nodes: list[TextNode] = []
        self.raw_atoms: list[dict[str, Any]] = []
        self.edges: list[dict[str, Any]] = []
        self._retriever: TimeTravelPolicyRetriever | None = None

    def load_nodes(self, nodes: list[TextNode]) -> None:
        """Directly register pre-parsed TextNodes into retriever."""
        self.nodes = nodes
        self._retriever = TimeTravelPolicyRetriever(nodes=self.nodes)

        # Đồng bộ TextNode sang dạng PolicyAtom memory pool
        self.raw_atoms = []
        for n in nodes:
            meta = n.metadata or {}
            self.raw_atoms.append(
                {
                    "atom_id": n.id_,
                    "policy_id": meta.get("policy_id", "POL-UNKNOWN"),
                    "canonical_text": n.text,
                    "retrieval_text": f"[{meta.get('policy_name', '')}] {n.text}",
                    "content_hash": meta.get("content_hash", "hash"),
                    "valid_from": meta.get("valid_from", "2026-01-01"),
                    "valid_to": meta.get("valid_to", "2026-12-31"),
                    "customer_tiers": meta.get("applicable_units", ["ALL"]),
                    "service_codes": ["ALL"],
                    "atom_type": "CLAUSE",
                }
            )

    def load_edges(self, edges: list[dict[str, Any]]) -> None:
        """Register policy edges into service for TDEC closure."""
        self.edges = edges

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
        self.load_nodes(self.nodes)
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
        """Legacy & Facade retrieval interface."""
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

        raw_candidates: list[RetrievedClause] = self._retriever.retrieve(
            query=query,
            time_filter=time_filter,
            top_k=top_k * 2,
        )

        pruned_candidates, decisions = self.pruner.prune(
            clauses=raw_candidates,
            preferred_policy_id=preferred_policy,
        )

        evidences = EvidenceBinder.bind_all(
            clauses=pruned_candidates[:top_k],
            min_score=0.0,
        )

        return evidences, decisions

    def compile_and_retrieve_bundle(
        self,
        policy_query: PolicyQuery,
        candidate_pool: list[dict[str, Any]] | None = None,
    ) -> tuple[EvidenceBundle | None, AbstentionCertificate | None]:
        """PEC-RAG Full Pipeline:
        1. Two-Stage Dual-Polarity Retrieval (Why & Why-not lanes)
        2. TDEC Graph Closure (1-2 hops expansion)
        3. 7-point Evidence Verification
        4. EvidenceBundle or AbstentionCertificate emission
        """
        pool = candidate_pool if candidate_pool is not None else self.raw_atoms

        # 1. Two-Stage Dual-Polarity Retrieval
        pos_seeds, neg_seeds = self.dual_retriever.retrieve_seeds(
            query=policy_query,
            candidate_pool=pool,
            coarse_top_k=20,
            fine_top_n=5,
        )

        # 2. TDEC Graph Closure
        atom_lookup = {a["atom_id"]: a for a in pool if "atom_id" in a}
        closed_atoms, applied_edges, conflicts = self.tdec_closure.expand_closure(
            positive_seeds=pos_seeds,
            negative_seeds=neg_seeds,
            available_edges=self.edges,
            atom_lookup=atom_lookup,
        )

        # 3. Evidence Verification & Emission
        bundle, cert = self.evidence_verifier.verify_and_emit(
            query_text=policy_query.query_text,
            transaction_date=policy_query.transaction_date,
            closed_atoms=closed_atoms,
            applied_edges=applied_edges,
            conflicts=conflicts,
            route=RetrievalRoute.T1_HYBRID,
        )

        return bundle, cert
