"""Policy Atomizer & Compiler for D1-1 Ingestion."""
from __future__ import annotations

import hashlib
import re
from typing import Any, Dict, List
from src.models.pec_contracts import PolicyAtom, PolicyAtomType
from src.rag.retrieval.bi_encoder import LocalBiEncoder


class PolicyAtomizer:
    """D1-1: Policy Compiler.
    
    Phân tách tài liệu chính sách thành các PolicyAtom có cấu trúc phân cấp:
    - CLAUSE (Điều/Khoản)
    - TABLE_ROW (Dòng bảng biểu)
    - FOOTNOTE (Ghi chú chân trang/điều khoản)
    - DEFINITION (Định nghĩa thuật ngữ)
    """

    def __init__(self, bi_encoder: LocalBiEncoder | None = None):
        self.bi_encoder = bi_encoder or LocalBiEncoder()

    def create_atom(
        self,
        raw_text: str,
        atom_type: PolicyAtomType,
        metadata: Dict[str, Any],
        chapter: str | None = None,
        article: str | None = None,
        clause: str | None = None,
        point: str | None = None,
        line_start: int = 1,
        line_end: int = 1,
    ) -> Dict[str, Any]:
        """Tạo một Policy Atom với đầy đủ thông tin provenance, canonical text và retrieval text."""
        clean_text = raw_text.strip()
        content_hash = hashlib.sha256(clean_text.encode("utf-8")).hexdigest()

        # Build deterministic context text: [Policy / Section Path / Article / Clause] Canonical Text
        section_path = metadata.get("section_path", "")
        policy_title = metadata.get("policy_name", metadata.get("policy_id", "POL"))
        context_prefix = f"[{policy_title} > {section_path}]" if section_path else f"[{policy_title}]"
        
        canonical_text = clean_text
        retrieval_text = f"{context_prefix} {clean_text}"

        atom_id = metadata.get("atom_id") or f"ATOM-{content_hash[:8]}"

        # Compute embedding using local bi-encoder
        embedding = self.bi_encoder.embed_query(retrieval_text)

        return {
            "atom_id": atom_id,
            "policy_id": metadata.get("policy_id", "POL-DEFAULT"),
            "atom_type": atom_type.value if hasattr(atom_type, "value") else str(atom_type),
            "chapter": chapter,
            "article": article,
            "clause": clause,
            "point": point,
            "parent_atom_id": metadata.get("parent_atom_id"),
            "page_number": metadata.get("page_number", 1),
            "section_path": section_path,
            "table_coordinates": metadata.get("table_coordinates"),
            "line_start": line_start,
            "line_end": line_end,
            "canonical_text": canonical_text,
            "retrieval_text": retrieval_text,
            "content_hash": content_hash,
            "valid_from": metadata.get("valid_from", "2026-01-01"),
            "valid_to": metadata.get("valid_to", "2026-12-31"),
            "customer_tiers": metadata.get("customer_tiers", ["ALL"]),
            "service_codes": metadata.get("service_codes", ["ALL"]),
            "channel": metadata.get("channel", "ALL"),
            "embedding": embedding,
            "embedding_model_id": self.bi_encoder.model_name,
        }

    def parse_markdown_to_atoms(
        self,
        markdown_text: str,
        policy_metadata: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        """Phân tích tài liệu Markdown theo cấu trúc Điều/Khoản và sinh danh sách atoms."""
        lines = markdown_text.splitlines()
        atoms: List[Dict[str, Any]] = []

        current_chapter: str | None = None
        current_article: str | None = None
        current_clause: str | None = None
        clause_lines: List[str] = []
        clause_start_line = 1

        def flush_clause(line_idx: int):
            nonlocal clause_lines, current_clause, clause_start_line
            if clause_lines:
                text_content = "\n".join(clause_lines).strip()
                if text_content:
                    meta = dict(policy_metadata)
                    meta["section_path"] = f"{current_chapter or ''} > {current_article or ''}".strip(" >")
                    
                    # Xác định kiểu atom: Footnote, Table Row hay Clause
                    if text_content.startswith("[*]") or "ghi chú" in text_content.lower() or "footnote" in text_content.lower():
                        atom_type = PolicyAtomType.FOOTNOTE
                    else:
                        atom_type = PolicyAtomType.CLAUSE

                    atom = self.create_atom(
                        raw_text=text_content,
                        atom_type=atom_type,
                        metadata=meta,
                        chapter=current_chapter,
                        article=current_article,
                        clause=current_clause,
                        line_start=clause_start_line,
                        line_end=line_idx,
                    )
                    atoms.append(atom)
                clause_lines = []

        for idx, line in enumerate(lines, start=1):
            stripped = line.strip()
            if not stripped:
                continue

            # Bắt tiêu đề Chương
            if re.match(r"^(#+|Chương\s+[IVXLCDM\d]+)", stripped, re.IGNORECASE):
                flush_clause(idx - 1)
                current_chapter = stripped.lstrip("#").strip()
                clause_start_line = idx
            # Bắt Điều khoản (Article)
            elif re.match(r"^(Điều\s+\d+|###?\s+Điều\s+\d+)", stripped, re.IGNORECASE):
                flush_clause(idx - 1)
                current_article = stripped.lstrip("#").strip()
                clause_start_line = idx
            # Bắt Khoản (Clause)
            elif re.match(r"^(\d+\.\s+|Khoản\s+\d+)", stripped, re.IGNORECASE):
                flush_clause(idx - 1)
                current_clause = stripped
                clause_lines.append(stripped)
                clause_start_line = idx
            else:
                clause_lines.append(stripped)

        flush_clause(len(lines))
        return atoms
