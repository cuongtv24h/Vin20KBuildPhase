"""Trình kiểm chứng chuỗi audit (genesis → head, phát hiện vòng/ghép giả)."""


class AuditVerifier:
    """Verify toàn vẹn chuỗi: genesis đúng, không anti-cyclic, hash khớp."""

    def verify_chain(self, quote_id: str, events: list[dict]) -> dict:
        """Trả về {valid, broken_at_event_id, reason} — phục vụ QR đối soát."""
        raise NotImplementedError("C-07: chain verification")
