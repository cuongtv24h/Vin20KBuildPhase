"""Hash chain bất biến per-quote (Spike 4: Anti-Cyclic + Genesis verify).

Mỗi sự kiện audit: event_hash = SHA256(prev_hash || canonical(event)),
append-only — không update/xóa. Là xương sống đối soát khiếu nại pháp lý.
"""


class AuditTrailService:
    """Ghi sự kiện vào chuỗi băm liên tục của một quote."""

    async def append_event(self, quote_id: str, event: dict) -> dict:
        """Nối event vào chuỗi: tính `event_hash` từ `prev_hash` hiện tại."""
        raise NotImplementedError("C-07: append audit event")
