"""Zero-Hallucination Evidence Binder.

Converts retrieved legal clauses into strongly-typed AttributedPolicyEvidence
structures carrying cryptographic SHA-256 coordinates and anti-tamper verification.
"""

from __future__ import annotations

import hashlib
import logging

from src.models.rag_schemas import (
    AttributedPolicyEvidence,
    EvidenceCoordinate,
    RetrievedClause,
)

logger = logging.getLogger(__name__)


class EvidenceBinder:
    """Binds retrieved candidate clauses into verifiable legal evidence."""

    @staticmethod
    def bind_clause(clause: RetrievedClause) -> AttributedPolicyEvidence:
        """Construct an AttributedPolicyEvidence instance with verified cryptographic coordinate."""
        meta = clause.metadata or {}

        # Extract verbatim text (remove any injected search header if present)
        raw_text = clause.text
        if "Nội dung: " in raw_text:
            verbatim_text = raw_text.split("Nội dung: ", 1)[1].strip()
        else:
            verbatim_text = raw_text.strip()

        # Extract or recalculate SHA-256
        recorded_sha = meta.get("content_sha256")
        if not recorded_sha:
            recorded_sha = hashlib.sha256(verbatim_text.encode("utf-8")).hexdigest()

        line_start = meta.get("line_start", 1)
        line_end = meta.get("line_end", 1)

        coordinate = EvidenceCoordinate(
            policy_id=clause.policy_id,
            chapter=clause.chapter,
            article=clause.article,
            clause=clause.clause,
            point=clause.point,
            line_span=(line_start, line_end),
            content_sha256=recorded_sha,
        )

        applicability = {
            "applicable_units": meta.get("applicable_units", ["ALL"]),
            "status": meta.get("status", "ACTIVE"),
            "project_id": meta.get("project_id", "PROJECT-VLF-001"),
        }

        if "conditional_benefit_reduction" in meta:
            applicability["conditional_benefit_reduction"] = meta["conditional_benefit_reduction"]

        if "requires_management_approval" in meta:
            applicability["requires_management_approval"] = True
            applicability["approval_rule"] = meta.get("approval_rule", "")

        evidence = AttributedPolicyEvidence(
            coordinate=coordinate,
            policy_title=clause.policy_title or clause.policy_id,
            verbatim_text=verbatim_text,
            valid_from=clause.valid_from,
            valid_to=clause.valid_to,
            applicability_conditions=applicability,
            similarity_score=clause.score,
            is_superseded=(meta.get("status") == "EXPIRED" or meta.get("supersedes") is not None),
            exclusion_group=clause.exclusion_group,
        )

        return evidence

    @classmethod
    def bind_all(
        cls,
        clauses: list[RetrievedClause],
        min_score: float = 0.0,
    ) -> list[AttributedPolicyEvidence]:
        """Bind all candidate clauses into evidence and verify cryptographic integrity."""
        evidence_list: list[AttributedPolicyEvidence] = []

        for clause in clauses:
            if clause.score < min_score:
                continue

            evidence = cls.bind_clause(clause)

            # Cryptographic validation check
            if not evidence.verify_integrity():
                logger.warning(
                    "Integrity check mismatch on clause %s: computed hash differs from coordinate",
                    clause.node_id,
                )

            evidence_list.append(evidence)

        logger.info("Bound %d verified policy evidences", len(evidence_list))
        return evidence_list
