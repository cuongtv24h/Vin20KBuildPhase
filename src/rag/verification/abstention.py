from src.models.pec_contracts import AbstentionCertificate, EvidenceDecisionStatus
import hashlib

class AbstentionGenerator:
    """
    D1-4: Sinh AbstentionArtifact khi máy không thể đưa ra quyết định
    để nhường lại cho con người (Manager) ra quyết định duyệt.
    """
    
    def generate(self, missing_facts: list, unresolved_edges: list) -> AbstentionCertificate:
        """
        Tạo AbstentionCertificate với reason_codes máy đọc được.
        """
        cert_hash = hashlib.sha256(b"mock_cert_hash").hexdigest()
        
        return AbstentionCertificate(
            decision_status=EvidenceDecisionStatus.ABSTAINED,
            query_fingerprint="sha256:...",
            policy_snapshot_hash="sha256:...",
            reason_codes=["UNRESOLVED_EXCLUSION_EDGE"],
            missing_facts=missing_facts,
            unresolved_edges=unresolved_edges,
            recommended_human_action="POLICY_ADMIN_REVIEW",
            canonical_certificate_hash=f"sha256:{cert_hash}"
        )
