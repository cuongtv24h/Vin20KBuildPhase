"""Repository cho quotes / quote_versions / snapshots."""


class QuoteRepository:
    """CRUD + phiên bản hóa quote; append-only cho version (không UPDATE nội dung)."""

    async def create_with_outbox(self, payload: dict, idempotency_key: str) -> dict:
        """Insert Quote + Idempotency Record + Outbox Job trong 1 transaction."""
        raise NotImplementedError("Repo: create_with_outbox")

    async def supersede_version(self, quote_id: str, version: int) -> None:
        raise NotImplementedError("Repo: supersede_version")
