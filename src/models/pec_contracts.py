from enum import Enum
from pydantic import BaseModel, Field
from typing import List, Optional, Any

class PolicyAtomType(str, Enum):
    CLAUSE = "CLAUSE"
    TABLE_ROW = "TABLE_ROW"
    FOOTNOTE = "FOOTNOTE"
    DEFINITION = "DEFINITION"

class PolicyEdgeType(str, Enum):
    REQUIRES = "REQUIRES"
    EXCLUDES = "EXCLUDES"
    SUPERSEDES = "SUPERSEDES"
    REFERENCES = "REFERENCES"
    TABLE_HAS_FOOTNOTE = "TABLE_HAS_FOOTNOTE"

class EvidenceDecisionStatus(str, Enum):
    VERIFIED = "VERIFIED"
    ABSTAINED = "ABSTAINED"

class RetrievalRoute(str, Enum):
    T0_EXACT = "T0_EXACT"
    T1_HYBRID = "T1_HYBRID"
    T2_RERANKED = "T2_RERANKED"

class PolicyAtom(BaseModel):
    atom_id: str
    atom_type: PolicyAtomType
    content_hash: str
    canonical_text: str
    parent: Optional[str] = None
    page: Optional[int] = None
    section: Optional[str] = None
    table_coordinates: Optional[str] = None

class PolicyEdge(BaseModel):
    edge_id: str
    source_atom_id: str
    edge_type: PolicyEdgeType
    target_atom_id: str
    source_authority: str
    validation_status: str
    reviewed_by: Optional[str] = None
    edge_version: str

class EvidenceItem(BaseModel):
    atom_id: str
    canonical_text: str
    similarity_score: Optional[float] = None
    applied_via_edge: Optional[str] = None

class PolicyQuery(BaseModel):
    query_text: str
    transaction_date: str
    project_scope: Optional[str] = None

class RetrievalTrace(BaseModel):
    route: RetrievalRoute
    positive_seed_ids: List[str] = Field(default_factory=list)
    negative_seed_ids: List[str] = Field(default_factory=list)
    closure_edge_ids: List[str] = Field(default_factory=list)
    closure_hops: int = 1

class ConflictReport(BaseModel):
    status: str
    pairs: List[Any] = Field(default_factory=list)

class EvidenceBundle(BaseModel):
    schema_version: str = "evidence-bundle.v1"
    bundle_id: str
    decision_status: EvidenceDecisionStatus = EvidenceDecisionStatus.VERIFIED
    query_fingerprint: str
    transaction_context_hash: str
    policy_snapshot_hash: str
    active_policy_versions: List[str] = Field(default_factory=list)
    applied_rules: List[EvidenceItem] = Field(default_factory=list)
    excluded_rules: List[EvidenceItem] = Field(default_factory=list)
    uncertain_rules: List[EvidenceItem] = Field(default_factory=list)
    conflict_report: ConflictReport
    missing_facts: List[str] = Field(default_factory=list)
    retrieval_trace: RetrievalTrace
    canonical_bundle_hash: str

class AbstentionCertificate(BaseModel):
    schema_version: str = "abstention-certificate.v1"
    decision_status: EvidenceDecisionStatus = EvidenceDecisionStatus.ABSTAINED
    query_fingerprint: str
    policy_snapshot_hash: str
    reason_codes: List[str] = Field(default_factory=list)
    missing_facts: List[str] = Field(default_factory=list)
    unresolved_edges: List[str] = Field(default_factory=list)
    conflicting_atom_ids: List[str] = Field(default_factory=list)
    recommended_human_action: str
    canonical_certificate_hash: str

class ResolvedPolicySnapshot(BaseModel):
    snapshot_hash: str
    active_policies: List[str] = Field(default_factory=list)

class EvidenceBundleRef(BaseModel):
    bundle_id: str
    bundle_hash: str
    decision_status: str
    resolved_policy_snapshot_hash: str

class PricingRequest(BaseModel):
    """Payload representing a call to the Pricing Engine."""
    evidence_bundle_ref: EvidenceBundleRef
    # Trong thực tế sẽ có thêm các trường về account, balance... ở đây
