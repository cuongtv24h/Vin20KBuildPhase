"""Chuẩn hoá lệnh gạch chéo (slash command) cho Copilot.

Vì sao cần: Sale gõ nhanh `/chinh-sach`, `/baogia`… như phím tắt. Nếu chuỗi thô đó đi thẳng vào LLM
thì (a) model coi đó là nội dung câu hỏi và **nhắc lại lệnh trong câu trả lời**, (b) câu trả lời bị
lệch nghĩa so với ý định thật. Lớp này làm hai việc:

1. `normalize_user_message()` — dịch lệnh thành câu tiếng Việt tự nhiên trước khi đưa vào agent,
   đồng thời bóc mọi token `/abc` còn sót (gõ tay, dán vào, lịch sử cũ).
2. `strip_command_mentions()` — dọn lệnh gạch chéo nếu model vẫn nhắc trong câu trả lời
   (prompt đã dặn không nhắc, nhưng phải chặn ở output chứ không tin tưởng model).

Lưu ý an toàn: chỉ bóc token khớp **danh mục lệnh đã biết** và đứng tách khỏi từ khác
(`(?<![\\w])`), nên không bao giờ ăn nhầm chữ trong "Anh/chị" hay đường dẫn `/api/v1`.
"""

from __future__ import annotations

import re

#: Lệnh gạch chéo của workspace Sale → câu tiếng Việt tương ứng.
#: Giữ đúng danh mục ở `SalesWorkspacePage.SLASH_COMMANDS` (một nguồn sự thật cho cả hai phía).
SLASH_COMMAND_MAP: dict[str, str] = {
    "/tao-khach": "Tạo khách hàng mới",
    "/tim-khach": "Tìm khách hàng",
    "/khach-hang": "Xem danh sách hồ sơ khách hàng",
    "/baogia": "Xem pipeline báo giá",
    "/soan-tin": "Soạn tin nhắn gửi khách",
    "/chinh-sach": "Tra cứu chính sách đang hiệu lực",
    "/tinh-lai": "Lập báo giá mới theo chính sách đang hiệu lực",
    "/gio-hang": "Giỏ hàng còn căn nào?",
}

#: Ứng viên token lệnh: `/<chữ>` đứng đầu câu / sau khoảng trắng / sau dấu mở ngoặc,
#: và KHÔNG dính liền chữ phía trước (tránh "Anh/chị", "km/h") hay phía sau (tránh "/api/v1").
_SLASH_TOKEN_RE = re.compile(r"(?<![\w/])([(\[]?\s*)/([a-z][a-z0-9-]{0,30})(?![\w-])", re.IGNORECASE)
#: Câu chỉ dẫn cách dùng UI ("gõ /baogia", "dùng lệnh /tinh-lai") — prompt đã cấm, model vẫn lỡ →
#: bỏ cả câu thay vì để lại mệnh đề cụt.
_INSTRUCTION_RE = re.compile(
    r"(?<![\w/])(?:gõ|dùng|bấm|nhập|chọn|mở)\s*(?:lệnh\s*)?[([(]?\s*/[a-z][a-z0-9-]{0,30}",
    re.IGNORECASE,
)
def _lower_first(phrase: str) -> str:
    return phrase[:1].lower() + phrase[1:] if phrase else phrase


def normalize_user_message(text: str) -> str:
    """Dịch lệnh gạch chéo thành câu tự nhiên; bóc token `/abc` còn sót.

    Ví dụ:
        "/chinh-sach"              → "Tra cứu chính sách đang hiệu lực"
        "/tim-khach Nguyễn Văn An" → "Tìm khách hàng Nguyễn Văn An"
        "/baogia căn ZEN-A-1205"   → "Xem pipeline báo giá căn ZEN-A-1205"
        "/ch"                      → "ch" (lệnh trơ: bỏ dấu gạch, không gửi chuỗi thô cho LLM)
    """
    raw = (text or "").strip()
    if not raw:
        return ""

    def _replace(match: re.Match[str]) -> str:
        token = "/" + match.group(2).lower()
        phrase = SLASH_COMMAND_MAP.get(token)
        if phrase is None:
            # Lệnh lạ: chỉ bóc dấu gạch khi nó đứng đầu câu, còn giữa câu thì bỏ hẳn token.
            return match.group(0).lstrip()[1:] if match.group(0).strip().startswith("/") and match.start() == 0 else " "
        # Giữa câu thì hạ chữ đầu cho khỏi gãy văn phong.
        return _lower_first(phrase) if match.start() > 0 else phrase

    normalized = _SLASH_TOKEN_RE.sub(_replace, raw)
    if normalized.strip().startswith("/"):
        normalized = normalized.strip()[1:]
    normalized = re.sub(r"\s{2,}", " ", normalized).strip(" ,;:-")
    return normalized or raw.lstrip("/").strip()


#: Token lệnh đứng lẻ trong câu (đã biết trong danh mục) — bóc tại chỗ.
_INLINE_CMD_RE = re.compile(r"(?<![\w/])[([(]?\s*/([a-z][a-z0-9-]{0,30})(?![-\w])\s*[)\]]?", re.IGNORECASE)
#: Tách câu để xử lý theo từng câu (giữ dấu câu của câu gốc).
_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?;])\s+|\n+")


def _clean_sentence(sentence: str) -> str:
    """Bóc token lệnh trong một câu, dọn ngoặc/khoảng trắng còn sót."""

    def _replace(match: re.Match[str]) -> str:
        return " " if ("/" + match.group(1).lower()) in SLASH_COMMAND_MAP else match.group(0)

    cleaned = _INLINE_CMD_RE.sub(_replace, sentence)
    cleaned = re.sub(r"\(\s*\)", "", cleaned)
    cleaned = re.sub(r"[([(]\s*[)\]]", "", cleaned)
    # Ngoặc mở cụt ở cuối câu sau khi bóc lệnh: "… 8% (xem thêm." → "… 8%."
    cleaned = re.sub(r"\s*[([(]\s*(?:xem thêm|tham khảo|chi tiết|ví dụ)?\s*[.,;:!?]?\s*$", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s{2,}", " ", cleaned)
    cleaned = re.sub(r"\s+([,.;:!?])", r"\1", cleaned)
    return cleaned.strip(" ,;:-")


def strip_command_mentions(text: str) -> str:
    """Bỏ nhắc nhở về lệnh gạch chéo trong câu trả lời, giữ câu văn liền mạch.

    - Câu chỉ dẫn UI ("Anh/chị gõ /chinh-sach để tra cứu") → bỏ cả câu.
    - Câu nghiệp vụ có nhắc lệnh lẫn trong ngoặc → chỉ bóc token, giữ nội dung.
    - An toàn với "Anh/chị", "km/h", "/api/v1" (chỉ bóc token có trong danh mục).
    """
    if not text or "/" not in text:
        return text

    kept: list[str] = []
    for sentence in _SENTENCE_SPLIT_RE.split(text):
        raw_sentence = sentence.strip()
        if not raw_sentence:
            continue
        if _INSTRUCTION_RE.search(raw_sentence):
            continue  # câu chỉ để dạy bấm lệnh — không phải nội dung trả lời
        cleaned = _clean_sentence(raw_sentence)
        # Câu bị bóc lệnh mà teo lại thành mảnh vô nghĩa ("Xem.") → bỏ luôn.
        if cleaned and (cleaned == raw_sentence or len(cleaned.split()) >= 3):
            kept.append(cleaned)

    cleaned_text = " ".join(kept).strip()
    cleaned_text = re.sub(r"\s{2,}", " ", cleaned_text)
    if cleaned_text and not cleaned_text.endswith((".", "!", "?", "_", ")", "”")):
        cleaned_text += "."
    return cleaned_text


def sanitize_history(history: list[dict[str, str]] | None) -> list[dict[str, str]]:
    """Chuẩn hoá lịch sử hội thoại gửi kèm (lượt cũ có thể còn lệnh thô)."""
    out: list[dict[str, str]] = []
    for item in history or []:
        content = str(item.get("content", "") or "")
        if not content.strip():
            continue
        out.append({**item, "content": normalize_user_message(content)})
    return out
