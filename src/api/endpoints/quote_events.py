"""
Server-Sent Events (SSE) Streaming Endpoint for Live Quote Updates and Event Replay (Async).
Owner: TechLead (cuongtv_02560)
"""

from __future__ import annotations

import json
from collections.abc import AsyncGenerator
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import Principal, get_current_principal
from src.contracts.errors import ErrorCode
from src.db.repositories.audit import AuditRepository
from src.db.repositories.quotes import QuoteRepository
from src.db.session import get_db_session

router = APIRouter(prefix="/api/v1/quotes", tags=["quote-events"])


@router.get("/{quote_id}/events")
async def stream_quote_events(
    quote_id: str,
    request: Request,
    last_event_id: str | None = Header(None, alias="Last-Event-ID"),
    db: AsyncSession = Depends(get_db_session),
    principal: Principal = Depends(get_current_principal),
) -> StreamingResponse:
    """
    SSE Streaming Endpoint (C-01 / Phase 4):
    Streams quote audit events and workflow state changes in real-time.
    Supports event replay via Last-Event-ID header.
    """
    quote = await QuoteRepository.get_by_id(db, quote_id, principal.tenant_id)
    if not quote:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": ErrorCode.NOT_FOUND.value, "message": f"Quote {quote_id} not found."},
        )

    # Fetch existing audit events for initial replay
    audit_events = await AuditRepository.get_events_by_quote_id(db, quote_id)

    async def event_generator() -> AsyncGenerator[str, None]:
        # Step 1: Replay past events if any
        replaying = True if last_event_id is None else False
        for e in audit_events:
            if not replaying:
                if str(e.event_id) == last_event_id or str(e.event_seq) == last_event_id:
                    replaying = True
                continue

            event_data = {
                "quote_id": quote_id,
                "event_id": e.event_id,
                "event_seq": e.event_seq,
                "event_type": e.event_type,
                "actor_id": e.actor_id,
                "event_hash": e.event_hash,
                "occurred_at": e.occurred_at.isoformat() if e.occurred_at else None,
                "payload": e.payload_json,
            }
            yield f"id: {e.event_id}\nevent: {e.event_type}\ndata: {json.dumps(event_data)}\n\n"

        # Step 2: Yield current status beacon
        status_event = {
            "quote_id": quote.quote_id,
            "quote_version": quote.quote_version,
            "status": quote.status,
            "approval_status": quote.approval_status,
            "pdf_status": quote.pdf_status,
            "timestamp": datetime.now(UTC).isoformat(),
        }
        yield f"id: beacon-{quote.quote_version}\nevent: QUOTE_STATUS_BEACON\ndata: {json.dumps(status_event)}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
