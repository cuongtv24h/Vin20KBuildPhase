"""Compliance endpoints — C-11 / F8 (TD-4.4 endpoint 7/8)."""

from fastapi import APIRouter, HTTPException, status

router = APIRouter(tags=["compliance"])

_NOT_IMPLEMENTED = "Chưa implement — dựng theo TD-4.4 khi C-11 sẵn sàng"


@router.post("/compliance/check-message")
async def check_message() -> dict:
    """Endpoint 7 — F8 Message Verification Gate (ON_PREVIEW/ON_COPY, live feedback)."""
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail=_NOT_IMPLEMENTED)


@router.post("/messages/send")
async def send_message() -> dict:
    """Endpoint 8 — Cổng phát hành DUY NHẤT, bắt buộc gate ON_FINAL_SEND."""
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail=_NOT_IMPLEMENTED)
