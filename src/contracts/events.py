"""
Server-Sent Events (SSE) contracts and event envelopes.
"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class SseEventEnvelope(BaseModel):
    """
    Gói tin sự kiện SSE truyền thời gian thực về Frontend:
    - Sequence tăng đơn điệu
    - Hỗ trợ replay sự kiện qua Last-Event-ID
    """
    event_id: str = Field(..., description="Mã sự kiện duy nhất (vd: SES-001:v1:000004)")
    event_seq: int = Field(..., ge=1, description="Số thứ tự sự kiện tăng đơn điệu")
    event_type: str = Field(..., description="Loại sự kiện nghiệp vụ")
    session_id: str | None = None
    quote_id: str | None = None
    quote_version: int | None = None
    schema_version: str = Field(default="sse-event.v1")
    correlation_id: str = Field(default="trace-unknown")
    occurred_at: datetime = Field(default_factory=datetime.utcnow)
    payload: dict[str, Any] = Field(default_factory=dict)
