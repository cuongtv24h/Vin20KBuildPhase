"""Lịch sử hội thoại Copilot — giữ và tra cứu lại được.

Trước đây nội dung chat chỉ nằm trong state React: rời trang (đổi route, F5) là mất sạch, không có
cách nào xem lại câu hỏi/câu trả lời cũ. Module này lưu hội thoại **theo từng nhân viên** xuống đĩa
(JSON, append-theo-lượt) để:

- Sale mở lại trang là thấy cuộc trò chuyện gần nhất;
- tra lại được các cuộc cũ trong danh sách "Lịch sử hội thoại";
- vẫn đọc được sau khi restart server (khác với store in-memory).

Chọn JSON file thay vì DB vì: không cần migration, chạy được cả khi hạ tầng DB chưa sẵn sàng, và
khối lượng dữ liệu nhỏ (mỗi nhân viên giữ tối đa `MAX_CONVERSATIONS_PER_USER` cuộc). Đường dẫn lấy
từ `COPILOT_HISTORY_PATH`, mặc định `data/copilot_conversations.json`.
"""

from __future__ import annotations

import contextlib
import json
import os
import threading
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

DEFAULT_HISTORY_PATH = Path("data/copilot_conversations.json")
#: Trần số cuộc hội thoại mỗi nhân viên (cũ nhất bị cắt trước).
MAX_CONVERSATIONS_PER_USER = 50
#: Trần số lượt (message) mỗi cuộc — Copilot chỉ cần ngữ cảnh gần, không cần cả lịch sử.
MAX_MESSAGES_PER_CONVERSATION = 200
#: Độ dài tiêu đề tối đa suy ra từ câu hỏi đầu tiên.
TITLE_MAX_CHARS = 80

#: Khoá trong MỘT tiến trình (an toàn luồng của uvicorn).
_LOCK = threading.Lock()

try:  # POSIX — dùng được trên VM Ubuntu
    import fcntl
except ImportError:  # pragma: no cover - Windows dev không có fcntl
    fcntl = None  # type: ignore[assignment]

VALID_ROLES = ("user", "assistant")


def _path() -> Path:
    """Đường dẫn file lịch sử (đọc runtime để test/ẩn danh đổi được qua ENV)."""
    raw = os.environ.get("COPILOT_HISTORY_PATH")
    return Path(raw) if raw else DEFAULT_HISTORY_PATH


def _empty_store() -> dict[str, Any]:
    return {"version": 1, "conversations": []}


def _read_store() -> dict[str, Any]:
    path = _path()
    if not path.exists():
        return _empty_store()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return _empty_store()
    if not isinstance(data, dict) or not isinstance(data.get("conversations"), list):
        return _empty_store()
    return data


def _write_store(store: dict[str, Any]) -> None:
    path = _path()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(store, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(path)


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _derive_title(first_message: str) -> str:
    text = " ".join((first_message or "").split())
    if not text:
        return "Cuộc trò chuyện mới"
    return text if len(text) <= TITLE_MAX_CHARS else text[: TITLE_MAX_CHARS - 1].rstrip() + "…"


@contextlib.contextmanager
def _process_lock():
    """Khoá **liên tiến trình** cho các thao tác đọc–sửa–ghi file lịch sử.

    Vì sao cần: production chạy `uvicorn --workers 2` (xem `deploy/ecosystem.config.cjs`) — hai
    tiến trình Python riêng biệt cùng đọc/sửa/ghi một file JSON. `threading.Lock` chỉ khoá trong
    nội bộ một tiến trình, nên hai worker ghi đè lẫn nhau: lượt hỏi–đáp của nhau biến mất khỏi
    lịch sử (Sale "không thấy hội thoại cũ"). `flock` trên file `.lock` cạnh file dữ liệu khoá
    được cả liên tiến trình; máy không có `fcntl` (Windows) thì lùi về khoá luồng như trước.
    """
    path = _path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with _LOCK:
        if fcntl is None:
            yield
            return
        lock_path = path.with_suffix(path.suffix + ".lock")
        with open(lock_path, "w", encoding="utf-8") as handle:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def _public(conversation: dict[str, Any], *, with_messages: bool) -> dict[str, Any]:
    base = {
        "conversation_id": conversation["conversation_id"],
        "title": conversation.get("title") or "Cuộc trò chuyện mới",
        "created_at": conversation.get("created_at"),
        "updated_at": conversation.get("updated_at"),
        "message_count": len(conversation.get("messages") or []),
        "last_message": next(
            (m.get("content", "") for m in reversed(conversation.get("messages") or []) if m.get("role") == "assistant"),
            "",
        )[:160],
    }
    if with_messages:
        base["messages"] = [
            {
                "role": m.get("role"),
                "content": m.get("content", ""),
                "at": m.get("at"),
                "citations": m.get("citations") or [],
                "action_type": m.get("action_type"),
            }
            for m in conversation.get("messages") or []
            if m.get("role") in VALID_ROLES
        ]
    return base


def _find(store: dict[str, Any], user_id: str, conversation_id: str) -> dict[str, Any] | None:
    return next(
        (c for c in store["conversations"] if c.get("user_id") == user_id and c.get("conversation_id") == conversation_id),
        None,
    )


def list_conversations(user_id: str, *, limit: int = 30) -> list[dict[str, Any]]:
    """Danh sách cuộc hội thoại của một nhân viên, mới nhất trước."""
    with _process_lock():
        store = _read_store()
        items = [c for c in store["conversations"] if c.get("user_id") == user_id]
        items.sort(key=lambda c: c.get("updated_at") or "", reverse=True)
        return [_public(c, with_messages=False) for c in items[: max(1, limit)]]


def get_conversation(user_id: str, conversation_id: str) -> dict[str, Any] | None:
    """Chi tiết một cuộc hội thoại (kèm toàn bộ lượt). Chỉ chủ sở hữu đọc được."""
    with _process_lock():
        store = _read_store()
        found = _find(store, user_id, conversation_id)
        return _public(found, with_messages=True) if found else None


def create_conversation(user_id: str, title: str | None = None) -> dict[str, Any]:
    """Tạo cuộc hội thoại mới (chưa có lượt nào)."""
    with _process_lock():
        store = _read_store()
        now = _now()
        conversation = {
            "conversation_id": f"CNV-{uuid.uuid4().hex[:10]}",
            "user_id": user_id,
            "title": (title or "").strip() or "Cuộc trò chuyện mới",
            "created_at": now,
            "updated_at": now,
            "messages": [],
        }
        store["conversations"].append(conversation)
        _trim(store, user_id)
        _write_store(store)
        return _public(conversation, with_messages=True)


def append_turn(
    user_id: str,
    *,
    conversation_id: str | None,
    user_message: str,
    assistant_message: str,
    citations: list[dict[str, Any]] | None = None,
    action_type: str | None = None,
) -> dict[str, Any]:
    """Ghi một lượt hỏi–đáp vào hội thoại (tự tạo hội thoại nếu chưa có).

    Trả về bản ghi hội thoại đã cập nhật — FE dùng luôn `conversation_id` cho lượt kế tiếp.
    """
    with _process_lock():
        store = _read_store()
        conversation = _find(store, user_id, conversation_id) if conversation_id else None
        if conversation is None:
            now = _now()
            conversation = {
                "conversation_id": f"CNV-{uuid.uuid4().hex[:10]}",
                "user_id": user_id,
                "title": _derive_title(user_message),
                "created_at": now,
                "updated_at": now,
                "messages": [],
            }
            store["conversations"].append(conversation)
        now = _now()
        if user_message.strip():
            conversation["messages"].append({"role": "user", "content": user_message.strip(), "at": now})
        if assistant_message.strip():
            conversation["messages"].append(
                {
                    "role": "assistant",
                    "content": assistant_message.strip(),
                    "at": now,
                    "citations": citations or [],
                    "action_type": action_type,
                }
            )
        conversation["messages"] = conversation["messages"][-MAX_MESSAGES_PER_CONVERSATION:]
        if conversation.get("title") in (None, "", "Cuộc trò chuyện mới") and user_message.strip():
            conversation["title"] = _derive_title(user_message)
        conversation["updated_at"] = now
        _trim(store, user_id)
        _write_store(store)
        return _public(conversation, with_messages=True)


def rename_conversation(user_id: str, conversation_id: str, title: str) -> dict[str, Any] | None:
    with _process_lock():
        store = _read_store()
        found = _find(store, user_id, conversation_id)
        if not found:
            return None
        found["title"] = (title or "").strip() or found.get("title")
        found["updated_at"] = _now()
        _write_store(store)
        return _public(found, with_messages=False)


def delete_conversation(user_id: str, conversation_id: str) -> bool:
    with _process_lock():
        store = _read_store()
        before = len(store["conversations"])
        store["conversations"] = [
            c for c in store["conversations"] if not (c.get("user_id") == user_id and c.get("conversation_id") == conversation_id)
        ]
        if len(store["conversations"]) == before:
            return False
        _write_store(store)
        return True


def _trim(store: dict[str, Any], user_id: str) -> None:
    """Giữ tối đa `MAX_CONVERSATIONS_PER_USER` cuộc/người — cắt cuộc cũ nhất."""
    mine = [c for c in store["conversations"] if c.get("user_id") == user_id]
    if len(mine) <= MAX_CONVERSATIONS_PER_USER:
        return
    mine.sort(key=lambda c: c.get("updated_at") or "", reverse=True)
    keep = {c["conversation_id"] for c in mine[:MAX_CONVERSATIONS_PER_USER]}
    store["conversations"] = [
        c for c in store["conversations"] if c.get("user_id") != user_id or c.get("conversation_id") in keep
    ]
