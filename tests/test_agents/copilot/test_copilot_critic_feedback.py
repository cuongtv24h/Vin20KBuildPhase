"""Test cho hai năng lực P2: critic vòng 2 và học từ phản hồi.

- critic: soi lập luận/phát ngôn của câu trả lời (không chỉ đối chiếu con số như verifier).
- feedback: log phản hồi của Sale → thống kê → biến thành "điều cần tránh" trong prompt.
"""

from __future__ import annotations

import pytest

from src.agents.copilot import critic, feedback
from src.agents.copilot.graph import CopilotRequest, stream_copilot

# ─── Critic ─────────────────────────────────────────────────────────────────


def test_critic_flags_money_without_evidence_anchor():
    result = critic.critique_reply("Căn này có giá 4,2 tỷ và chiết khấu tốt cho anh.")
    assert result.ok is False
    assert any(i["code"] == "MONEY_WITHOUT_ANCHOR" for i in result.issues)
    assert critic.revision_note(result)


def test_critic_accepts_number_with_anchor_and_condition():
    result = critic.critique_reply(
        "Căn ZEN-A-1205 giá 4,2 tỷ, chiết khấu 8% cho thanh toán sớm 95% nếu anh đủ điều kiện [1]."
    )
    assert result.ok is True
    assert critic.revision_note(result) == ""


def test_critic_flags_over_promise_language():
    result = critic.critique_reply("Em cam kết ngân hàng sẽ duyệt vay 100% cho anh.")
    assert result.ok is False
    assert any(i["code"] == "OVER_PROMISE" for i in result.issues)


def test_critic_flags_offer_without_condition():
    result = critic.critique_reply("Dự án áp dụng lãi suất 0% cho anh ngay bây giờ.")
    assert result.ok is False
    assert any(i["code"] == "OFFER_WITHOUT_CONDITION" for i in result.issues)


def test_critic_skips_low_stakes_turns():
    """Câu chào hỏi không tốn công soi (tối ưu chi phí/độ trễ)."""
    assert critic.is_high_stakes("Dạ em chào anh, em có thể giúp gì ạ?") is False
    assert critic.is_high_stakes("Giá căn này 4,2 tỷ") is True
    assert critic.is_high_stakes("Dạ vâng", intent="smart_compose_message") is True


# ─── Feedback ───────────────────────────────────────────────────────────────


def test_feedback_is_recorded_and_summarized(tmp_path):
    path = tmp_path / "fb.jsonl"
    feedback.record_feedback(message="Giá căn A?", reply="4,2 tỷ", rating=1, path=path)
    feedback.record_feedback(
        message="Tính phương án giúp em",
        reply="...",
        rating=-1,
        comment="thiếu căn cứ",
        tags=["thieu_can_cu"],
        path=path,
    )

    summary = feedback.summarize_feedback(feedback.load_feedback(path))
    assert summary["total"] == 2
    assert summary["up"] == 1 and summary["down"] == 1
    assert summary["satisfaction_rate"] == 0.5
    assert summary["top_negative_tags"][0] == ("thieu_can_cu", 1)


def test_feedback_hints_surface_negative_examples_only(tmp_path):
    path = tmp_path / "fb.jsonl"
    feedback.record_feedback(message="câu bị chê", rating=-1, comment="sai số", path=path)
    feedback.record_feedback(message="câu được khen", rating=1, path=path)

    hints = feedback.few_shot_hints(feedback.load_feedback(path))
    assert len(hints) == 1
    assert "câu bị chê" in hints[0] and "sai số" in hints[0]


def test_feedback_skips_corrupted_lines(tmp_path):
    path = tmp_path / "fb.jsonl"
    path.write_text('{"rating": 1, "message": "ok"}\n{ hỏng\n', encoding="utf-8")
    entries = feedback.load_feedback(path)
    assert len(entries) == 1 and entries[0]["message"] == "ok"


def test_feedback_summary_is_empty_safe(tmp_path):
    summary = feedback.summarize_feedback([])
    assert summary["total"] == 0
    assert summary["satisfaction_rate"] is None


# ─── Prompt động ────────────────────────────────────────────────────────────


def test_system_prompt_includes_avoid_examples():
    from src.agents.copilot.prompts import build_system_prompt

    prompt = build_system_prompt({"avoid_examples": ["Sale đã chê câu trả lời thiếu căn cứ"]})
    assert "ĐIỀU CẦN TRÁNH" in prompt
    assert "thiếu căn cứ" in prompt


@pytest.mark.asyncio
async def test_final_payload_carries_critique(tmp_path, monkeypatch):
    """Mọi lượt trả lời đều có trường `critique` để UI/hậu kiểm đọc được."""
    monkeypatch.setenv("COPILOT_FEEDBACK_PATH", str(tmp_path / "fb.jsonl"))
    from tests.test_agents.copilot.test_copilot_react import FailingLLM

    events = [
        event
        async for event in stream_copilot(
            CopilotRequest(message="Chính sách chiết khấu thanh toán sớm hiện hành là bao nhiêu?"),
            llm=FailingLLM(),
        )
    ]
    final = next(e.data for e in events if e.type == "final")
    assert "critique" in final and "ok" in final["critique"]


def test_critic_does_not_flag_engine_scenario_table():
    """Bảng 3 phương án do engine sinh có 'khả thi: có/không' → không tính là nói ưu đãi thiếu điều kiện."""
    reply = (
        "Kết quả engine tất định cho ZEN-A-1205 (objective MIN_INITIAL_CASH):\n"
        "- PA-NHANH (Phương án Thanh toán sớm (Chiết khấu 8%)): giá Net 3.864.000.000 ₫ · ưu đãi 336.000.000 ₫ · khả thi: có\n"
        "- PA-VAY (Phương án Hỗ trợ Lãi suất Ngân hàng): lãi suất 0% trong 24 tháng · khả thi: có"
    )
    assert critic.critique_reply(reply).ok is True


def test_critic_accepts_policy_code_anchor_without_numeric_marker():
    """Trích nguồn bằng mã văn bản [CSBH-…] cũng tính là mỏ neo, không chỉ [1]."""
    reply = "Chiết khấu thanh toán sớm là 8.0% [CSBH-ZEN-2026-V3.1 · Điều 4, Khoản 2b]."
    assert critic.critique_reply(reply).ok is True
