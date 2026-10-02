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
    """Thống kê: tổng, theo nhãn, tỉ lệ hài lòng, tag bị chê nhiều nhất."""
    data = entries if entries is not None else load_feedback()
    labels = Counter(str(e.get("label", "unknown")) for e in data)
    tags = Counter(t for e in data if int(e.get("rating", 0)) < 0 for t in (e.get("tags") or []))
    up, down = labels.get("up", 0), labels.get("down", 0)
    rated = up + down
    return {
        "total": len(data),
        "up": up,
        "down": down,
        "neutral": labels.get("neutral", 0),
        "satisfaction_rate": round(up / rated, 4) if rated else None,
        "top_negative_tags": tags.most_common(5),
    }


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
