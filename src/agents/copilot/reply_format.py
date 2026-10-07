"""Chuẩn hoá câu trả lời ở lớp **tất định** — bảng không dính câu văn, không lộ tên nội bộ.

Hai lỗi thực tế người dùng gặp (đợt 15, bổ sung P1.5b + P2.5):

1. **LLM viết bảng dính vào câu văn.** Ví dụ: `... hiện có **3 căn** đáp ứng. | Mã căn | Phòng ngủ |
   ... |` — cả bảng nằm trên **một dòng**. Hệ quả: bộ hiển thị markdown không nhận ra bảng (nó nhận
   theo *dòng* bắt đầu bằng `|`), nên Sale nhìn thấy một cục chữ có gạch dọc, không có cột, không
   xuống hàng. Không thể sửa bằng prompt cho chắc — phải **tách bằng máy**.
2. **Tên nội bộ lọt vào văn bản gửi khách.** Ví dụ: `(gia_toi_da_vnd = 0, tức không giới hạn trần…)`.
   Tên tham số/tool là chuyện kỹ thuật; Sale không được thấy, và khách thì tuyệt đối không.

Cách làm — cùng triết lý với `anchors.py` (P2.3): LLM chỉ lo **nội dung**, còn **hình thức** và
**thứ không được xuất hiện** là việc của lớp tất định chạy sau khi model viết xong:

- `normalize_markdown()`: tách bảng dính bằng cách dò hàng phân cách `|---|---|` để biết số cột rồi
  cắt dòng theo đúng số cột; ép dòng trống trước/sau bảng và danh sách; đổi emoji mũi tên (➡️) thành
  gạch đầu dòng; bỏ đậm rác trong ô bảng và đậm mở nửa câu. Hàm **idempotent** — chạy hai lần cho
  cùng kết quả, nên có thể áp lại cho dữ liệu cũ.
- `strip_internal_names()`: bỏ ngoặc chỉ chứa tham số nội bộ, bỏ `ten_tham_so = giá_trị`, đổi tên
  tool thành cách nói nghiệp vụ (`tinh_phuong_an_thanh_toan` → "phương án thanh toán chi tiết"),
  và dọn mọi `snake_case` còn sót.
- `structure_sections()` (đợt 20): câu trả lời nhiều ý mà model viết liền một khối (kiểu "… em đã tính
  3 phương án. **PA-CHUDONG:** … **PA-NHANH:** … **Khuyến nghị:** …") được tách thành **mục in đậm +
  mỗi ý một dòng**, để Sale bấm "Copy cho khách" là gửi được ngay. Chỉ chạy khi văn bản **thật sự** có
  nhãn mục; đoạn văn bình thường giữ nguyên (không tự biến mọi câu thành gạch đầu dòng).

Vì sao không chỉ sửa prompt: prompt chỉ *giảm* xác suất, còn dữ liệu cũ đã lưu vẫn hỏng. Lớp này bảo
đảm mọi câu trả lời (kể cả của model yếu) đều ra hình thức đọc được.
"""

from __future__ import annotations

import re

# ─── 1. Bảng markdown viết dính ────────────────────────────────────────────────────

#: Một ô của hàng phân cách: `---`, `:---`, `---:`, `:---:` (từ 2 gạch).
_DIVIDER_CELL = r":?-{2,}:?"

#: Hàng phân cách bảng: `|---|---|`, `| --- | --- |`, `---|---`.
_DIVIDER_RE = re.compile(rf"\|?\s*{_DIVIDER_CELL}\s*(?:\|\s*{_DIVIDER_CELL}\s*)+\|?")

#: Dòng chỉ có hàng phân cách (không lẫn chữ) — dùng để dò bảng khi tiêu đề nằm dòng trên.
_DIVIDER_ONLY_RE = re.compile(rf"^\|?\s*{_DIVIDER_CELL}\s*(?:\|\s*{_DIVIDER_CELL}\s*)*\|?$")

#: Dòng bảng hoàn chỉnh: bắt đầu và kết thúc bằng `|`.
_TABLE_LINE_RE = re.compile(r"^\|.*\|$")

#: Mũi tên ở đầu dòng → gạch đầu dòng; mũi tên giữa dòng → gạch ngang dài.
_LEAD_ARROW_RE = re.compile(r"^[ \t]*(?:➡️|➡|⇒|→|»)\s*")
_INLINE_ARROW_RE = re.compile(r"\s*(?:➡️|➡|⇒|→)\s*")

#: `** **` — cặp đậm rỗng do model gõ lỗi. Thay bằng **khoảng trắng** (không phải chuỗi rỗng) để
#: hai chữ hai bên không dính vào nhau: `3 tỷ** **(ZEN…` → `3 tỷ (ZEN…`.
_EMPTY_BOLD_RE = re.compile(r"\*\*\s*\*\*")

_FENCE_RE = re.compile(r"^\s*```")


def _divider_columns(divider: str) -> int:
    """Số cột suy ra từ hàng phân cách (có/không có gạch dọc ngoài cùng)."""
    text = divider.strip()
    pipes = text.count("|")
    if text.startswith("|") and text.endswith("|"):
        return pipes - 1
    return pipes + 1


def _split_glued_line(line: str) -> tuple[str, list[str], str] | None:
    """Tách một dòng có bảng viết dính thành (chữ trước bảng, các dòng bảng, chữ sau bảng)."""
    match = _DIVIDER_RE.search(line)
    if not match:
        return None
    columns = _divider_columns(match.group(0))
    per_row = columns + 1
    if columns < 1:
        return None

    pipes = [i for i, ch in enumerate(line) if ch == "|"]
    head = [p for p in pipes if p < match.start()]
    tail = [p for p in pipes if p >= match.end()]
    if len(head) < per_row or len(tail) < per_row:
        return None

    head_pipes = head[-per_row:]
    rows = [tail[i : i + per_row] for i in range(0, len(tail) - per_row + 1, per_row)]

    divider = match.group(0).strip()
    if not divider.startswith("|"):
        divider = "|" + divider
    if not divider.endswith("|"):
        divider = divider + "|"

    block = [
        line[head_pipes[0] : head_pipes[-1] + 1].strip(),
        divider,
        *[line[r[0] : r[-1] + 1].strip() for r in rows],
    ]
    return line[: head_pipes[0]].strip(), block, line[rows[-1][-1] + 1 :].strip()


def _split_tables(text: str) -> str:
    """Đưa mọi bảng (kể cả bảng bị viết dính câu văn) về đúng dòng của nó."""
    lines = text.split("\n")
    out: list[str] = []
    in_fence = False
    for index, line in enumerate(lines):
        if _FENCE_RE.match(line):
            in_fence = not in_fence
            out.append(line)
            continue
        if in_fence or not line.strip():
            out.append(line)
            continue

        parts = _split_glued_line(line)
        if parts is not None:
            prefix, block, suffix = parts
            if prefix:
                out.extend([prefix, ""])
            out.extend(block)
            if suffix:
                out.extend(["", suffix])
            continue

        # Trường hợp tiêu đề bảng dính câu văn nhưng hàng phân cách lại nằm dòng dưới.
        next_line = lines[index + 1] if index + 1 < len(lines) else ""
        if _DIVIDER_ONLY_RE.match(next_line.strip()) and "-" in next_line:
            columns = _divider_columns(next_line)
            per_row = columns + 1
            pipes = [i for i, ch in enumerate(line) if ch == "|"]
            if columns >= 1 and len(pipes) >= per_row:
                head_pipes = pipes[-per_row:]
                header = line[head_pipes[0] : head_pipes[-1] + 1].strip()
                prefix = line[: head_pipes[0]].strip()
                if prefix:
                    out.extend([prefix, ""])
                out.append(header)
                continue

        out.append(line)
    return "\n".join(out)


# ─── 2. Hình thức từng dòng ────────────────────────────────────────────────────────


def _clean_line(line: str) -> str:
    """Chuẩn hoá một dòng: mũi tên, đậm rác, khoảng trắng thừa, canh cột bảng."""
    text = line.rstrip()
    text = _LEAD_ARROW_RE.sub("- ", text)
    text = _INLINE_ARROW_RE.sub(" — ", text)
    text = _EMPTY_BOLD_RE.sub(" ", text)

    stripped = text.strip()
    if _TABLE_LINE_RE.match(stripped):
        # Ô bảng: bỏ đậm (bảng vốn đã có kẻ ô phân cách) và canh lại khoảng trắng giữa các cột.
        cells = [cell.strip().replace("**", "") for cell in stripped[1:-1].split("|")]
        return "| " + " | ".join(cells) + " |"

    # Đậm mở nửa câu (số dấu `**` lẻ) sẽ hiện ra dấu sao rác → bỏ hết đậm trên dòng đó.
    if text.count("**") % 2:
        text = text.replace("**", "")
    text = re.sub(r"[ \t]{2,}", " ", text)
    text = re.sub(r"\s+([,.;:!?])", r"\1", text)
    return text.rstrip()


def _is_table_line(line: str) -> bool:
    return line.strip().startswith("|")


def _is_list_line(line: str) -> bool:
    return bool(re.match(r"^[-*•]\s+", line.strip()) or re.match(r"^\d+\.\s+", line.strip()))


def _spaced_blocks(lines: list[str]) -> list[str]:
    """Chèn dòng trống trước/sau bảng và danh sách để bộ hiển thị tách khối đúng."""
    out: list[str] = []
    for line in lines:
        if not line.strip():
            out.append(line)
            continue
        previous = out[-1] if out else ""
        starts_block = _is_table_line(line) or _is_list_line(line)
        previous_is_block = _is_table_line(previous) or _is_list_line(previous)
        if starts_block and previous.strip() and not previous_is_block:
            out.append("")
        elif not starts_block and previous_is_block:
            out.append("")
        out.append(line)
    return out


def normalize_markdown(text: str) -> str:
    """Chuẩn hoá hình thức câu trả lời (idempotent — áp lại nhiều lần vẫn cho cùng kết quả)."""
    if not text or not text.strip():
        return text
    lines = [_clean_line(line) for line in _split_tables(text).split("\n")]

    # Câu trả lời nhiều ý → mục in đậm + mỗi ý một dòng (chốt đợt 20: sẵn sàng gửi khách).
    # CHỈ tác động lên các đoạn văn xuôi: bảng, danh sách, tiêu đề do máy dựng phải giữ nguyên.
    lines = _apply_sections(lines)

    collapsed: list[str] = []
    for line in _spaced_blocks(lines):
        if not line.strip():
            if collapsed and not collapsed[-1].strip():
                continue
            collapsed.append("")
        else:
            collapsed.append(line)
    return "\n".join(collapsed).strip("\n")


# ─── 2b. Cấu trúc mục cho câu trả lời nhiều ý (sẵn sàng gửi khách) ────────────────

#: Nhãn mục quen thuộc → tiêu đề in đậm. Dò trên bản "bỏ dấu" nên khớp cả khi model viết không dấu.
SECTION_LABELS: tuple[tuple[str, str], ...] = (
    ("phuong an", "PHƯƠNG ÁN"),
    ("khuyen nghi", "KHUYẾN NGHỊ"),
    ("luu y", "LƯU Ý"),
    ("ket luan", "KẾT LUẬN"),
    ("buoc tiep theo", "BƯỚC TIẾP THEO"),
    ("ghi chu", "GHI CHÚ"),
)

#: Bảng bỏ dấu **giữ nguyên độ dài chuỗi** (mỗi ký tự tiếng Việt → một ký tự ASCII) để cắt văn bản gốc
#: theo đúng vị trí tìm được trên bản bỏ dấu.
_FOLD_TABLE = str.maketrans(
    "àáảãạăằắẳẵặâầấẩẫậđèéẻẽẹêềếểễệìíỉĩịòóỏõọôồốổỗộơờớởỡợùúủũụưừứửữựỳýỷỹỵ",
    "aaaaaaaaaaaaaaaaadeeeeeeeeeeeiiiiiooooooooooooooooouuuuuuuuuuuyyyyy",
)

#: Dấu nhãn mục: `**Khuyến nghị:**`, `Phương án:`, `_Lưu ý_ :`. Nhãn chỉ có hiệu lực khi theo sau là `:`.
_SCAN_LABEL_RE = re.compile(r"(?:\*\*|__)?\s*([a-z0-9][a-z0-9 .,()+/\-]{1,39}?)\s*[:：]\s*(?:\*\*|__)?")

#: Số ký tự tối thiểu của một câu để còn tách ý (câu cụt như "Vâng." không tạo gạch đầu dòng riêng).
_MIN_BULLET_CHARS = 12


def _fold(text: str) -> str:
    """Bỏ dấu tiếng Việt, giữ nguyên độ dài — dùng để dò nhãn mà vẫn cắt được văn bản gốc."""
    return str(text).lower().translate(_FOLD_TABLE)


def _label_title(folded: str) -> str | None:
    """Nhãn (đã bỏ dấu) → tiêu đề chuẩn, nếu nhãn nằm trong danh sách quen thuộc."""
    head = folded.strip().rstrip(".").strip()
    for key, title in SECTION_LABELS:
        if head == key:
            return title
    return None


def _split_sentences(text: str) -> list[str]:
    """Tách câu ở ranh giới `.`/`!`/`?` — không cắt ở số (`4.5 tỷ`, `31.8%`) hay viết tắt ngắn."""
    parts = re.split(r"(?<=[.!?])\s+(?=[A-ZÀ-ỸĐ*\"“(])", text.strip())
    return [part.strip() for part in parts if part.strip()]


def _is_plain_line(line: str) -> bool:
    """Dòng văn xuôi (không phải bảng, danh sách, tiêu đề markdown, trích dẫn, code fence)."""
    stripped = line.strip()
    if not stripped:
        return False
    if stripped.startswith(("|", "#", ">", "```")) or _FENCE_RE.match(stripped):
        return False
    return not _is_list_line(stripped)


def _starts_bold(text: str, label_start: int) -> bool:
    """Nhãn có được mở bằng `**`/`__` ngay trước nó không (bỏ qua khoảng trắng)?

    Phải nhìn **văn bản gốc** thay vì dựa vào kết quả regex: một nhãn trần kết thúc bằng `:` (ví dụ đoạn
    dẫn "… em đã tính 3 phương án thanh toán:") có thể "nuốt" cặp `**` mở đầu của nhãn kế tiếp, khiến
    `**PA-NHANH:**` bị coi là nhãn thường và không được tách dòng.
    """
    i = label_start
    while i > 0 and text[i - 1] in " \t":
        i -= 1
    return text[max(0, i - 2) : i] in ("**", "__")


def _markers(text: str) -> list[tuple[int, int, str, str]]:
    """Dò mốc nhãn trong một đoạn văn → `(vị trí đầu, vị trí cuối, loại, tiêu đề)`.

    - Loại `section` (`Phương án:`, `Khuyến nghị:`, `Lưu ý:`…) → tiêu đề mục in đậm.
    - Loại `item` (nhãn in đậm kiểu `**PA-NHANH (Thanh toán nhanh):**`, hoặc mã `PA-…`) → ngắt dòng để
      mỗi phương án nằm trên một dòng; nhãn được giữ nguyên trong dòng đó.
    - Loại `text` là phần văn xuôi giữa các mốc (không do hàm này sinh ra).
    """
    folded = _fold(text)
    found: list[tuple[int, int, str, str]] = []
    for match in _SCAN_LABEL_RE.finditer(folded):
        title = _label_title(match.group(1))
        label = match.group(1).strip()
        # Mở rộng mốc về bên trái để **lấy lại cặp `**` mở đầu** nếu nhãn trần phía trước đã "nuốt" nó —
        # nhờ vậy dòng phương án vẫn giữ nguyên in đậm như văn bản gốc.
        start = match.start()
        probe = start
        while probe > 0 and text[probe - 1] in " \t":
            probe -= 1
        if text[max(0, probe - 2) : probe] in ("**", "__"):
            start = max(0, probe - 2)
        # Mốc Ý phải là NHÃN IN ĐẬM mở đầu một dòng/phương án (`**PA-NHANH (…):**`) và là nhãn phương án.
        # Nhắc tới "PA-CHUDONG" giữa câu (ví dụ trong bảng/dòng kết quả của engine) KHÔNG phải mốc.
        is_item = _starts_bold(text, match.start(1)) and (
            label.startswith("pa-") or label.startswith("phuong an")
        )
        if title is None and not is_item:
            continue
        if found and match.start() < found[-1][1]:
            continue
        found.append((start, match.end(), "section" if title else "item", title or ""))
    return found


def _structure_run(lines: list[str]) -> list[str]:
    """Cấu trúc một đoạn văn xuôi thành mục in đậm + mỗi ý một dòng.

    Không có mốc nhãn nào ⇒ trả nguyên trạng (văn xuôi bình thường không bị biến thành gạch đầu dòng).
    """
    text = " ".join(line.strip() for line in lines if line.strip())
    markers = _markers(text)
    if not markers:
        return lines

    # 1) Cắt văn bản tại các mốc; chữ của mốc nằm trong chính khối của nó (giữ nguyên nhãn).
    chunks: list[tuple[str, str, str]] = []  # (loại, nội dung, tiêu đề)
    cursor = 0
    for start, stop, kind, title in markers:
        prefix = text[cursor:start].strip(" *_-")
        if prefix:
            chunks.append(("text", prefix, ""))
        chunks.append((kind, text[start:stop], title))
        cursor = stop
    tail = text[cursor:].strip()
    if tail:
        chunks.append(("text", tail, ""))

    # 2) Mỗi câu một dòng: mục in đậm mở tiêu đề; mốc Ý mở dòng mới và **hút luôn câu mô tả ngay sau
    #    nó** để nhãn với nội dung nằm cùng một dòng; văn xuôi trước mốc đầu tiên giữ làm đoạn dẫn.
    out: list[str] = []
    intro: list[str] = []
    seen_marker = False
    pending_item: str | None = None
    for kind, body, title in chunks:
        if kind == "section":
            seen_marker = True
            if pending_item:
                out.append(f"- {pending_item}")
                pending_item = None
            out.append("")
            out.append(f"**{title}:**")
            continue
        if kind == "item":
            seen_marker = True
            if pending_item:
                out.append(f"- {pending_item}")
            pending_item = body.strip()
            continue
        sentences = _split_sentences(body)
        if pending_item is not None:
            if sentences:
                out.append(f"- {pending_item} {sentences[0]}".rstrip())
                pending_item = None
                sentences = sentences[1:]
            else:
                continue
        for sentence in sentences:
            if not seen_marker:
                intro.append(sentence)
            else:
                out.append(f"- {sentence}")
    if pending_item:
        out.append(f"- {pending_item}")

    if intro:
        out = [" ".join(intro), *out]
    return out


def _apply_sections(lines: list[str]) -> list[str]:
    """Cấu trúc **từng đoạn văn xuôi** trong danh sách dòng; dòng đã có cấu trúc giữ nguyên.

    Vì sao phải theo *đoạn* chứ không theo cả văn bản: phần kết quả của engine (`- PA-CHUDONG (…): giá Net …`)
    là **danh sách do máy dựng** — gom cả văn bản lại để "cấu trúc" sẽ xoá sạch gạch đầu dòng và số liệu
    xuống dòng của nó.
    """
    out: list[str] = []
    run: list[str] = []
    fence = False

    def flush() -> None:
        if run:
            out.extend(_structure_run(run))
            run.clear()

    for line in lines:
        if _FENCE_RE.match(line):
            fence = not fence
        if not fence and _is_plain_line(line):
            run.append(line)
            continue
        flush()
        out.append(line)
    flush()
    return out


def structure_sections(text: str) -> str:
    """Tách câu trả lời nhiều ý thành **mục in đậm + mỗi ý một dòng** (idempotent).

    Chỉ áp cho các **đoạn văn xuôi** có nhãn mục (`Phương án:`, `Khuyến nghị:`, `Lưu ý:`…). Bảng, danh
    sách và tiêu đề markdown đi qua nguyên vẹn — không phá bảng giỏ hàng do máy dựng ở bước sau.
    """
    if not text or not text.strip():
        return text
    return "\n".join(_apply_sections(text.split("\n")))


# ─── 3. Không lộ tên nội bộ ────────────────────────────────────────────────────────

#: Tên tool → cách nói nghiệp vụ (Sale đọc hiểu ngay, không thấy chuyện kỹ thuật).
_TOOL_LABELS = {
    "tra_cuu_gio_hang": "tra cứu giỏ hàng",
    "tra_cuu_chinh_sach": "tra cứu chính sách",
    "tinh_phuong_an_thanh_toan": "phương án thanh toán chi tiết",
    "danh_gia_von_tu_co": "đánh giá vốn tự có",
    "soan_tin_tu_van": "soạn tin tư vấn",
    "tao_khach_hang": "tạo khách hàng",
    "kiem_tra_phat_ngon_f8": "kiểm tra tuân thủ F8",
}

#: Mọi định danh snake_case (tham số, trường dữ liệu, tên tool).
_SNAKE_RE = re.compile(r"\b[a-z][a-z0-9]*(?:_[a-z0-9]+)+\b")
#: Ngoặc chỉ chứa tham số nội bộ → bỏ cả ngoặc (ví dụ `(gia_toi_da_vnd = 0, …)`).
_PAREN_RE = re.compile(r"\([^()]*\)")
#: `gia_toi_da_vnd = 0` còn sót ngoài ngoặc.
_ASSIGN_RE = re.compile(r"\b[a-z][a-z0-9]*(?:_[a-z0-9]+)+\b\s*=\s*[^\s,;.)]+")
#: Giới từ lơ lửng sau khi bỏ cụm nội bộ: "với ," → ",".
_DANGLING_PREP_RE = re.compile(r"\b(với|theo|bằng|dùng|từ|do|qua|của|và)\s*([,.;:!?])")


def _tidy(text: str) -> str:
    text = re.sub(r"[ \t]{2,}", " ", text)
    text = re.sub(r"[ \t]+([,.;:!?])", r"\1", text)
    text = re.sub(r"\(\s*\)", "", text)
    text = _DANGLING_PREP_RE.sub(r"\2", text)
    text = re.sub(r"(\s*—\s*){2,}", " — ", text)
    return text


def strip_internal_names(text: str) -> tuple[str, list[str]]:
    """Bỏ tên tool/tham số nội bộ khỏi văn bản trả lời.

    Trả về `(văn bản đã sạch, danh sách định danh đã bỏ)` để lớp trên ghi log — cần biết model
    đang rò rỉ gì mà chỉnh prompt, chứ không im lặng che đi.
    """
    if not text:
        return text, []

    found: list[str] = []

    def _drop_parentheses(match: re.Match[str]) -> str:
        inner = match.group(0)
        tokens = _SNAKE_RE.findall(inner)
        if not tokens:
            return inner
        found.extend(tokens)
        return ""

    cleaned = _PAREN_RE.sub(_drop_parentheses, text)

    def _drop_assignment(match: re.Match[str]) -> str:
        found.append(_SNAKE_RE.findall(match.group(0))[0])
        return ""

    cleaned = _ASSIGN_RE.sub(_drop_assignment, cleaned)

    # "tool tinh_phuong_an_thanh_toan" → "phương án thanh toán chi tiết"
    cleaned = re.sub(r"\btool\s+", "", cleaned)
    for name, label in _TOOL_LABELS.items():
        if name in cleaned:
            found.append(name)
            cleaned = cleaned.replace(name, label)

    def _drop_token(match: re.Match[str]) -> str:
        token = match.group(0)
        if token in _TOOL_LABELS:
            return _TOOL_LABELS[token]
        found.append(token)
        return ""

    cleaned = _SNAKE_RE.sub(_drop_token, cleaned)
    if found:
        cleaned = _tidy(cleaned)
    return cleaned, found


# ─── 4. Che phần trích dẫn khi quét rò rỉ ──────────────────────────────────────────

#: Các cặp ngoặc kép thường gặp (nháy đơn cũng dùng vì tool in `'câu bị chặn'`).
_QUOTED_SPAN_RE = re.compile(r"['\"“”‘’«»]([^'\"“”‘’«»]{4,300})['\"“”‘’«»]")


def _normalize_claim(text: str) -> str:
    lowered = text.lower().replace("\u2019", "'")
    return re.sub(r"\s+", " ", lowered).strip(" .,;:'\"“”‘’")


def mask_quoted_claims(text: str, claims: list[str]) -> tuple[str, int]:
    """Thay các đoạn **trích dẫn lại câu đang bị kiểm duyệt** bằng một ký hiệu an toàn.

    Vì sao cần: khi Sale nhờ kiểm một phát ngôn rủi ro ("cam kết sinh lời 20% mỗi năm"), kết luận kiểm
    duyệt **buộc phải trích lại** đúng câu đó để nói rõ chỗ sai. Nếu đem quét rò rỉ cả câu trả lời thì
    chính phần trích dẫn hợp lệ này kích hoạt luật cấm "cam kết sinh lời" ⇒ bộ chặn nuốt mất kết luận,
    và Sale không nhận được cảnh báo ở đúng ca quan trọng nhất.

    Nguyên tắc an toàn: **chỉ** che đoạn nằm trong ngoặc kép và **khớp với văn bản đã được kiểm duyệt**
    (do tool cung cấp). Câu do model tự viết, kể cả khi na ná, vẫn bị quét bình thường — không nới lỏng.

    Trả về `(văn bản đã che, số đoạn đã che)`.
    """
    if not text or not claims:
        return text, 0
    wanted = [_normalize_claim(c) for c in claims if c and c.strip()]
    if not wanted:
        return text, 0

    masked = 0

    def _replace(match: re.Match[str]) -> str:
        nonlocal masked
        inner = _normalize_claim(match.group(1))
        if not inner:
            return match.group(0)
        for claim in wanted:
            if len(inner) >= 6 and (inner in claim or claim in inner):
                masked += 1
                return "[nội dung đang được kiểm duyệt]"
        return match.group(0)

    return _QUOTED_SPAN_RE.sub(_replace, text), masked


#: Độ dài tối thiểu của một dòng **do engine viết** để được miễn theo kiểu trùng nguyên văn.
REVIEW_TEXT_MIN_CHARS = 12


def mask_review_text(
    text: str,
    *,
    engine_texts: list[str] | None = None,
    reviewed_texts: list[str] | None = None,
) -> tuple[str, int]:
    """Che phần **do hệ thống kiểm duyệt sinh ra** trước khi quét rò rỉ đầu ra.

    Phải tách đúng hai loại văn bản, vì mức độ tin cậy khác nhau:

    * `engine_texts` — câu chữ do **engine tất định** viết (dòng kết luận, lý do, mã luật). Đây là văn
      bản của hệ thống, hiển thị nguyên văn cho Sale là đúng ⇒ miễn theo kiểu **trùng nguyên văn**
      (≥ 12 ký tự). Không có đường nào để model lợi dụng: câu model tự viết không trùng nguyên văn.
    * `reviewed_texts` — **nội dung đang bị kiểm duyệt** (câu Sale nhờ kiểm, câu bị gắn cờ). Đây là văn
      bản có thể chứa cụm từ nguy hiểm, nên **chỉ** được miễn khi nằm trong **ngoặc kép** và khớp với
      chính văn bản đó — tức là đang được *trích dẫn để nói rõ chỗ sai*.

    Nhờ vậy: kết luận F8 hiển thị được đầy đủ (cả phần trích dẫn lẫn lời giải thích), mà một câu cam kết
    trái luật do model tự viết — dù có bọc ngoặc kép — vẫn bị chặn như cũ.
    """
    if not text:
        return text, 0

    masked_text = text
    masked_count = 0

    lines = sorted(
        {s.strip() for s in (engine_texts or []) if s and len(s.strip()) >= REVIEW_TEXT_MIN_CHARS},
        key=len,
        reverse=True,
    )
    for line in lines:
        if line in masked_text:
            masked_count += masked_text.count(line)
            masked_text = masked_text.replace(line, "[nội dung đang được kiểm duyệt]")

    masked_text, quoted_count = mask_quoted_claims(masked_text, list(reviewed_texts or []))
    return masked_text, masked_count + quoted_count


__all__ = [
    "REVIEW_TEXT_MIN_CHARS",
    "mask_quoted_claims",
    "mask_review_text",
    "normalize_markdown",
    "strip_internal_names",
]
