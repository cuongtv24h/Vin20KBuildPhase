"""Tasks bất đồng bộ của worker (Outbox → side effects)."""

PDF_GENERATION_TASK = "generate_quote_pdf"
SSE_DISPATCH_TASK = "dispatch_sse_events"


async def generate_quote_pdf(quote_id: str, version: int) -> dict:
    """Render PDF báo giá (QR kiểm thực) — chỉ khi version APPROVED."""
    raise NotImplementedError("Worker: PDF generation")


async def dispatch_sse_events() -> None:
    """Poll outbox → phát SSE event monotonic tới các stream đang mở."""
    raise NotImplementedError("Worker: SSE dispatch")
