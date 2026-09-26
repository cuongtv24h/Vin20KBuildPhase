"""Vòng đời Lead Dossier: NEW → ASSIGNED → ... → CONVERTED_TO_QUOTE.

Nguồn: TD-4.4 (leads endpoints), TD-4.5 (Sales Handover Dossier), enum
`LeadDossierStatus`. Kèm SLA countdown và 1-click convert-to-quote.
"""


class DossierService:
    """Quản lý hồ sơ lead bàn giao từ phiên pre-sales."""

    async def create_from_session(self, session_id: str, consent: dict) -> dict:
        """F6/F7 — tạo dossier từ phiên pre-sales sau khi khách đồng ý."""
        raise NotImplementedError("C-10: create dossier")

    async def assign(self, dossier_id: str, sales_id: str) -> dict:
        raise NotImplementedError("C-10: assign dossier")

    async def convert_to_quote(self, dossier_id: str, idempotency_key: str) -> dict:
        """1-click chuyển dossier thành báo giá chính thức (POST /quotes flow)."""
        raise NotImplementedError("C-10: convert to quote")
