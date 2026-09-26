"""Official Quote endpoints — C-01/C-05 (TD-4.4 §Quotes).

Commands ghi đều bắt buộc Idempotency-Key; version báo giá là BẤT BIẾN —
recalculate tạo version mới, version cũ SUPERSEDED (append-only).
"""

from fastapi import APIRouter, Depends, HTTPException, status

from src.api.deps import get_idempotency_key

router = APIRouter(tags=["quotes"])

_NOT_IMPLEMENTED = "Chưa implement — dựng theo TD-4.4 khi C-01 sẵn sàng"


@router.post("/quotes", status_code=status.HTTP_202_ACCEPTED)
async def create_quote(idempotency_key: str = Depends(get_idempotency_key)) -> dict:
    """Endpoint 1 — POST /quotes: async ingress, commit nguyên tử DRAFT/ANALYZING."""
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail=_NOT_IMPLEMENTED)


@router.post("/quotes/{quote_id}/versions/{version}/recalculate")
async def recalculate_quote(quote_id: str, version: int) -> dict:
    """Endpoint 2 — recalculate: version cũ SUPERSEDED, tạo version + 1."""
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail=_NOT_IMPLEMENTED)


@router.post("/quotes/{quote_id}/versions/{version}/approve")
async def approve_quote(quote_id: str, version: int) -> dict:
    """Endpoint 4 — approve: HITL + re-auth + KMS Ed25519 attestation (C-05)."""
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail=_NOT_IMPLEMENTED)


@router.post("/quotes/{quote_id}/versions/{version}/reject")
async def reject_quote(quote_id: str, version: int) -> dict:
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail=_NOT_IMPLEMENTED)


@router.post("/quotes/{quote_id}/versions/{version}/request-revision")
async def request_revision(quote_id: str, version: int) -> dict:
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail=_NOT_IMPLEMENTED)


@router.post("/quotes/{quote_id}/versions/{version}/exception")
async def create_exception(quote_id: str, version: int) -> dict:
    """Tiếp nhận chứng từ ủy quyền TGĐ → N-18 exception version."""
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail=_NOT_IMPLEMENTED)


@router.post("/quotes/{quote_id}/versions/{version}/pdf/retry")
async def retry_pdf(quote_id: str, version: int) -> dict:
    """Retry sinh PDF qua Transactional Outbox (PdfStatus RETRYING)."""
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail=_NOT_IMPLEMENTED)


@router.get("/quotes/{quote_id}")
async def get_quote(quote_id: str) -> dict:
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail=_NOT_IMPLEMENTED)


@router.get("/quotes/{quote_id}/versions/{version}")
async def get_quote_version(quote_id: str, version: int) -> dict:
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail=_NOT_IMPLEMENTED)


@router.get("/quotes/{quote_id}/versions/{version}/evidence")
async def get_quote_evidence(quote_id: str, version: int) -> dict:
    """Claims + tọa độ nguồn (F4 — evidence traceability)."""
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail=_NOT_IMPLEMENTED)


@router.get("/quotes/{quote_id}/versions/{version}/audit")
async def get_quote_audit(quote_id: str, version: int) -> dict:
    """Hash chain audit events (C-07)."""
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail=_NOT_IMPLEMENTED)


@router.get("/quotes/{quote_id}/versions/{version}/pdf")
async def get_quote_pdf(quote_id: str, version: int) -> dict:
    """PDF báo giá có mã QR kiểm thực độc lập."""
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail=_NOT_IMPLEMENTED)
