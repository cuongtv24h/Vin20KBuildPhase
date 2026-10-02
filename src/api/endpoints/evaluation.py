"""
Public Key Discovery, JWKS, and Independent Attestation Verification Endpoints (Spike 3 / Phase 4).
Owner: TechLead (cuongtv_02560)
"""

from __future__ import annotations

import base64
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from src.api.deps import Principal, get_current_principal
from src.services.approval import KMSServerSigner
from src.services.pricing.evaluation import (
    BenchmarkRunReport,
    run_benchmark_evaluation,
)

router = APIRouter(tags=["evaluation"])

# In-memory storage for benchmark runs history
_BENCHMARK_RUNS_CACHE: dict[str, BenchmarkRunReport] = {}


class VerifySignatureRequest(BaseModel):
    snapshot_hash: str
    signature_b64: str
    public_key_b64: str | None = None


class BenchmarkRunRequest(BaseModel):
    benchmark_suite: str = "golden_scenarios_17"
    case_ids: list[str] | None = None
    policy_id: str | None = None
    policy_version: str | None = None


@router.get("/.well-known/jwks.json")
async def get_jwks() -> dict[str, Any]:
    """
    Public JWKS Endpoint (RFC 8037):
    Publishes Ed25519 public keys for independent verification by third-party auditors.
    """
    signer = KMSServerSigner()
    raw_pub_bytes = signer.get_public_key_raw_bytes()
    x_b64url = base64.urlsafe_b64encode(raw_pub_bytes).decode("utf-8").rstrip("=")

    return {
        "keys": [
            {
                "kty": "OKP",
                "crv": "Ed25519",
                "kid": "vlandfuture-kms-root-2026",
                "use": "sig",
                "x": x_b64url,
            }
        ]
    }


@router.get("/api/v1/evaluation/public-key")
async def get_server_public_key() -> dict[str, Any]:
    """Returns the active server attestation Ed25519 public key in Base64."""
    signer = KMSServerSigner()
    return {
        "algorithm": "Ed25519",
        "format": "RFC 8032 / RFC 8037",
        "key_id": "vlandfuture-kms-root-2026",
        "public_key_b64": signer.get_public_key_base64(),
    }


@router.post("/api/v1/evaluation/verify")
async def verify_signature_endpoint(req: VerifySignatureRequest) -> dict[str, Any]:
    """
    Public verification tool: verifies an Ed25519 signature against a snapshot hash.
    """
    signer = KMSServerSigner()
    pub_bytes = (
        base64.b64decode(req.public_key_b64)
        if req.public_key_b64
        else signer.get_public_key_raw_bytes()
    )

    is_valid = KMSServerSigner.verify_signature(
        public_key_raw_bytes=pub_bytes,
        snapshot_hash=req.snapshot_hash,
        signature_base64=req.signature_b64,
    )

    return {
        "snapshot_hash": req.snapshot_hash,
        "is_valid": is_valid,
        "algorithm": "Ed25519",
    }


def _require_quality_roles(principal: Principal) -> None:
    """Kiểm thử công thức là nghiệp vụ quản trị: chỉ ADMIN và POLICY_ADMIN được chạy/xem."""
    if not principal.has_role("ADMIN", "POLICY_ADMIN"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Chỉ Quản trị viên hệ thống hoặc Quản trị chính sách được chạy kiểm thử công thức.",
        )


@router.post("/api/v1/evaluation/benchmark-runs", response_model=BenchmarkRunReport)
async def trigger_benchmark_run(
    req: BenchmarkRunRequest | None = None,
    principal: Principal = Depends(get_current_principal),
) -> BenchmarkRunReport:
    """
    Trigger automated execution of Golden Benchmark Test Suite (17 vectors FCS v2.6).
    Evaluates Zero-Delta AC-FIN-01, checks all financial invariants, and tracks P50/P95 latencies.
    """
    _require_quality_roles(principal)
    case_ids = req.case_ids if req else None
    report = run_benchmark_evaluation(
        case_ids=case_ids,
        policy_id=req.policy_id if req else None,
        policy_version=req.policy_version if req else None,
    )
    _BENCHMARK_RUNS_CACHE[report.run_id] = report
    return report


@router.get("/api/v1/evaluation/benchmark-runs/{run_id}", response_model=BenchmarkRunReport)
async def get_benchmark_run(
    run_id: str,
    principal: Principal = Depends(get_current_principal),
) -> BenchmarkRunReport:
    """Retrieve historical benchmark run results by run_id."""
    _require_quality_roles(principal)
    report = _BENCHMARK_RUNS_CACHE.get(run_id)
    if not report:
        raise HTTPException(
            status_code=404,
            detail=f"Benchmark run with id '{run_id}' not found.",
        )
    return report


@router.get("/api/v1/evaluation/benchmark-runs")
async def list_benchmark_runs(
    principal: Principal = Depends(get_current_principal),
) -> list[dict[str, Any]]:
    """List summary of all executed benchmark runs."""
    _require_quality_roles(principal)
    return [
        {
            "run_id": r.run_id,
            "benchmark_suite": r.benchmark_suite,
            "executed_at": r.executed_at,
            "total_cases": r.total_cases,
            "passed_cases": r.passed_cases,
            "accuracy_rate": r.accuracy_rate,
            "latency_p50_ms": r.latency_p50_ms,
            "latency_p95_ms": r.latency_p95_ms,
            "ac_fin_01_passed": r.ac_fin_01_passed,
            "policy_id": r.policy_id,
            "policy_version": r.policy_version,
            "policy_alignment": r.policy_alignment,
        }
        for r in _BENCHMARK_RUNS_CACHE.values()
    ]

