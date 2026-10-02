"""Hai tiến trình cùng ghi lịch sử (mô phỏng `uvicorn --workers 2` trên VM) — không được mất lượt.

Vì sao có test này: production chạy pm2 với `uvicorn --workers 2`, tức hai tiến trình Python riêng
biệt cùng đọc–sửa–ghi một file JSON. Bản cũ chỉ có `threading.Lock` (khoá trong một tiến trình),
nên hai worker ghi đè lẫn nhau và lượt hỏi–đáp biến mất khỏi lịch sử — đúng triệu chứng Sale báo
"không thấy hội thoại cũ". Test này chạy thật nhiều tiến trình ghi song song và đòi hỏi **đủ** số lượt.
"""

from __future__ import annotations

import multiprocessing as mp
from pathlib import Path

from src.agents.copilot import history

TURNS_PER_PROCESS = 15
PROCESSES = 3


def _worker(conversation_id: str, worker_index: int, path: str) -> None:
    """Ghi liên tiếp nhiều lượt vào CÙNG một cuộc hội thoại từ một tiến trình riêng."""
    import os

    os.environ["COPILOT_HISTORY_PATH"] = path
    for turn in range(TURNS_PER_PROCESS):
        history.append_turn(
            "sale-concurrent",
            conversation_id=conversation_id,
            user_message=f"câu {worker_index}-{turn}",
            assistant_message=f"đáp {worker_index}-{turn}",
        )


def test_nhieu_tien_trinh_ghi_song_song_khong_mat_luot(tmp_path: Path, monkeypatch) -> None:
    history_path = tmp_path / "conversations.json"
    monkeypatch.setenv("COPILOT_HISTORY_PATH", str(history_path))

    created = history.create_conversation("sale-concurrent", "Kiểm tra ghi song song")
    conversation_id = created["conversation_id"]

    ctx = mp.get_context("fork")  # fork để con thừa hưởng ENV trỏ đúng file tạm
    workers = [
        ctx.Process(target=_worker, args=(conversation_id, i, str(history_path))) for i in range(PROCESSES)
    ]
    for w in workers:
        w.start()
    for w in workers:
        w.join(timeout=60)
        assert w.exitcode == 0, f"tiến trình con lỗi (exit={w.exitcode})"

    detail = history.get_conversation("sale-concurrent", conversation_id)
    assert detail is not None
    expected_messages = PROCESSES * TURNS_PER_PROCESS * 2  # mỗi lượt có 1 câu hỏi + 1 câu trả lời
    assert detail["message_count"] == expected_messages, (
        f"mất lượt: có {detail['message_count']}/{expected_messages} message "
        "— khoá liên tiến trình (flock) đang không hoạt động"
    )

    # Câu trả lời của mọi tiến trình đều phải còn trong file lịch sử.
    contents = {m["content"] for m in detail["messages"]}
    for i in range(PROCESSES):
        assert f"đáp {i}-{TURNS_PER_PROCESS - 1}" in contents
