"""Abstention Certificate Generator for Safe Governance."""
from __future__ import annotations

import hashlib
import json
from typing import List, Optional
from src.models.pec_contracts import AbstentionCertificate, EvidenceDecisionStatus


class AbstentionGenerator:
    """Tạo chứng chỉ từ chối quyết định an toàn (Safe Abstention Certificate)."""

    @staticmethod
    def generate(
        query_text: str,
        policy_snapshot_hash: str,
        reason_codes: List[str],
        missing_facts: Optional[List[str]] = None,
        unresolved_edges: Optional[List[str]] = None,
        conflicting_atom_ids: Optional[List[str]] = None,
        recommended_action: str = "POLICY_ADMIN_REVIEW",
    ) -> AbstentionCertificate:
        """Tạo AbstentionCertificate chuẩn hóa kèm canonical SHA-256 hash."""
        query_fingerprint = f"sha256:{hashlib.sha256(query_text.encode('utf-8')).hexdigest()}"
        
        cert_data = {
            "schema_version": "abstention-certificate.v1",
            "decision_status": EvidenceDecisionStatus.ABSTAINED.value,
            "query_fingerprint": query_fingerprint,
            "policy_snapshot_hash": policy_snapshot_hash,
            "reason_codes": sorted(reason_codes),
            "missing_facts": sorted(missing_facts or []),
            "unresolved_edges": sorted(unresolved_edges or []),
            "conflicting_atom_ids": sorted(conflicting_atom_ids or []),
            "recommended_human_action": recommended_action,
        }

        canonical_json = json.dumps(cert_data, sort_keys=True, ensure_ascii=False)
        cert_hash = f"sha256:{hashlib.sha256(canonical_json.encode('utf-8')).hexdigest()}"

        return AbstentionCertificate(
            schema_version="abstention-certificate.v1",
            decision_status=EvidenceDecisionStatus.ABSTAINED,
            query_fingerprint=query_fingerprint,
            policy_snapshot_hash=policy_snapshot_hash,
            reason_codes=cert_data["reason_codes"],
            missing_facts=cert_data["missing_facts"],
            unresolved_edges=cert_data["unresolved_edges"],
            conflicting_atom_ids=cert_data["conflicting_atom_ids"],
            recommended_human_action=recommended_action,
            canonical_certificate_hash=cert_hash,
        )
