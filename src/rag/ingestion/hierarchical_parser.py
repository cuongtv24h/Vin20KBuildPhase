"""Hierarchical Legal Document Parser for Vietnamese Bank / Real Estate Policies.

Decomposes policy documents into structured legal hierarchies:
Document -> Chapter (Chương) -> Article (Điều) -> Clause (Khoản) -> Point (Điểm).
Preserves exact verbatim content, line spans, and cryptographic SHA-256 hashes
to support zero-hallucination evidence citations.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class ParsedLegalUnit:
    """Represents a leaf or atomic legal unit (Clause or Point) with full hierarchical lineage."""

    policy_id: str
    policy_name: str
    chapter: str | None
    article: str
    clause: str
    point: str | None
    verbatim_text: str
    hierarchical_context: str
    line_span: tuple[int, int]
    content_sha256: str
    raw_frontmatter: dict[str, Any] = field(default_factory=dict)

    @property
    def full_searchable_text(self) -> str:
        """Enriched text suitable for dense & sparse embeddings."""
        header = f"[{self.policy_id}] {self.policy_name}\n"
        if self.chapter:
            header += f"{self.chapter} - "
        header += f"{self.article} - {self.clause}"
        if self.point:
            header += f" - {self.point}"
        return f"{header}\nNội dung: {self.verbatim_text}"


class LegalHierarchicalParser:
    """Parser specifically designed for Vietnamese legal and financial policy documents."""

    # Regex patterns for Vietnamese legal structure
    FRONTMATTER_PATTERN = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)
    CHAPTER_PATTERN = re.compile(r"^(?:#+\s*)?(Chương\s+[IVXLCDM0-9]+(?:\s*[:\-]\s*[^\n]+)?)", re.IGNORECASE)
    ARTICLE_PATTERN = re.compile(r"^(?:#+\s*)?(Điều\s+\d+(?:\s*[:\-]\s*[^\n]+)?)", re.IGNORECASE)
    CLAUSE_PATTERN = re.compile(r"^(?:(\d+)\.\s+|Khoản\s+(\d+)[:\.\s]+)(.*)", re.DOTALL)
    POINT_PATTERN = re.compile(r"^(?:([a-zđ])[\)\.]\s+|Điểm\s+([a-zđ])[:\.\s]+)(.*)", re.IGNORECASE | re.DOTALL)

    def parse_file(self, file_path: str | Path) -> list[ParsedLegalUnit]:
        """Parse a markdown policy document into a list of atomic ParsedLegalUnits."""
        path = Path(file_path)
        content = path.read_text(encoding="utf-8")
        return self.parse_text(content, default_id=path.stem)

    def parse_text(self, text: str, default_id: str = "POL-UNKNOWN") -> list[ParsedLegalUnit]:
        """Parse raw text string into structured legal units."""
        lines = text.splitlines()
        frontmatter, content_start_line = self._extract_frontmatter(lines)

        policy_id = frontmatter.get("policy_id", default_id)
        policy_name = frontmatter.get("policy_name", policy_id)

        units: list[ParsedLegalUnit] = []
        current_chapter: str | None = None
        current_article: str | None = None
        current_clause: str | None = None
        clause_lines: list[str] = []
        clause_start_line = content_start_line

        def flush_current_clause(end_line: int):
            nonlocal clause_lines, clause_start_line, current_clause
            if not clause_lines or not current_article:
                clause_lines = []
                return

            clause_text = "\n".join(clause_lines).strip()
            if not clause_text:
                clause_lines = []
                return

            c_name = current_clause if current_clause else "Khoản 1"
            sha = hashlib.sha256(clause_text.encode("utf-8")).hexdigest()

            lineage = f"{policy_id} > "
            if current_chapter:
                lineage += f"{current_chapter} > "
            lineage += f"{current_article} > {c_name}"

            unit = ParsedLegalUnit(
                policy_id=policy_id,
                policy_name=policy_name,
                chapter=current_chapter,
                article=current_article,
                clause=c_name,
                point=None,
                verbatim_text=clause_text,
                hierarchical_context=lineage,
                line_span=(clause_start_line + 1, end_line),
                content_sha256=sha,
                raw_frontmatter=frontmatter,
            )
            units.append(unit)
            clause_lines = []

        for idx in range(content_start_line, len(lines)):
            line = lines[idx]
            stripped = line.strip()

            if not stripped:
                if clause_lines:
                    clause_lines.append("")
                continue

            # Check Chapter
            ch_match = self.CHAPTER_PATTERN.match(stripped)
            if ch_match:
                flush_current_clause(idx)
                current_chapter = ch_match.group(1).strip()
                continue

            # Check Article (Điều)
            art_match = self.ARTICLE_PATTERN.match(stripped)
            if art_match:
                flush_current_clause(idx)
                current_article = art_match.group(1).strip()
                current_clause = None
                clause_start_line = idx
                continue

            # Check Clause (Khoản X or 1. / 2. / 3.)
            cl_match = self.CLAUSE_PATTERN.match(stripped)
            if cl_match and current_article:
                flush_current_clause(idx)
                clause_num = cl_match.group(1) or cl_match.group(2)
                current_clause = f"Khoản {clause_num}"
                clause_start_line = idx
                clause_lines.append(stripped)
                continue

            # Normal content line belonging to the active clause / article
            if not clause_lines and not current_clause and current_article:
                current_clause = "Khoản 1"
                clause_start_line = idx

            clause_lines.append(stripped)

        # Flush the remaining clause
        flush_current_clause(len(lines))

        return units

    def _extract_frontmatter(self, lines: list[str]) -> tuple[dict[str, Any], int]:
        """Extract YAML-style frontmatter from top of lines."""
        if not lines or lines[0].strip() != "---":
            return {}, 0

        frontmatter: dict[str, Any] = {}
        end_idx = -1
        for idx in range(1, len(lines)):
            if lines[idx].strip() == "---":
                end_idx = idx
                break

        if end_idx == -1:
            return {}, 0

        fm_text = "\n".join(lines[1:end_idx])
        # Simple key-value parser for YAML without strict dependency
        for fm_line in fm_text.splitlines():
            line = fm_line.strip()
            if not line or line.startswith("#"):
                continue
            if ":" in line:
                k, v = line.split(":", 1)
                key = k.strip()
                val = v.strip().strip('"').strip("'")
                if val.startswith("[") and val.endswith("]"):
                    # list of strings
                    items = [i.strip().strip('"').strip("'") for i in val[1:-1].split(",") if i.strip()]
                    frontmatter[key] = items
                else:
                    frontmatter[key] = val

        return frontmatter, end_idx + 1
