"""F9 — Structured Rule Extraction & Pre-Publish Test Gate (C-03)."""


class RuleExtractionService:
    """Trích quy tắc có cấu trúc từ văn bản chính sách trước khi publish."""

    async def extract_structured_rules(self, document_id: str) -> list[dict]:
        """LLM trích `StructuredRule` (điều kiện / loại trừ / mức ưu đãi)."""
        raise NotImplementedError("F9: extract rules")

    async def run_pre_publish_tests(self, document_id: str) -> dict:
        """Regression test: quy tắc mới phải tái tạo đúng kết quả golden fixtures."""
        raise NotImplementedError("F9: pre-publish test gate")
