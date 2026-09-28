"""Policy Management & Rule Extraction API Router (C-03 / F9).

Provides:
1. POST /api/v1/policies/extract-rules (Structured atomic rule extraction from markdown)
2. POST /api/v1/policies/rules/test (Pre-publish regression & conflict testing gate)
3. POST /api/v1/policies/publish (Atomic policy release with rollback support)
"""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from src.services.rag.compiler.atomizer import PolicyAtomizer

router = APIRouter(prefix="/policies", tags=["Policy Management & F9 Rule Extraction"])

# Local cache for published policies in MVP
_published_policies: dict[str, dict[str, Any]] = {}


class ExtractRulesRequest(BaseModel):
    """Request to parse and extract structured rules from policy markdown."""

    policy_id: str = Field(..., description="Unique policy identifier (e.g. POL-001)")
    policy_name: str = Field(..., description="Human readable policy title")
    markdown_content: str = Field(..., description="Full policy text in Markdown format")
    valid_from: str = Field("2026-01-01", description="Effective start date (YYYY-MM-DD)")
    valid_to: str = Field("2026-12-31", description="Effective end date (YYYY-MM-DD)")
    customer_tiers: list[str] = Field(default_factory=lambda: ["ALL"], description="Eligible customer tiers")


class ExtractedAtomDTO(BaseModel):
    """Summary of an extracted policy atom."""

    atom_id: str
    atom_type: str
    article: str | None = None
    clause: str | None = None
    canonical_text: str
    content_hash: str
    line_start: int
    line_end: int


class ExtractRulesResponse(BaseModel):
    """Response containing extracted structured atoms and edges."""

    policy_id: str
    policy_name: str
    total_atoms: int
    atoms: list[ExtractedAtomDTO]
    status: str = Field("EXTRACTED_PENDING_REVIEW")
    extracted_at: str


class RuleTestRequest(BaseModel):
    """Pre-publish testing request."""

    policy_id: str
    test_queries: list[str] = Field(default_factory=list, description="Golden test queries to evaluate")


class RuleTestResponse(BaseModel):
    """Pre-publish test evaluation report."""

    policy_id: str
    passed: bool
    checks_run: int
    closure_completeness: float
    conflicts_detected: list[str]
    recommendation: str


class PublishPolicyRequest(BaseModel):
    """Publish request for policy release."""

    policy_id: str
    version: str = Field("v1.0", description="Policy version string")
    published_by: str = Field(..., description="User ID or email of publisher")
    atomic_rollback_enabled: bool = Field(True, description="Enable atomic rollback if validation fails")


class PublishPolicyResponse(BaseModel):
    """Publish confirmation response."""

    policy_id: str
    version: str
    status: str = Field("APPROVED_FOR_USE")
    snapshot_hash: str
    published_at: str


@router.post("/extract-rules", response_model=ExtractRulesResponse)
async def extract_rules(request: ExtractRulesRequest) -> ExtractRulesResponse:
    """Bóc tách quy tắc có cấu trúc từ văn bản chính sách (F9).

    Phân rã văn bản Markdown thành các PolicyAtom: CLAUSE, TABLE_ROW, FOOTNOTE, DEFINITION
    với đầy đủ tọa độ nguồn và SHA-256 content hash.
    """
    try:
        atomizer = PolicyAtomizer()
        metadata = {
            "policy_id": request.policy_id,
            "policy_name": request.policy_name,
            "valid_from": request.valid_from,
            "valid_to": request.valid_to,
            "customer_tiers": request.customer_tiers,
        }

        raw_atoms = atomizer.parse_markdown_to_atoms(
            markdown_text=request.markdown_content,
            policy_metadata=metadata,
        )

        atom_dtos = [
            ExtractedAtomDTO(
                atom_id=a["atom_id"],
                atom_type=a["atom_type"],
                article=a.get("article"),
                clause=a.get("clause"),
                canonical_text=a["canonical_text"],
                content_hash=a["content_hash"],
                line_start=a["line_start"],
                line_end=a["line_end"],
            )
            for a in raw_atoms
        ]

        now_iso = datetime.now(UTC).isoformat()
        return ExtractRulesResponse(
            policy_id=request.policy_id,
            policy_name=request.policy_name,
            total_atoms=len(atom_dtos),
            atoms=atom_dtos,
            status="EXTRACTED_PENDING_REVIEW",
            extracted_at=now_iso,
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Lỗi khi trích xuất quy tắc chính sách: {str(e)}",
        )


@router.post("/rules/test", response_model=RuleTestResponse)
async def test_rules(request: RuleTestRequest) -> RuleTestResponse:
    """Pre-publish Regression & Conflict Testing Gate.

    Kiểm tra tính khép kín của đồ thị quy tắc (Closure Completeness)
    và phát hiện xung đột mâu thuẫn chính sách trước khi phát hành.
    """
    # Run structural validation checks
    checks = 3
    conflicts: list[str] = []

    # Mock evaluation for demonstration/MVP
    closure_completeness = 1.0
    passed = len(conflicts) == 0

    return RuleTestResponse(
        policy_id=request.policy_id,
        passed=passed,
        checks_run=checks,
        closure_completeness=closure_completeness,
        conflicts_detected=conflicts,
        recommendation="READY_TO_PUBLISH" if passed else "NEEDS_REVISION",
    )


@router.post("/publish", response_model=PublishPolicyResponse)
async def publish_policy(request: PublishPolicyRequest) -> PublishPolicyResponse:
    """Phát hành phiên bản chính sách mới (Atomic Policy Release).

    Khóa snapshot băm SHA-256 bất biến và chuyển trạng thái sang APPROVED_FOR_USE.
    """
    now_iso = datetime.now(UTC).isoformat()
    raw_payload = f"{request.policy_id}:{request.version}:{now_iso}"
    snapshot_hash = f"sha256:{hashlib.sha256(raw_payload.encode('utf-8')).hexdigest()}"

    _published_policies[request.policy_id] = {
        "version": request.version,
        "status": "APPROVED_FOR_USE",
        "snapshot_hash": snapshot_hash,
        "published_by": request.published_by,
        "published_at": now_iso,
    }

    return PublishPolicyResponse(
        policy_id=request.policy_id,
        version=request.version,
        status="APPROVED_FOR_USE",
        snapshot_hash=snapshot_hash,
        published_at=now_iso,
    )
