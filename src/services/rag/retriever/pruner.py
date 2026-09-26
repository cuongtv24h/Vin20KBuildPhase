"""Mutual Exclusion Pruning Post-Processor.

Applies enterprise conflict matrices (TIER_1_HARD, TIER_2_CONDITIONAL, TIER_3_AMBIGUOUS)
to prune mutually exclusive policies and annotate conditional concessions before
passing candidate evidence to the generation phase.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from src.models.rag_schemas import RetrievedClause

logger = logging.getLogger(__name__)


@dataclass
class ExclusionDecision:
    """Record of an exclusion or modification decision made on a policy clause."""

    conflict_id: str
    tier: str
    action: str
    winner_policy: str
    pruned_policy: str | None
    reason: str


class MutualExclusionPruner:
    """Post-processor that detects and resolves mutual exclusions across retrieved clauses."""

    def __init__(self, exclusions_path: str | Path | None = None):
        self.rules: list[dict[str, Any]] = []
        if exclusions_path and Path(exclusions_path).exists():
            self.load_rules(Path(exclusions_path))

    def load_rules(self, path: Path) -> None:
        """Load exclusion rules from JSON file."""
        self.rules = json.loads(path.read_text(encoding="utf-8"))
        logger.info("Loaded %d mutual exclusion rules from %s", len(self.rules), path)

    def prune(
        self,
        clauses: list[RetrievedClause],
        preferred_policy_id: str | None = None,
    ) -> tuple[list[RetrievedClause], list[ExclusionDecision]]:
        """Filter out mutually exclusive clauses based on scoring, preference, and rules.

        Returns:
            Tuple of (surviving_clauses, exclusion_decisions)
        """
        if not clauses or not self.rules:
            return clauses, []

        surviving: list[RetrievedClause] = list(clauses)
        decisions: list[ExclusionDecision] = []

        # Map policies present in the current retrieved set
        policy_ids: set[str] = {c.policy_id for c in surviving}

        for rule in self.rules:
            p_a = rule.get("policy_a")
            p_b = rule.get("policy_b")
            tier = rule.get("tier", "TIER_1_HARD")
            action = rule.get("action", "MUTUALLY_EXCLUSIVE")
            conflict_id = rule.get("conflict_id", "CONF-UNKNOWN")

            # Check if both policies (or wildcard) exist in retrieved results
            has_a = p_a in policy_ids
            has_b = (p_b in policy_ids) or (p_b == "ALL_POLICIES" and has_a)

            if not (has_a and has_b):
                continue

            if tier == "TIER_1_HARD" and action == "MUTUALLY_EXCLUSIVE":
                # Hard conflict: Only one can survive
                # Preference priority -> higher score priority
                if preferred_policy_id == p_a:
                    winner, loser = p_a, p_b
                elif preferred_policy_id == p_b:
                    winner, loser = p_b, p_a
                else:
                    # Compare max scores of clauses from each policy
                    score_a = max((c.score for c in surviving if c.policy_id == p_a), default=0.0)
                    score_b = max((c.score for c in surviving if c.policy_id == p_b), default=0.0)
                    if score_a >= score_b:
                        winner, loser = p_a, p_b
                    else:
                        winner, loser = p_b, p_a

                # Prune the loser clauses
                surviving = [c for c in surviving if c.policy_id != loser]
                policy_ids.discard(loser)

                decisions.append(
                    ExclusionDecision(
                        conflict_id=conflict_id,
                        tier=tier,
                        action=action,
                        winner_policy=winner,
                        pruned_policy=loser,
                        reason=rule.get("description", f"Hard exclusion between {p_a} and {p_b}"),
                    )
                )
                logger.info(
                    "Pruned policy %s in favor of %s due to conflict %s",
                    loser,
                    winner,
                    conflict_id,
                )

            elif tier == "TIER_2_CONDITIONAL" and action == "REDUCE_BENEFIT":
                # Annotate metadata with conditional reduction constraint
                for c in surviving:
                    if c.policy_id in (p_a, p_b):
                        c.metadata["conditional_benefit_reduction"] = rule.get(
                            "condition", "Benefit reduced due to combination."
                        )

                decisions.append(
                    ExclusionDecision(
                        conflict_id=conflict_id,
                        tier=tier,
                        action=action,
                        winner_policy=p_a,
                        pruned_policy=None,
                        reason=rule.get("condition", "Benefit reduced"),
                    )
                )

            elif tier == "TIER_3_AMBIGUOUS" and action == "SAFE_ABSTAIN":
                # Mark as requiring human / CEO escalation
                for c in surviving:
                    if c.policy_id == p_a:
                        c.metadata["requires_management_approval"] = True
                        c.metadata["approval_rule"] = rule.get("condition", "Escalation needed")

                decisions.append(
                    ExclusionDecision(
                        conflict_id=conflict_id,
                        tier=tier,
                        action=action,
                        winner_policy=p_a,
                        pruned_policy=None,
                        reason=rule.get("condition", "Ambiguous boundary requires safe escalation"),
                    )
                )

        return surviving, decisions
