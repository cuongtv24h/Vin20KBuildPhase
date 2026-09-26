"""Evaluation & công khai khóa — benchmark-runs + JWKS (TD-4.4)."""

from fastapi import APIRouter, HTTPException, status

router = APIRouter(tags=["evaluation"])

_NOT_IMPLEMENTED = "Chưa implement — dựng theo TD-4.4"


@router.post("/evaluation/benchmark-runs")
async def start_benchmark_run() -> dict:
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail=_NOT_IMPLEMENTED)


@router.get("/evaluation/benchmark-runs/{run_id}")
async def get_benchmark_run(run_id: str) -> dict:
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail=_NOT_IMPLEMENTED)


@router.get("/.well-known/jwks.json")
async def get_jwks() -> dict:
    """Public Ed25519 keys phục vụ khách hàng đối soát chữ ký báo giá."""
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail=_NOT_IMPLEMENTED)
