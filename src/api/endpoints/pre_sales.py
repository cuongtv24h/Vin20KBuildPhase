"""Pre-Sales session endpoints — C-09 (TD-4.4, các endpoint 5/6 nhóm Pre-Sales)."""

from fastapi import APIRouter, HTTPException, status

router = APIRouter(tags=["pre-sales"])

_NOT_IMPLEMENTED = "Chưa implement — dựng theo TD-4.4 khi C-09 sẵn sàng"


@router.post("/pre-sales/sessions", status_code=status.HTTP_201_CREATED)
async def create_session() -> dict:
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail=_NOT_IMPLEMENTED)


@router.post("/pre-sales/sessions/{session_id}/messages")
async def post_message(session_id: str) -> dict:
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail=_NOT_IMPLEMENTED)


@router.get("/pre-sales/sessions/{session_id}/stream")
async def stream_session(session_id: str) -> dict:
    """SSE Pre-Sales Dialogue (tiến trình agent thời gian thực)."""
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail=_NOT_IMPLEMENTED)


@router.post("/pre-sales/sessions/{session_id}/confirm-constraints")
async def confirm_constraints(session_id: str) -> dict:
    """Khách xác nhận ràng buộc tài chính F2 trước khi tính phương án."""
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail=_NOT_IMPLEMENTED)


@router.get("/pre-sales/sessions/{session_id}/reference-plan.pdf")
async def get_reference_plan_pdf(session_id: str) -> dict:
    """Endpoint 6 — PDF tham khảo on-demand, bắt buộc watermark NOT AN OFFICIAL QUOTE."""
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail=_NOT_IMPLEMENTED)


@router.post("/pre-sales/sessions/{session_id}/consent-and-handoff")
async def consent_and_handoff(session_id: str) -> dict:
    """Endpoint 5 — F6/F7: đồng ý → tạo Lead Dossier (C-10)."""
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail=_NOT_IMPLEMENTED)
