"""Time-Travel Policy Retriever.

Enforces strict temporal validity at retrieval time so expired or unreleased
policies are filtered out before reaching any LLM prompt or decision logic.
"""

from __future__ import annotations

import logging
from datetime import date, datetime

from llama_index.core.indices.vector_store import VectorStoreIndex
from llama_index.core.schema import NodeWithScore, TextNode
from llama_index.core.vector_stores.types import (
    FilterCondition,
    FilterOperator,
    MetadataFilter,
    MetadataFilters,
)

from src.models.rag_schemas import RetrievedClause, TimeTravelFilter

logger = logging.getLogger(__name__)


class TimeTravelPolicyRetriever:
    """Retriever with strict temporal and contextual pre-filtering."""

    def __init__(
        self,
        index: VectorStoreIndex | None = None,
        nodes: list[TextNode] | None = None,
        top_k: int = 5,
    ):
        self.index = index
        self.nodes = nodes or []
        self.top_k = top_k

    def build_metadata_filters(self, filter_spec: TimeTravelFilter) -> MetadataFilters:
        """Construct LlamaIndex MetadataFilters enforcing temporal validity."""
        date_iso = filter_spec.transaction_date.isoformat()

        filters = [
            MetadataFilter(
                key="valid_from",
                value=date_iso,
                operator=FilterOperator.LTE,
            ),
            MetadataFilter(
                key="valid_to",
                value=date_iso,
                operator=FilterOperator.GTE,
            ),
        ]

        if filter_spec.customer_tier:
            filters.append(
                MetadataFilter(
                    key="customer_tier",
                    value=filter_spec.customer_tier,
                    operator=FilterOperator.EQ,
                )
            )

        return MetadataFilters(filters=filters, condition=FilterCondition.AND)

    def retrieve(
        self,
        query: str,
        time_filter: TimeTravelFilter,
        top_k: int | None = None,
    ) -> list[RetrievedClause]:
        """Execute time-travel retrieval across vector store index or in-memory nodes."""
        k = top_k or self.top_k

        if self.index:
            return self._retrieve_from_index(query, time_filter, k)
        elif self.nodes:
            return self._retrieve_from_nodes(query, time_filter, k)
        else:
            logger.warning("No index or nodes provided to TimeTravelPolicyRetriever")
            return []

    def _retrieve_from_index(
        self,
        query: str,
        time_filter: TimeTravelFilter,
        top_k: int,
    ) -> list[RetrievedClause]:
        """Query via LlamaIndex vector store with metadata filters."""
        filters = self.build_metadata_filters(time_filter)
        retriever = self.index.as_retriever(
            similarity_top_k=top_k * 2,  # retrieve extra for post-verification
            filters=filters,
        )

        nodes_with_scores: list[NodeWithScore] = retriever.retrieve(query)
        clauses: list[RetrievedClause] = []

        for item in nodes_with_scores:
            node = item.node
            meta = node.metadata or {}

            # Double verification on dates
            if not self._is_temporally_valid(meta, time_filter.transaction_date):
                continue

            clause = self._node_to_clause(node, score=item.score or 0.0)
            clauses.append(clause)
            if len(clauses) >= top_k:
                break

        return clauses

    def _retrieve_from_nodes(
        self,
        query: str,
        time_filter: TimeTravelFilter,
        top_k: int,
    ) -> list[RetrievedClause]:
        """Perform lexical / keyword search across local nodes with strict temporal filtering."""
        query_tokens = set(query.lower().split())
        scored_nodes: list[tuple[float, TextNode]] = []

        for node in self.nodes:
            meta = node.metadata or {}
            if not self._is_temporally_valid(meta, time_filter.transaction_date):
                continue

            # Check unit applicability if specified
            if time_filter.service_code:
                applicable_units = meta.get("applicable_units", ["ALL"])
                if "ALL" not in applicable_units and time_filter.service_code not in applicable_units:
                    continue

            # Calculate keyword match overlap score
            node_text = node.text.lower()
            overlap = sum(1 for token in query_tokens if token in node_text)
            score = overlap / max(len(query_tokens), 1)

            if score > 0.0:
                scored_nodes.append((score, node))

        # Sort descending by score
        scored_nodes.sort(key=lambda x: x[0], reverse=True)

        clauses: list[RetrievedClause] = []
        for score, node in scored_nodes[:top_k]:
            clauses.append(self._node_to_clause(node, score=score))

        return clauses

    def _is_temporally_valid(self, metadata: dict, target_date: date) -> bool:
        """Verify whether metadata dates encompass target_date."""
        v_from_str = metadata.get("valid_from")
        v_to_str = metadata.get("valid_to")

        if not v_from_str or not v_to_str:
            return True

        try:
            v_from = datetime.strptime(v_from_str[:10], "%Y-%m-%d").date()
            v_to = datetime.strptime(v_to_str[:10], "%Y-%m-%d").date()
            return v_from <= target_date <= v_to
        except Exception:
            return False

    def _node_to_clause(self, node: TextNode, score: float) -> RetrievedClause:
        """Convert TextNode to strongly-typed RetrievedClause."""
        meta = node.metadata or {}
        v_from = datetime.strptime(meta.get("valid_from", "2026-01-01")[:10], "%Y-%m-%d").date()
        v_to = datetime.strptime(meta.get("valid_to", "2026-12-31")[:10], "%Y-%m-%d").date()

        return RetrievedClause(
            node_id=node.id_,
            policy_id=meta.get("policy_id", "POL-UNKNOWN"),
            policy_title=meta.get("policy_name", ""),
            chapter=meta.get("chapter") or None,
            article=meta.get("article", ""),
            clause=meta.get("clause", ""),
            point=meta.get("point") or None,
            text=node.text,
            valid_from=v_from,
            valid_to=v_to,
            customer_tiers=meta.get("applicable_units", []),
            service_codes=[],
            exclusion_group=None,
            priority=0,
            score=score,
            metadata=meta,
        )
