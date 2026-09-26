"""Repository cho transactional_outbox — nguồn sự kiện cho worker."""


class OutboxRepository:
    """Insert event trong cùng transaction nghiệp vụ; worker poll phát SSE/PDF."""

    async def enqueue(self, event_type: str, payload: dict) -> dict:
        raise NotImplementedError("Repo: outbox enqueue")

    async def poll_pending(self, limit: int = 50) -> list[dict]:
        raise NotImplementedError("Repo: outbox poll")
