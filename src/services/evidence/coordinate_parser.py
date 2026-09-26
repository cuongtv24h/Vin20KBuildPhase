"""Evidence Coordinate Parser & Normalizer (C-04 / F4).

Standardizes source coordinates (doc_id, content_hash, line_span, section, quote)
and provides tamper-evident validation for claim-level auditability.
"""

from __future__ import annotations

import hashlib

from pydantic import BaseModel, Field

from src.models.rag_schemas import EvidenceCoordinate


class NormalizedCoordinate(BaseModel):
    """Normalized coordinate representation for claim-level evidence."""
    doc_id: str = Field(..., description="Document identifier (e.g. POL-001)")
    content_hash: str = Field(..., description="SHA-256 hash of verbatim quote")
    line_start: int = Field(1, description="Start line in source markdown")
    line_end: int = Field(1, description="End line in source markdown")
    chapter: str | None = Field(None, description="Chapter heading")
    article: str | None = Field(None, description="Article heading (e.g. Điều 5)")
    clause: str | None = Field(None, description="Clause heading (e.g. Khoản 2)")
    point: str | None = Field(None, description="Point identifier (e.g. Điểm a)")
    quote: str = Field(..., description="Verbatim text quote")

    def verify_hash(self) -> bool:
        """Verifies that the quote text produces the expected content_hash."""
        computed = hashlib.sha256(self.quote.encode("utf-8")).hexdigest()
        expected = self.content_hash.replace("sha256:", "")
        return computed == expected


class CoordinateParser:
    """Parser and normalizer for policy coordinates."""

    @staticmethod
    def parse_citation(citation_str: str) -> dict[str, str]:
        """Parses human-readable citation strings like:
        '[POL-001, Điều 5, Khoản 2, Điểm a:L15-L20#sha256:abc]'
        """
        result: dict[str, str] = {}
        # Clean brackets
        clean = citation_str.strip("[]")
        parts = [p.strip() for p in clean.split(",")]
        if parts:
            result["doc_id"] = parts[0]

        for part in parts[1:]:
            if part.startswith("Điều"):
                result["article"] = part
            elif part.startswith("Khoản"):
                result["clause"] = part
            elif part.startswith("Điểm"):
                subparts = part.split(":")
                result["point"] = subparts[0]
                if len(subparts) > 1:
                    span_and_hash = subparts[1]
                    if "#" in span_and_hash:
                        span, hash_val = span_and_hash.split("#", 1)
                        result["span"] = span
                        result["hash"] = hash_val
                    else:
                        result["span"] = span_and_hash
        return result

    @staticmethod
    def normalize_from_coordinate(
        coord: EvidenceCoordinate,
        verbatim_text: str,
    ) -> NormalizedCoordinate:
        """Converts an internal EvidenceCoordinate into a NormalizedCoordinate."""
        expected_hash = coord.content_sha256 or hashlib.sha256(verbatim_text.encode("utf-8")).hexdigest()
        return NormalizedCoordinate(
            doc_id=coord.policy_id,
            content_hash=expected_hash if expected_hash.startswith("sha256:") else f"sha256:{expected_hash}",
            line_start=coord.line_span[0] if coord.line_span else 1,
            line_end=coord.line_span[1] if coord.line_span else 1,
            chapter=coord.chapter,
            article=coord.article,
            clause=coord.clause,
            point=coord.point,
            quote=verbatim_text,
        )
