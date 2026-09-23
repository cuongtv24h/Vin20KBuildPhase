"""Policy Metadata Enricher.

Cross-references parsed legal clauses with canonical policy definitions (policies.json)
and mutual exclusion matrices (mutual_exclusions.json) to attach structured temporal
and constraint attributes (valid_from, valid_to, applicable_units, exclusion_groups).
"""

from __future__ import annotations

import json
from datetime import date, datetime
from pathlib import Path
from typing import Any

from src.rag.ingestion.hierarchical_parser import ParsedLegalUnit


class PolicyMetadataEnricher:
    """Enriches ParsedLegalUnit objects with canonical metadata and conflict rules."""

    def __init__(
        self,
        policies_path: str | Path | None = None,
        exclusions_path: str | Path | None = None,
    ):
        self.policies_lookup: dict[str, dict[str, Any]] = {}
        self.exclusion_matrix: list[dict[str, Any]] = []

        if policies_path and Path(policies_path).exists():
            self._load_policies(Path(policies_path))

        if exclusions_path and Path(exclusions_path).exists():
            self._load_exclusions(Path(exclusions_path))

    def _load_policies(self, path: Path) -> None:
        """Load canonical policies JSON."""
        data = json.loads(path.read_text(encoding="utf-8"))
        for item in data:
            pid = item.get("policy_id")
            if pid:
                self.policies_lookup[pid] = item

    def _load_exclusions(self, path: Path) -> None:
        """Load canonical mutual exclusions JSON."""
        self.exclusion_matrix = json.loads(path.read_text(encoding="utf-8"))

    def enrich_unit(self, unit: ParsedLegalUnit) -> dict[str, Any]:
        """Produce a complete metadata dictionary for pgvector / LlamaIndex Node.

        Guarantees presence of valid_from, valid_to, and exclusion mapping.
        """
        canonical = self.policies_lookup.get(unit.policy_id, {})

        # Parse valid_from / valid_to
        valid_from_str = (
            canonical.get("effective_from")
            or unit.raw_frontmatter.get("effective_from")
            or "2026-01-01"
        )
        valid_to_str = (
            canonical.get("effective_to")
            or unit.raw_frontmatter.get("effective_to")
            or "2026-12-31"
        )

        valid_from_date = self._parse_date(valid_from_str, default=date(2026, 1, 1))
        valid_to_date = self._parse_date(valid_to_str, default=date(2026, 12, 31))

        # Scope and applicable units
        scope = canonical.get("scope", {})
        applicable_units = (
            scope.get("applicable_units")
            or unit.raw_frontmatter.get("applicable_units")
            or ["ALL"]
        )
        if isinstance(applicable_units, str):
            applicable_units = [applicable_units]

        project_id = scope.get("project_id") or "PROJECT-VLF-001"
        status = canonical.get("status", "ACTIVE")
        supersedes = canonical.get("supersedes") or unit.raw_frontmatter.get("supersedes")

        # Check mutual exclusion groups
        exclusion_conflicts: list[dict[str, Any]] = []
        for exc in self.exclusion_matrix:
            if exc.get("policy_a") == unit.policy_id or exc.get("policy_b") == unit.policy_id:
                exclusion_conflicts.append(exc)

        metadata = {
            "policy_id": unit.policy_id,
            "policy_name": unit.policy_name,
            "chapter": unit.chapter or "",
            "article": unit.article,
            "clause": unit.clause,
            "point": unit.point or "",
            "line_start": unit.line_span[0],
            "line_end": unit.line_span[1],
            "content_sha256": unit.content_sha256,
            "hierarchical_context": unit.hierarchical_context,
            "valid_from": valid_from_date.isoformat(),
            "valid_to": valid_to_date.isoformat(),
            "applicable_units": applicable_units,
            "project_id": project_id,
            "status": status,
            "supersedes": supersedes,
            "exclusion_conflicts": exclusion_conflicts,
        }

        return metadata

    def _parse_date(self, date_str: str, default: date) -> date:
        """Parse ISO date or datetime string to a date object."""
        if not date_str:
            return default
        try:
            # Handle standard ISO: 2026-01-01T00:00:00+07:00 or 2026-01-01
            if "T" in date_str:
                return datetime.fromisoformat(date_str).date()
            return datetime.strptime(date_str[:10], "%Y-%m-%d").date()
        except Exception:
            return default
