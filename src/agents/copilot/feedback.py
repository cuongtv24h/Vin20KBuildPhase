"""Học từ phản hồi (§3.3 P2) — log thumbs của Sale và biến thành gợi ý few-shot.

Thiết kế cố ý đơn giản để chạy được cả khi chưa có hạ tầng:
- Mỗi phản hồi là **một dòng JSONL** (append-only, không cần DB migration).
- Tổng hợp: đếm theo nhãn + tỉ lệ hài lòng + các ví dụ bị chê gần nhất.
- `few_shot_hints()` trả về vài câu bị chê để nhét vào system prompt dưới dạng **điều cần tránh**,
  đúng tinh thần "few-shot động" mà không cần fine-tune.

Đường dẫn log lấy từ `COPILOT_FEEDBACK_PATH`, mặc định `eval/results/copilot_feedback.jsonl`.
"""

from __future__ import annotations

import json
import os
import re
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

DEFAULT_FEEDBACK_PATH = Path("eval/results/copilot_feedback.jsonl")
#: Số ví dụ tiêu cực tối đa nhét vào prompt (nhiều hơn thì phình ngữ cảnh mà lợi ích giảm dần).
MAX_FEW_SHOT_HINTS = 3
#: Cắt độ dài mỗi ví dụ trước khi đưa vào prompt.
MAX_HINT_CHARS = 240

RATING_LABELS = {1: "up", 0: "neutral", -1: "down"}

#: Số ngày gần nhất đưa vào biểu đồ xu hướng của trang quản trị.
TREND_DAYS = 14
#: Che PII khi hiển thị cho người khác ngoài người gửi phản hồi (SĐT/email của khách).
_PHONE_RE = re.compile(r"\b0\d{8,10}\b")
_EMAIL_RE = re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.]+\b")


def mask_pii(text: str) -> str:
    """Che số điện thoại/email trong nội dung trước khi trả cho trang quản trị.

    Câu hỏi của Sale thường kèm tên + SĐT khách ("tạo khách Nguyễn Văn A 0912345678").
    Trang chất lượng chỉ cần *nội dung nghiệp vụ* để đánh giá Copilot, không cần PII.
    """
    masked = _PHONE_RE.sub(lambda m: m.group(0)[:3] + "***" + m.group(0)[-2:], str(text or ""))
    return _EMAIL_RE.sub("***@***", masked)


def feedback_path() -> Path:
    override = os.getenv("COPILOT_FEEDBACK_PATH", "").strip()
    return Path(override) if override else DEFAULT_FEEDBACK_PATH


def record_feedback(
    *,
    message: str,
    reply: str = "",
    rating: int,
    comment: str = "",
    tags: list[str] | None = None,
    mode: str | None = None,
    tools_used: list[str] | None = None,
    turn_id: str | None = None,
    path: Path | None = None,
) -> dict[str, Any]:
    """Ghi một phản hồi. Trả về bản ghi đã lưu (kèm thời điểm)."""
    entry = {
        "recorded_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "rating": int(rating),
        "label": RATING_LABELS.get(int(rating), "unknown"),
        "message": str(message or "")[:600],
        "reply": str(reply or "")[:1200],
        "comment": str(comment or "")[:400],
        "tags": [str(t)[:40] for t in (tags or [])][:8],
        "mode": mode,
        "tools_used": list(tools_used or [])[:8],
        "turn_id": turn_id,
    }
    target = path or feedback_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
    return entry


def load_feedback(path: Path | None = None, *, limit: int = 500) -> list[dict[str, Any]]:
    """Đọc log (mới nhất ở cuối file); bỏ qua dòng hỏng thay vì làm sập endpoint."""
    target = path or feedback_path()
    if not target.exists():
        return []
    entries: list[dict[str, Any]] = []
    with target.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError:  # pragma: no cover — dòng hỏng do ghi dở
                continue
    return entries[-limit:]


def summarize_feedback(entries: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    """Thống kê cho trang quản trị chất lượng: tổng, tỉ lệ hài lòng, xu hướng, nguyên nhân chê."""
    data = entries if entries is not None else load_feedback()
    labels = Counter(str(e.get("label", "unknown")) for e in data)
    negative = [e for e in data if int(e.get("rating", 0)) < 0]
    tags = Counter(t for e in negative for t in (e.get("tags") or []))
    modes = Counter(str(e.get("mode") or "không rõ") for e in data)
    tools = Counter(t for e in negative for t in (e.get("tools_used") or []))

    up, down = labels.get("up", 0), labels.get("down", 0)
    rated = up + down

    # Xu hướng theo ngày (TREND_DAYS gần nhất) — chỉ tính ngày có phát sinh để vẽ biểu đồ.
    by_day: list[dict[str, Any]] = []
    day_counter: dict[str, dict[str, int]] = {}
    for entry in data:
        stamp = str(entry.get("recorded_at") or "")[:10]
        if not stamp:
            continue
        bucket = day_counter.setdefault(stamp, {"up": 0, "down": 0})
        rating = int(entry.get("rating", 0))
        if rating > 0:
            bucket["up"] += 1
        elif rating < 0:
            bucket["down"] += 1
    for stamp in sorted(day_counter)[-TREND_DAYS:]:
        by_day.append({"date": stamp, **day_counter[stamp]})
    # Ngày chưa có phản hồi vẫn phải xuất hiện trên biểu đồ để không hiểu sai là "mất dữ liệu".
    filled: list[dict[str, Any]] = []
    if by_day:
        from datetime import date as _date
        from datetime import timedelta

        start = _date.fromisoformat(by_day[0]["date"])
        end = _date.fromisoformat(by_day[-1]["date"])
        cursor = start
        known = {row["date"]: row for row in by_day}
        while cursor <= end:
            key = cursor.isoformat()
            filled.append(known.get(key) or {"date": key, "up": 0, "down": 0})
            cursor += timedelta(days=1)

    return {
        "total": len(data),
        "up": up,
        "down": down,
        "neutral": labels.get("neutral", 0),
        "satisfaction_rate": round(up / rated, 4) if rated else None,
        "top_negative_tags": tags.most_common(5),
        "by_mode": [{"mode": mode, "count": count} for mode, count in modes.most_common()],
        "by_day": filled[-TREND_DAYS:],
        "top_failing_tools": tools.most_common(5),
        "recent_negative": [_entry_view(e) for e in reversed(negative[-5:])],
    }


def _entry_view(entry: dict[str, Any], *, mask: bool = False) -> dict[str, Any]:
    """Bản ghi đã lọc trường + (tuỳ chọn) che PII, dùng cho API quản trị."""
    text_fields = {
        "message": entry.get("message", ""),
        "reply": entry.get("reply", ""),
        "comment": entry.get("comment", ""),
    }
    if mask:
        text_fields = {k: mask_pii(v) for k, v in text_fields.items()}
    return {
        "recorded_at": entry.get("recorded_at"),
        "rating": int(entry.get("rating", 0)),
        "label": entry.get("label", "unknown"),
        **text_fields,
        "tags": list(entry.get("tags") or []),
        "mode": entry.get("mode"),
        "tools_used": list(entry.get("tools_used") or []),
        "turn_id": entry.get("turn_id"),
    }


def list_recent(*, limit: int = 50, rating: int | None = None, mask: bool = True) -> list[dict[str, Any]]:
    """Danh sách phản hồi gần nhất (mới nhất trước), tuỳ chọn lọc theo điểm đánh giá."""
    entries = load_feedback(limit=1000)
    if rating is not None:
        entries = [e for e in entries if int(e.get("rating", 0)) == rating]
    return [_entry_view(e, mask=mask) for e in reversed(entries[-limit:])]


def few_shot_hints(entries: list[dict[str, Any]] | None = None, *, limit: int = MAX_FEW_SHOT_HINTS) -> list[str]:
    """Ví dụ bị chê gần nhất → chuỗi ngắn để nhét vào prompt dưới dạng "tránh lặp lại"."""
    data = entries if entries is not None else load_feedback()
    hints: list[str] = []
    for entry in reversed(data):
        if int(entry.get("rating", 0)) >= 0:
            continue
        question = str(entry.get("message", "")).strip()
        comment = str(entry.get("comment", "")).strip()
        if not question:
            continue
        hint = f"Người dùng đã chê câu hỏi “{question[:120]}”" + (f" — lý do: {comment[:80]}" if comment else "")
        hints.append(hint[:MAX_HINT_CHARS])
        if len(hints) >= limit:
            break
    return hints
