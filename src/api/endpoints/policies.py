"""Policy Management & Rule Extraction API Router (C-03 / F9).

Provides:
1. POST /api/v1/policies/extract-rules (Structured atomic rule extraction from markdown)
2. POST /api/v1/policies/rules/test (Pre-publish regression & conflict testing gate)
3. POST /api/v1/policies/publish (Atomic policy release with rollback support)
"""

from __future__ import annotations

import hashlib
import re
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from src.api.deps import Principal, get_current_principal
from src.api.endpoints.evaluation import _BENCHMARK_RUNS_CACHE
from src.services.pricing.evaluation import (
    DEFAULT_POLICY_REF,
    load_golden_cases,
    run_benchmark_evaluation,
)
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
    version: str = Field("v1.0", description="Phiên bản chuẩn bị ban hành")
    test_queries: list[str] = Field(default_factory=list, description="Golden test queries to evaluate")


class RuleTestCheck(BaseModel):
    """Một hạng mục kiểm tra trước ban hành (contract `RulesTestCheck` của frontend)."""

    code: str
    label: str
    status: str = Field(..., description="PASS, WARN hoặc FAIL")
    detail: str


class RuleTestResponse(BaseModel):
    """Pre-publish test evaluation report."""

    policy_id: str
    passed: bool
    checks_run: int
    closure_completeness: float
    conflicts_detected: list[str]
    recommendation: str

    # ─── Contract hiển thị của frontend (`RulesTestReport`) ───────────────────
    checked_at: str = Field(default="", description="Thời điểm chạy cổng kiểm thử (ISO-8601)")
    checks: list[RuleTestCheck] = Field(default_factory=list)
    conflict_findings: list[dict[str, Any]] = Field(default_factory=list)
    regression: dict[str, int] = Field(default_factory=dict, description="{passed, total} ca golden khớp tuyệt đối")
    can_publish: bool = Field(default=False, description="Văn bản đủ điều kiện ban hành")
    benchmark_run_id: str = Field(default="", description="Mã lần chạy kiểm thử công thức làm bằng chứng")
    policy_alignment: str = Field(default="PINNED", description="MATCH/DRIFT so với bản golden đang khoá")


class PolicyBenchmarkEvidence(BaseModel):
    """Bằng chứng kiểm thử công thức gắn với một lần ban hành chính sách."""

    benchmark_run_id: str
    total_cases: int
    passed_cases: int
    accuracy_rate: float
    golden_policy_ref: str
    policy_alignment: str
    approved_at: str


class PublishPolicyRequest(BaseModel):
    """Publish request for policy release."""

    policy_id: str
    version: str = Field("v1.0", description="Policy version string")
    published_by: str = Field(..., description="User ID or email of publisher")
    atomic_rollback_enabled: bool = Field(True, description="Enable atomic rollback if validation fails")
    enforce_test_gate: bool = Field(True, description="Bắt buộc cổng kiểm thử đạt mới cho ban hành")


class PublishPolicyResponse(BaseModel):
    """Publish confirmation response."""

    policy_id: str
    version: str
    status: str = Field("APPROVED_FOR_USE")
    snapshot_hash: str
    published_at: str
    benchmark: PolicyBenchmarkEvidence | None = Field(
        default=None,
        description="Bằng chứng kiểm thử công thức đi kèm — chính sách mới ban hành luôn có bản ghi chất lượng",
    )


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


_POLICY_ID_RE = re.compile(r"^[A-Z0-9][A-Z0-9._-]{2,63}$")


def _run_publish_gate(policy_id: str, version: str, test_queries: list[str]) -> RuleTestResponse:
    """Chạy cổng kiểm thử trước ban hành trên **engine thật**.

    Khác bản stub cũ (3 check hình thức), cổng này thực sự:
    1. Chạy lại toàn bộ 17 ca golden FCS v2.6 (`run_benchmark_evaluation`) — bắt hồi quy công thức.
    2. Kiểm tra trạng thái ban hành để không ghi đè phiên bản đang hiệu lực.
    3. Ghi nhận độ lệch giữa văn bản đang ban hành và bản golden đang khoá (`policy_alignment`).
    """
    checked_at = datetime.now(UTC).isoformat()
    checks: list[RuleTestCheck] = []
    conflicts: list[str] = []

    def add(code: str, label: str, status_value: str, detail: str) -> None:
        checks.append(RuleTestCheck(code=code, label=label, status=status_value, detail=detail))

    # 1. Mã văn bản hợp lệ
    if _POLICY_ID_RE.match(policy_id or ""):
        add("POLICY_ID", "Mã văn bản hợp lệ", "PASS", policy_id)
    else:
        add("POLICY_ID", "Mã văn bản hợp lệ", "FAIL", f"Mã không hợp lệ: '{policy_id}'")
        conflicts.append(f"POLICY_ID:{policy_id}")

    # 2. Bộ golden fixture sẵn sàng
    try:
        golden_cases = load_golden_cases()
        add("GOLDEN_SUITE", "Bộ ca vàng sẵn sàng", "PASS" if golden_cases else "FAIL", f"{len(golden_cases)} ca golden")
    except FileNotFoundError as exc:
        golden_cases = []
        add("GOLDEN_SUITE", "Bộ ca vàng sẵn sàng", "FAIL", str(exc))
        conflicts.append("GOLDEN_SUITE:MISSING")

    # 3. Hồi quy công thức — chạy thật, không mock
    if golden_cases:
        report = run_benchmark_evaluation(policy_id=policy_id, policy_version=version)
        _BENCHMARK_RUNS_CACHE[report.run_id] = report
        regression_ok = report.accuracy_rate >= 100.0
        add(
            "FORMULA_REGRESSION",
            "Kiểm thử hồi quy công thức",
            "PASS" if regression_ok else "FAIL",
            f"{report.passed_cases}/{report.total_cases} ca khớp tuyệt đối · Δ tối đa "
            f"{max((c.delta_vnd for c in report.results), default=0)} VNĐ · run {report.run_id}",
        )
        if not regression_ok:
            conflicts.append(f"FORMULA_REGRESSION:{report.failed_cases}_CASES")
    else:
        report = None
        add("FORMULA_REGRESSION", "Kiểm thử hồi quy công thức", "FAIL", "Không chạy được: thiếu bộ ca vàng")
        conflicts.append("FORMULA_REGRESSION:NOT_RUN")

    # 4. Độ phủ câu hỏi vàng của văn bản
    add(
        "TEST_QUERY_COVERAGE",
        "Câu hỏi vàng của văn bản",
        "PASS" if test_queries else "WARN",
        f"{len(test_queries)} câu hỏi đối soát" if test_queries else "Chưa khai báo câu hỏi vàng — chỉ kiểm tra được hồi quy công thức",
    )

    # 5. Trạng thái ban hành
    published = _published_policies.get(policy_id)
    if published is None:
        add("RELEASE_STATE", "Chưa có bản đang hiệu lực", "PASS", "Bản đầu tiên của văn bản")
    elif published.get("version") == version:
        add("RELEASE_STATE", "Chưa có bản đang hiệu lực", "FAIL", f"Phiên bản {version} đã ban hành trước đó")
        conflicts.append(f"RELEASE_STATE:{version}_ALREADY_PUBLISHED")
    else:
        add(
            "RELEASE_STATE",
            "Chưa có bản đang hiệu lực",
            "WARN",
            f"Sẽ thay thế bản {published.get('version')} đang hiệu lực (ban hành {published.get('published_at')})",
        )

    # 6. Đối chiếu với bản golden đang khoá — dấu hiệu văn bản mới lệch khỏi bộ ca vàng
    alignment = report.policy_alignment if report else "PINNED"
    add(
        "GOLDEN_ALIGNMENT",
        "Đối chiếu bản golden đang khoá",
        "PASS" if alignment == "MATCH" else "WARN",
        f"{policy_id} {version} so với {DEFAULT_POLICY_REF.policy_id} {DEFAULT_POLICY_REF.policy_version}"
        + ("" if alignment == "MATCH" else " — bộ ca vàng chưa được cập nhật theo văn bản mới"),
    )

    failures = [c for c in checks if c.status == "FAIL"]
    passed = not failures
    reg = {"passed": report.passed_cases if report else 0, "total": report.total_cases if report else 0}
    conflict_findings = [
        {
            "tier": 1,
            "status": "CONFLICT",
            "rule_codes": [policy_id],
            "message": next((c.detail for c in failures if c.code == f.split(":")[0]), ""),
            "source": None,
        }
        for f in conflicts
    ]

    return RuleTestResponse(
        policy_id=policy_id,
        passed=passed,
        checks_run=len(checks),
        closure_completeness=round((len(checks) - len(failures)) / len(checks), 4) if checks else 0.0,
        conflicts_detected=conflicts,
        recommendation="READY_TO_PUBLISH" if passed else "NEEDS_REVISION",
        checked_at=checked_at,
        checks=checks,
        conflict_findings=conflict_findings,
        regression=reg,
        can_publish=passed,
        benchmark_run_id=report.run_id if report else "",
        policy_alignment=alignment,
    )


@router.post("/rules/test", response_model=RuleTestResponse)
async def test_rules(request: RuleTestRequest) -> RuleTestResponse:
    """Pre-publish Regression & Conflict Testing Gate.

    Chạy 17 ca golden + kiểm tra trạng thái ban hành trước khi phát hành văn bản.
    """
    return _run_publish_gate(request.policy_id, request.version, request.test_queries)


@router.post("/publish", response_model=PublishPolicyResponse)
async def publish_policy(
    request: PublishPolicyRequest,
    principal: Principal = Depends(get_current_principal),
) -> PublishPolicyResponse:
    """Phát hành phiên bản chính sách mới (Atomic Policy Release).

    Trước khi ban hành, cổng kiểm thử được chạy lại trên engine thật. Bản phát hành
    luôn mang theo **bằng chứng chất lượng** (`benchmark`) để khu vực đo lường
    (/admin/benchmark) truy vết được văn bản nào đã được duyệt với kết quả ra sao.
    """
    if not principal.has_role("ADMIN", "POLICY_ADMIN"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Chỉ Quản trị viên hệ thống hoặc Quản trị chính sách được ban hành văn bản.",
        )

    gate = _run_publish_gate(request.policy_id, request.version, [])
    if request.enforce_test_gate and not gate.can_publish:
        raise HTTPException(
            status_code=422,
            detail={
                "code": "POLICY_TEST_GATE_FAILED",
                "message": "Văn bản chưa vượt qua cổng kiểm thử trước ban hành.",
                "conflicts": gate.conflicts_detected,
                "checks": [c.model_dump() for c in gate.checks if c.status == "FAIL"],
            },
        )

    now_iso = datetime.now(UTC).isoformat()
    raw_payload = f"{request.policy_id}:{request.version}:{now_iso}"
    snapshot_hash = f"sha256:{hashlib.sha256(raw_payload.encode('utf-8')).hexdigest()}"

    _published_policies[request.policy_id] = {
        "version": request.version,
        "status": "APPROVED_FOR_USE",
        "snapshot_hash": snapshot_hash,
        "published_by": request.published_by,
        "published_at": now_iso,
        "benchmark_run_id": gate.benchmark_run_id,
        "regression": gate.regression,
        "policy_alignment": gate.policy_alignment,
    }

    return PublishPolicyResponse(
        policy_id=request.policy_id,
        version=request.version,
        status="APPROVED_FOR_USE",
        snapshot_hash=snapshot_hash,
        published_at=now_iso,
        benchmark=PolicyBenchmarkEvidence(
            benchmark_run_id=gate.benchmark_run_id,
            total_cases=gate.regression.get("total", 0),
            passed_cases=gate.regression.get("passed", 0),
            accuracy_rate=round(gate.regression.get("passed", 0) / gate.regression["total"] * 100.0, 2) if gate.regression.get("total") else 0.0,
            golden_policy_ref=f"{DEFAULT_POLICY_REF.policy_id} {DEFAULT_POLICY_REF.policy_version}",
            policy_alignment=gate.policy_alignment,
            approved_at=now_iso,
        ),
    )
