"""Parser tọa độ nguồn (document_id, page, section, quote) của chunk."""

COORDINATE_FIELDS = ("document_id", "document_hash", "page", "section", "quote")


def parse_chunk_coordinates(chunk_metadata: dict) -> dict:
    """Chuẩn hóa tọa độ nguồn từ metadata chunk — fail nhanh nếu thiếu trường."""
    raise NotImplementedError("C-04: coordinate parser")
