"""SSE stream cho tiến trình Official Quote — TD-4.4 endpoint 3 (C-01 + Dev 3)."""

from fastapi import APIRouter, HTTPException, status

router = APIRouter(tags=["quote-events"])

_NOT_IMPLEMENTED = "Chưa implement — SSE engine + monotonic Last-Event-ID (TD-4.4)"


@router.get("/quotes/{quote_id}/events")
async def stream_quote_events(quote_id: str) -> dict:
    """Streaming tiến trình suy luận agent; reconnect qua Last-Event-ID."""
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail=_NOT_IMPLEMENTED)
