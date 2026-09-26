"""Lead Dossier endpoints — C-10 (TD-4.4)."""

from fastapi import APIRouter, HTTPException, status

router = APIRouter(tags=["leads"])

_NOT_IMPLEMENTED = "Chưa implement — dựng theo TD-4.4 khi C-10 sẵn sàng"


@router.get("/leads/dossiers")
async def list_dossiers() -> dict:
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail=_NOT_IMPLEMENTED)


@router.post("/leads/dossiers/{dossier_id}/convert-to-quote")
async def convert_to_quote(dossier_id: str) -> dict:
    """1-click chuyển dossier → báo giá chính thức (đi qua POST /quotes flow)."""
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail=_NOT_IMPLEMENTED)
