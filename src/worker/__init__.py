"""
Background workers package (Phase 2 & Phase 4).
Owner: TechLead (cuongtv_02560)
"""

from src.worker.tasks import generate_official_quote_pdf, process_outbox_batch
from src.worker.watermark_pdf import WATERMARK_TEXT, generate_reference_pdf

__all__ = [
    "WATERMARK_TEXT",
    "generate_official_quote_pdf",
    "generate_reference_pdf",
    "process_outbox_batch",
]
