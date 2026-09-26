"""Policy lifecycle endpoints — C-03 / F9 (TD-4.4)."""

from fastapi import APIRouter, HTTPException, status

router = APIRouter(tags=["policies"])

_NOT_IMPLEMENTED = "Chưa implement — dựng theo TD-4.4 khi C-03 sẵn sàng"


@router.post("/policies/{policy_id}/extract-rules")
async def extract_rules(policy_id: str) -> dict:
    """F9 — trích StructuredRule từ văn bản chính sách."""
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail=_NOT_IMPLEMENTED)


@router.post("/policies/{policy_id}/rules/test")
async def test_rules(policy_id: str) -> dict:
    """Pre-Publish Regression Test Gate — fail thì cấm publish."""
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail=_NOT_IMPLEMENTED)


@router.post("/policies/{policy_id}/publish")
async def publish_policy(policy_id: str) -> dict:
    """Endpoint 9 — Atomic Activation với Non-destructive Rollback."""
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail=_NOT_IMPLEMENTED)
