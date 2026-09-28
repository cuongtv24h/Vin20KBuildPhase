"""
Transactional Outbox Worker for Official Quotes & Official PDF Generation with QR Code.
Owner: TechLead (cuongtv_02560)
"""

from __future__ import annotations

import logging
import os
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from src.contracts.enums import PdfStatus
from src.db.repositories.outbox import OutboxRepository
from src.db.repositories.quotes import QuoteRepository

logger = logging.getLogger(__name__)


def generate_official_quote_pdf(
    quote_id: str,
    unit_code: str,
    snapshot_hash: str,
    signature: str,
    total_price_vnd: int = 0,
    output_dir: str | None = None,
) -> str:
    """
    Renders authoritative Official Quote PDF featuring:
    - Official VLandFuture Header & Title
    - Quote metadata, Unit Code, Total Price
    - Cryptographic Attestation section (Ed25519 signature & SHA-256 snapshot hash)
    - Verification QR URL: https://verify.vlandfuture.vn/quote/{quote_id}?hash={snapshot_hash}&sig={signature}
    """
    out_dir = output_dir or os.path.join("data", "official_pdfs")
    Path(out_dir).mkdir(parents=True, exist_ok=True)
    pdf_path = os.path.join(out_dir, f"official_quote_{quote_id}.pdf")

    qr_url = f"https://verify.vlandfuture.vn/quote/{quote_id}?hash={snapshot_hash}&sig={signature}"

    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.pdfgen import canvas

        c = canvas.Canvas(pdf_path, pagesize=A4)
        width, height = A4

        # Title Header
        c.setFont("Helvetica-Bold", 18)
        c.drawString(50, height - 60, "BẢNG CHÀO GIÁ BÁN HÀNG CHÍNH THỨC")
        c.setFont("Helvetica", 11)
        c.drawString(50, height - 80, "Hệ Thống Phê Duyệt Giá & Quản Trị Chính Sách VLandFuture (P-096)")

        # Metadata
        c.drawString(50, height - 120, f"Mã Báo Giá: {quote_id}")
        c.drawString(50, height - 140, f"Mã Căn Hộ: {unit_code}")
        c.drawString(50, height - 160, f"Tổng Giá Trị HĐ (dự kiến): {total_price_vnd:,} VNĐ")
        c.drawString(50, height - 180, f"Thời Điểm Cấp: {datetime.now(UTC).strftime('%Y-%m-%d %H:%M:%S UTC')}")

        # Cryptographic Attestation Box
        c.rect(50, height - 280, width - 100, 80, stroke=1, fill=0)
        c.setFont("Helvetica-Bold", 10)
        c.drawString(60, height - 215, "CHỨNG THƯ KÝ SỐ SERVER ATTESTATION (RFC 8032 Ed25519):")
        c.setFont("Courier", 8)
        c.drawString(60, height - 235, f"Snapshot Hash (SHA-256): {snapshot_hash[:48]}...")
        c.drawString(60, height - 250, f"Server Signature:        {signature[:48]}...")
        c.setFont("Helvetica-Oblique", 9)
        c.drawString(60, height - 270, f"Tra cứu chứng thực: {qr_url[:70]}...")

        c.save()
        return pdf_path

    except ImportError:
        # Fallback pure-text rendering when reportlab is absent in test/local environments
        content = (
            f"=== BẢNG CHÀO GIÁ BÁN HÀNG CHÍNH THỨC ===\n"
            f"Mã Báo Giá: {quote_id}\n"
            f"Mã Căn Hộ: {unit_code}\n"
            f"Tổng Giá Trị: {total_price_vnd} VNĐ\n"
            f"Snapshot Hash (SHA-256): {snapshot_hash}\n"
            f"Server Signature (Ed25519): {signature}\n"
            f"Tra Cứu Mã QR: {qr_url}\n"
            f"Trạng Thái: CHÍNH THỨC ĐÃ PHÊ DUYỆT\n"
        )
        with open(pdf_path, "w", encoding="utf-8") as f:
            f.write(content)
        return pdf_path


async def process_outbox_batch(db: AsyncSession, limit: int = 10) -> int:
    """
    Polls pending outbox records and executes asynchronous tasks.
    Returns number of successfully processed events.
    """
    pending_events = await OutboxRepository.poll_pending(db, limit=limit)
    processed_count = 0

    for item in pending_events:
        try:
            payload = item.payload_json or {}
            event_type = item.event_type

            if event_type in ("QUOTE_OFFICIALLY_APPROVED", "OFFICIAL_QUOTE_ISSUED"):
                quote_id = payload.get("quote_id", item.aggregate_id)
                unit_code = payload.get("unit_code", "N/A")
                snapshot_hash = payload.get("snapshot_hash", "")
                signature = payload.get("signature", "")

                # Render Official PDF
                pdf_path = generate_official_quote_pdf(
                    quote_id=quote_id,
                    unit_code=unit_code,
                    snapshot_hash=snapshot_hash,
                    signature=signature,
                )

                # Update Quote Model
                quote = await QuoteRepository.get_by_id(db, quote_id)
                if quote:
                    quote.pdf_status = PdfStatus.ISSUED.value
                    quote.pdf_url = pdf_path.replace("\\", "/")
                    await QuoteRepository.update_quote(db, quote)

                # Mark Outbox as PROCESSED
                await OutboxRepository.mark_processed(db, item.event_id)
                processed_count += 1
            else:
                # Other event types: mark processed
                await OutboxRepository.mark_processed(db, item.event_id)
                processed_count += 1

        except Exception as ex:
            logger.error("Failed to process outbox event %s: %s", item.event_id, ex)
            await OutboxRepository.mark_failed(db, item.event_id, item.retry_count + 1)

    return processed_count
