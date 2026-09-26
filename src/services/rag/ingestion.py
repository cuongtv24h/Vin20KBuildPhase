"""C-03 — Policy Registry & Ingestion Pipeline.

Pipeline nạp văn bản chính sách (nguồn mẫu: `mydoc/dataset/policies_md/POL-*.md`
và `showcase_documents/`) vào Supabase + pgvector:
    parse → chunk → embed (1536 dims) → upsert + versioning hiệu lực
    → (F9) extract-rules → pre-publish test gate → publish
"""


class PolicyIngestionPipeline:
    """Điều phối nạp chính sách mới (kèm phát hiện xung đột thời gian)."""

    async def ingest_document(self, document_path: str, effective_from: str, effective_to: str) -> dict:
        raise NotImplementedError("C-03: ingest pipeline")
