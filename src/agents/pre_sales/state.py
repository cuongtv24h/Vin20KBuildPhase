"""State schema của Pre-Sales Advisory StateGraph (C-09)."""

from __future__ import annotations

from typing import Any, TypedDict

from src.contracts.enums import PreSalesSessionStatus


class PreSalesSessionState(TypedDict, total=False):
    """State đọc/ghi bởi các node của phiên pre-sales."""

    session_id: str
    status: PreSalesSessionStatus
    transcript: list[dict[str, Any]]  # lượt chat khách ↔ agent
    extracted_constraints: dict[str, Any]  # F2 — ràng buộc tài chính chuẩn hóa
    confirmed_constraints: dict[str, Any]  # sau khi khách xác nhận
    reference_plan: dict[str, Any]  # F3/F5 — phương án tham khảo (watermark)
    dossier_id: str | None  # F6/F7 — sau consent-and-handoff
    expires_at: str  # TTL phiên (Spike 5)
    error: str | None
    metadata: dict[str, Any]
