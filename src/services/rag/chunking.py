"""Chunking văn bản chính sách giữ nguyên tọa độ (section/bảng/dòng)."""


def chunk_policy_document(document_text: str, document_id: str) -> list[dict]:
    """Tách chunk kèm metadata tọa độ để F4 anchor về đúng câu.

    TODO(Dev 1): chunk theo heading + bảng Markdown, mỗi chunk gắn hash nguồn.
    """
    raise NotImplementedError("C-03: chunking")
