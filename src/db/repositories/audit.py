"""Repository append-only cho quote_audit_events (C-07)."""


class AuditRepository:
    """Chỉ INSERT — không UPDATE/DELETE (append-only enforcement)."""

    async def append(self, quote_id: str, event: dict, prev_hash: str, event_hash: str) -> dict:
        raise NotImplementedError("Repo: audit append")
