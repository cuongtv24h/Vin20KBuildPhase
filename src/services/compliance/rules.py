"""Quy chuẩn phát ngôn — nguồn: `mydoc/dataset/policies_md/POL-08`."""

# TODO(Dev 1): nạp danh mục cấm/từ khóa bắt buộc mỏ neo từ POL-08 khi implement.
FORBIDDEN_CLAIM_PATTERNS: tuple[str, ...] = ()


def check_forbidden_phrases(message_text: str) -> list[str]:
    """Trả về các cụm vi phạm phát ngôn tìm thấy trong tin nhắn."""
    raise NotImplementedError("C-11: forbidden phrase check")
