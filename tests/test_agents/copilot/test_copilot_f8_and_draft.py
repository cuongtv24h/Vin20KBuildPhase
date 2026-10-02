"""Hồi quy cho hai lỗi thật phát hiện ở đợt 15 (bộ kịch bản Sale):

1. **Kết luận kiểm duyệt F8 bị bộ chặn rò rỉ nuốt mất.** Kết luận buộc phải trích lại câu bị chặn
   ("cam kết sinh lời 20%"), mà luật cấm `ILLEGAL_COMMITMENT_VI` lại khớp chính phần trích dẫn ⇒ toàn bộ
   câu trả lời bị thay bằng câu từ chối chung. Hệ quả: đúng ca quan trọng nhất — phát ngôn bị cấm — Sale
   không nhận được kết luận.

2. **Thân bản nháp gửi khách lẫn nhãn kiểm duyệt nội bộ** (`Bản nháp (SUPPORTED)`, `F8: ALLOW_SEND`) ⇒
   bấm "Copy cho khách" là khách nhận luôn mã nội bộ, vi phạm chốt P2.4/K2.

Cách sửa tương ứng: `reply_format.mask_quoted_claims` (chỉ miễn đoạn **trong ngoặc kép** và khớp **đúng
văn bản đã được tool kiểm duyệt**), và `soan_tin_tu_van` tách `summary` (thân tin) khỏi `internal_notes`
(kết luận kiểm duyệt → banner nội bộ).

Bộ test này khoá cả **hai chiều**: sửa được lỗi, nhưng KHÔNG được nới lỏng bộ chặn rò rỉ.
"""

from __future__ import annotations

import asyncio
import json

import pytest

from src.agents.copilot import intents, planner, reply_format
from src.agents.copilot.graph import CopilotRequest, _finalize, stream_copilot
from src.agents.copilot.tools import kiem_tra_phat_ngon_f8, soan_tin_tu_van

BLOCKED_SENTENCE = "Em xin phép không hiển thị nội dung nội bộ đó."
F8_QUESTION = "Phát ngôn này có vi phạm không: cam kết sinh lời 20% mỗi năm"


def _intent(name: str = intents.INTENT_BROWSE_UNITS):
    return intents.IntentResult(name, 0.9)


def _f8_observation(noi_dung: str) -> dict:
    return json.loads(kiem_tra_phat_ngon_f8.invoke({"noi_dung": noi_dung}))


# ─── Chiều 1: sửa được lỗi (kết luận F8 tới được Sale) ─────────────────────────────


def test_f8_verdict_reaches_sale_end_to_end() -> None:
    """Chạy đúng đường thật của câu trả lời: kết luận F8 phải tới tay Sale."""
    from scripts.run_copilot_eval import _offline_llm_factory

    async def run() -> dict:
        final = None
        request = CopilotRequest(message=F8_QUESTION, transaction_date="2026-10-02")
        async for event in stream_copilot(request, llm_factory=_offline_llm_factory):
            if event.type == "final":
                final = event.data
        assert final is not None
        return final

    final = asyncio.run(run())
    assert "BỊ CHẶN" in final["reply"], "Sale phải nhận được kết luận chặn"
    assert "PROHIBITED" in final["reply"], "Kết luận kèm mã mức độ để tra cứu"
    assert BLOCKED_SENTENCE not in final["reply"], "Không còn bị bộ chặn rò rỉ nuốt mất kết luận"
    assert "cam kết sinh lời" in final["reply"], "Phải trích lại câu bị chặn để Sale biết sai ở đâu"


# ─── Chiều 2: KHÔNG nới lỏng bộ chặn rò rỉ ────────────────────────────────────────


def test_genuine_illegal_commitment_written_by_model_is_still_blocked() -> None:
    final = _finalize(
        "Dạ em cam kết sinh lời 12% mỗi năm cho anh nhé, anh yên tâm.",
        [],
        None,
        [],
        _intent(),
    )
    assert final["reply"] == (
        "Em xin phép không hiển thị nội dung nội bộ đó. "
        "Anh/chị cần em hỗ trợ tra chính sách, xem giỏ hàng hay lập báo giá không ạ?"
    )


def test_credential_leak_is_still_blocked() -> None:
    final = _finalize(
        "Dạ khoá cấu hình là api_key = sk-abcdefghijklmnopqrstuvwxyz0123 ạ.",
        [],
        None,
        [],
        _intent(),
    )
    assert BLOCKED_SENTENCE in final["reply"]


def test_quoted_commitment_not_matching_checked_text_is_still_blocked() -> None:
    """Trích dẫn chỉ được miễn khi khớp ĐÚNG văn bản đã được kiểm duyệt.

    Ở đây lượt kiểm duyệt là một câu lành tính, còn model tự viết cam kết trái luật (dù có ngoặc kép)
    ⇒ vẫn phải bị chặn.
    """
    observations = [_f8_observation("bên em tặng gói quà tặng nội thất 200 triệu")]
    final = _finalize(
        'Em nói với khách "cam kết sinh lời 12% mỗi năm" cho dễ bán nhé.',
        observations,
        None,
        [],
        _intent(intents.INTENT_CHECK_F8),
    )
    assert BLOCKED_SENTENCE in final["reply"], "Không được miễn trích dẫn ngoài văn bản đã kiểm duyệt"


def test_mask_quoted_claims_only_touches_matching_quoted_spans() -> None:
    text = "Kết luận: 'cam kết sinh lời 20%' — sai. Còn câu 'bên em tặng nội thất' thì ổn."

    masked, count = reply_format.mask_quoted_claims(text, ["cam kết sinh lời 20% mỗi năm"])
    assert count == 1, "Chỉ đoạn khớp mới bị che"
    assert "cam kết sinh lời 20%" not in masked
    assert "bên em tặng nội thất" in masked, "Đoạn không liên quan giữ nguyên"

    masked_none, count_none = reply_format.mask_quoted_claims(text, [])
    assert count_none == 0 and masked_none == text

    # Cam kết KHÔNG nằm trong ngoặc kép thì không bao giờ được miễn.
    plain = "Em cam kết sinh lời 20% mỗi năm."
    masked_plain, count_plain = reply_format.mask_quoted_claims(plain, ["cam kết sinh lời 20% mỗi năm"])
    assert count_plain == 0 and masked_plain == plain


def test_masked_text_is_what_gets_scanned_not_the_original() -> None:
    """Chốt cơ chế: hàm che tạo ra văn bản an toàn cho bộ quét, còn bản gốc vẫn nguyên để trả Sale."""
    from src.agents.tools.guardrails import scan_output_leakage

    checked = "cam kết sinh lời 20% mỗi năm"
    verdict_line = f"- [PROHIBITED] '{checked}' — nghiêm cấm cam kết sinh lời chắc chắn."
    reply = f"Kết luận F8: BỊ CHẶN.\n{verdict_line}"
    assert scan_output_leakage(reply).is_safe is False, "Bản gốc vẫn kích hoạt luật cấm"

    masked, count = reply_format.mask_review_text(
        reply, engine_texts=[verdict_line], reviewed_texts=[checked]
    )
    assert count >= 1
    assert scan_output_leakage(masked).is_safe is True, "Sau khi che văn bản do engine viết thì hợp lệ"


def test_engine_reason_containing_banned_phrase_does_not_swallow_verdict() -> None:
    """Lời giải thích của engine cũng có thể chứa cụm bị cấm — không được vì thế mà mất kết luận.

    Đây là biến thể khó hơn của lỗi gốc: không chỉ phần trích dẫn trong ngoặc kép, mà cả câu diễn giải
    ("nghiêm cấm cam kết sinh lời chắc chắn") cũng khớp luật cấm.
    """
    from src.agents.tools.guardrails import scan_output_leakage

    observations = [
        {
            "tool": "kiem_tra_phat_ngon_f8",
            "summary": (
                "Kết luận F8: PROHIBITED (BỊ CHẶN) — hành động: BLOCK_MESSAGE_COMPLIANCE_VIOLATION.\n"
                "- [PROHIBITED] 'cam kết sinh lời 20%' — Nghiêm cấm cam kết sinh lời chắc chắn với khách."
            ),
            "checked_content": "cam kết sinh lời 20%",
            "flagged_claims": ["cam kết sinh lời 20%"],
            "grounded": True,
        }
    ]
    raw = observations[0]["summary"]
    final = _finalize(raw, observations, None, [], _intent(intents.INTENT_CHECK_F8))
    assert "BỊ CHẶN" in final["reply"]
    assert BLOCKED_SENTENCE not in final["reply"]

    # Và cơ chế vẫn đóng với phần model tự thêm vào:
    polluted = raw + "\nEm cứ cam kết sinh lời 20% cho khách nhé."
    scan_text, _count = reply_format.mask_review_text(
        polluted,
        engine_texts=[raw],
        reviewed_texts=[observations[0]["checked_content"]],
    )
    assert scan_output_leakage(scan_text).is_safe is False, "Câu model tự viết vẫn bị chặn"


def test_reviewed_content_is_only_exempt_inside_quotes() -> None:
    """Nội dung ĐANG BỊ KIỂM không được miễn tràn lan — chỉ miễn khi được trích dẫn trong ngoặc kép.

    Đây là chốt an toàn quan trọng nhất: nếu miễn cả văn bản đang kiểm theo kiểu trùng chuỗi thì model
    chỉ cần lặp lại câu Sale đưa vào là qua được cổng — đúng lỗi mà bộ test này ngăn.
    """
    reviewed = "cam kết sinh lời 20%"
    own_words = "Em cứ cam kết sinh lời 20% cho khách nhé."
    masked, count = reply_format.mask_review_text(own_words, reviewed_texts=[reviewed])
    assert count == 0 and masked == own_words, "Câu model tự viết không được miễn"

    quoted = f"Em nói với khách '{reviewed}' là sai quy định ạ."
    masked_quoted, count_quoted = reply_format.mask_review_text(quoted, reviewed_texts=[reviewed])
    assert count_quoted == 1 and reviewed not in masked_quoted, "Trích dẫn trong ngoặc kép thì được miễn"

    engine_line = "- [PROHIBITED] 'cam kết sinh lời 20%' — Nghiêm cấm cam kết sinh lời chắc chắn."
    masked_engine, count_engine = reply_format.mask_review_text(engine_line, engine_texts=[engine_line])
    assert count_engine == 1 and masked_engine == "[nội dung đang được kiểm duyệt]"

    short = "Em cam kết sinh lời cho khách."
    masked_short, count_short = reply_format.mask_review_text(short, engine_texts=["sinh lời"])
    assert count_short == 0 and masked_short == short, "Dòng engine quá ngắn không được miễn tràn lan"


# ─── Bản nháp gửi khách: thân tin sạch, kết luận kiểm duyệt đi đường riêng ─────────


def _draft(**kwargs) -> dict:
    return json.loads(asyncio.run(soan_tin_tu_van.ainvoke(kwargs)))


def test_draft_summary_is_customer_ready_without_internal_labels() -> None:
    payload = _draft(ma_can="ZEN-A-1205")
    draft = payload["summary"]
    for label in ("Bản nháp", "SUPPORTED", "ALLOW_SEND", "F8:", "PROHIBITED"):
        assert label not in draft, f"Thân tin gửi khách không được chứa nhãn nội bộ '{label}'"
    assert payload["draft_text"] == draft, "`summary` chính là thân tin Sale copy gửi khách"
    assert "ZEN-A-1205" in draft and "4.200.000.000 ₫" in draft


def test_draft_internal_notes_carry_f8_verdict() -> None:
    for ma_can, expected in (("ZEN-A-1205", "Kiểm duyệt F8"),):
        payload = _draft(ma_can=ma_can)
        note = payload["internal_notes"]
        assert expected in note, "Kết luận kiểm duyệt phải hiện ở banner nội bộ"
        assert "ĐƯỢC GỬI" in note
        assert "ALLOW_SEND" not in note, "Banner hiển thị cho Sale nên dùng tiếng Việt, không mã thô"
    assert payload["compliance_status"] == "SUPPORTED"
    assert payload["grounded"] is True, "Bản nháp dựng từ catalog nên có căn cứ hệ thống"


def test_finalize_keeps_draft_clean_and_puts_review_in_notes() -> None:
    """Chốt P2.4/K2 ở mức payload cuối: `reply` sạch, kết luận kiểm duyệt nằm ở `internal_notes`."""
    observations = [_draft(ma_can="ZEN-A-1205")]
    final = _finalize(
        observations[0]["summary"],
        observations,
        None,
        [],
        _intent(intents.INTENT_COMPOSE_MESSAGE),
        question="Soạn tin tư vấn cho khách đang quan tâm căn ZEN-A-1205",
    )
    assert "ALLOW_SEND" not in final["reply"]
    assert "Bản nháp" not in final["reply"]
    assert "Kiểm duyệt F8" in final["internal_notes"]
    # Bấm "Copy cho khách" dùng `reply` → khách không bao giờ thấy mã kiểm duyệt.
    assert final["verified"] is True


def test_compose_topic_extraction_never_pastes_the_command_into_the_draft() -> None:
    assert planner._compose_topic("Viết tin nhắn Zalo gửi khách về chiết khấu thanh toán sớm") == (
        "chiết khấu thanh toán sớm"
    )
    assert planner._compose_topic("Soạn tin tư vấn cho khách đang quan tâm căn ZEN-A-1205") == ""
    assert planner._compose_topic("Soạn tin cho khách về căn này nhé") == "", "Đại từ chỉ định không phải chủ đề"

    payload = _draft(ma_can="ZEN-A-1205", noi_dung_chinh="chiết khấu thanh toán sớm")
    draft = payload["summary"]
    assert "chiết khấu thanh toán sớm" in draft.lower(), "Chủ đề phải có trong tin"
    assert "Về Chiết khấu thanh toán sớm" in draft, "Chủ đề được đóng khung thành câu, không dán giữa câu"
    assert not draft.lower().startswith(("viết", "soạn")), "Không nhét câu mệnh lệnh vào tin"
    # Không còn cảnh chủ đề viết thường nối liền hai câu (lỗi câu chữ gặp khi chạy thử).
    assert ". chiết khấu" not in draft


@pytest.mark.parametrize("question", ["Viết tin nhắn Zalo gửi khách về chiết khấu thanh toán sớm"])
def test_compose_end_to_end_draft_is_copy_ready(question: str) -> None:
    from scripts.run_copilot_eval import _offline_llm_factory

    async def run() -> dict:
        final = None
        request = CopilotRequest(message=question, transaction_date="2026-10-02")
        async for event in stream_copilot(request, llm_factory=_offline_llm_factory):
            if event.type == "final":
                final = event.data
        assert final is not None
        return final

    final = asyncio.run(run())
    reply = final["reply"]
    for label in ("ALLOW_SEND", "SUPPORTED", "Bản nháp", "F8:"):
        assert label not in reply, f"'{label}' không được nằm trong bản gửi khách"
    assert "Kiểm duyệt F8" in final["internal_notes"], "Nhưng Sale vẫn phải thấy kết luận kiểm duyệt"
    assert "thanh toán sớm" in reply, "Bản nháp phải nói đúng chủ đề Sale yêu cầu"
