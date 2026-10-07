"""P0 — câu trả lời rõ ràng: không còn cảnh báo xếp chồng, không báo động giả.

Khoá lại đúng ca người dùng nêu: "Khách hàng có 2 tỷ, cần mua căn 3 ngủ".

Trước P0, câu trả lời đó bị 3 dòng cảnh báo xếp chồng dù nội dung không sai:
1. verifier: "có số liệu chưa đối chiếu được (2 tỷ, 2,5 tỷ, 6,1 tỷ)" — trong đó "2 tỷ" là số **Sale tự nêu**;
2. `grounded=False` → "câu trả lời này chưa đối chiếu được với dữ liệu chính sách/giỏ hàng" — trong khi
   tool tra giỏ hàng đã chạy thành công và kết luận "0 căn khớp" chính là dữ liệu;
3. critic: "Gắn mỏ neo [n] cho từng con số" — lượt này không có citation nào để gắn ⇒ lời nhắc vô nghĩa.
"""

from __future__ import annotations

import json
from typing import Any

import pytest

from src.agents.copilot import critic, intents, verifier
from src.agents.copilot.graph import _finalize
from src.agents.copilot.tools import tra_cuu_gio_hang

QUESTION = "Khách hàng có 2 tỷ, cần mua căn 3 ngủ"


def _empty_basket_observations() -> list[dict[str, Any]]:
    """Observation thật khi lọc 3PN ≤ 2 tỷ: tool chạy OK nhưng không có căn nào khớp."""
    return [json.loads(tra_cuu_gio_hang.invoke({"so_phong_ngu": 3, "gia_toi_da_vnd": 2_000_000_000}))]


def _intent(name: str = intents.INTENT_BROWSE_UNITS):
    return intents.IntentResult(name, 0.9)


# ─── P0.1: `grounded` không còn báo động giả khi tool chạy đúng mà trả rỗng ─────────


def test_lookup_that_runs_ok_is_grounded_even_when_no_citation() -> None:
    final = _finalize(
        "Không còn căn nào phù hợp tiêu chí trong giỏ hàng đang mở bán.",
        _empty_basket_observations(),
        None,
        [],
        _intent(),
        question=QUESTION,
    )
    assert final["grounded"] is True, "Tra giỏ hàng chạy thành công thì câu trả lời có căn cứ"
    assert "chưa đối chiếu" not in final["reply"]


def test_non_lookup_tool_does_not_claim_grounded() -> None:
    """Soạn tin / kiểm F8 / hồ sơ khách **không** thuộc phạm vi 'dữ liệu chính sách/giỏ hàng'."""
    observations = [{"tool": "soan_tin_tu_van", "summary": "Bản thảo tin nhắn…", "citations": []}]
    final = _finalize("Bản thảo tin nhắn gửi khách.", observations, None, [], _intent(intents.INTENT_COMPOSE_MESSAGE))
    assert final["grounded"] is False


def test_failed_lookup_is_not_grounded() -> None:
    observations = [{"tool": "tra_cuu_gio_hang", "summary": "Tool lỗi", "error": True, "citations": []}]
    final = _finalize("Em chưa tra được dữ liệu.", observations, None, [], _intent())
    assert final["grounded"] is False


# ─── P0.2: số do Sale nêu trong câu hỏi không bị coi là bịa ─────────────────────────


def test_verifier_excuses_numbers_stated_in_question() -> None:
    observations = [{"tool": "tra_cuu_gio_hang", "summary": "Căn ZEN-B-1502 giá 6.100.000.000 ₫", "citations": []}]
    result = verifier.verify_reply(
        "Với ngân sách 2 tỷ, căn 3 ngủ hiện có giá 6,1 tỷ.",
        observations,
        question=QUESTION,
    )
    assert result.verified is True
    assert result.unsupported == []
    assert "2 tỷ" in result.echoed, "Số của Sale phải được ghi nhận là số nhắc lại, không phải bịa"


def test_verifier_still_catches_number_nobody_said() -> None:
    observations = [{"tool": "tra_cuu_gio_hang", "summary": "Căn ZEN-B-1502 giá 6.100.000.000 ₫", "citations": []}]
    result = verifier.verify_reply("Căn này chỉ 3,5 tỷ thôi ạ.", observations, question=QUESTION)
    assert result.verified is False
    assert "3,5 tỷ" in result.unsupported


def test_verifier_without_question_keeps_old_strictness() -> None:
    observations = [{"tool": "tra_cuu_gio_hang", "summary": "Căn ZEN-A-1205", "citations": []}]
    assert verifier.verify_reply("Ngân sách 2 tỷ là vừa.", observations).verified is False


# ─── P0.3: critic chỉ nhắc mỏ neo khi có chứng cứ để gắn ────────────────────────────


def test_critic_does_not_demand_anchor_without_evidence() -> None:
    result = critic.critique_reply(
        "Với ngân sách 2 tỷ, chưa có căn 3 ngủ nào phù hợp.",
        observations=_empty_basket_observations(),
    )
    assert all(i["code"] != "MONEY_WITHOUT_ANCHOR" for i in result.issues)


def test_critic_still_demands_anchor_when_evidence_exists() -> None:
    result = critic.critique_reply(
        "Căn ZEN-A-1205 giá 4,2 tỷ.",
        observations=[{"tool": "tra_cuu_gio_hang", "citations": [{"policy_id": "CATALOG-UNITS"}]}],
    )
    assert result.ok is False
    assert any(i["code"] == "MONEY_WITHOUT_ANCHOR" for i in result.issues)


def test_critic_direct_call_default_keeps_strict_rule() -> None:
    """Gọi như hàm thuần (không truyền observation) giữ nguyên luật chặt — tương thích ngược."""
    assert critic.critique_reply("Căn này giá 4,2 tỷ.").ok is False


# ─── P0.4: tối đa MỘT khối ghi chú, và không nhét ghi chú kiểm duyệt vào nội dung ──


def test_finalize_keeps_reply_clean_and_packs_notes_into_one_field() -> None:
    """Chốt P2.4: `reply` sạch (Sale copy gửi khách được), mọi cảnh báo dồn vào `internal_notes`."""
    # Tool soạn tin: không thuộc nhóm tra cứu chính sách/giỏ hàng ⇒ chưa grounded;
    # cộng thêm số "9,9 tỷ" không có nguồn ⇒ cả hai điều kiện cảnh báo cùng đúng.
    observations = [{"tool": "soan_tin_tu_van", "summary": "Bản thảo tin nhắn", "citations": []}]
    final = _finalize(
        "Căn này khoảng 9,9 tỷ và chưa đối chiếu.",
        observations,
        None,
        [],
        _intent(intents.INTENT_COMPOSE_MESSAGE),
        question=QUESTION,
    )
    reply = final["reply"]
    notes = final["internal_notes"]
    assert reply == "Căn này khoảng 9,9 tỷ và chưa đối chiếu.", "Nội dung trả lời phải sạch"
    assert "Ghi chú nội bộ" not in reply and "_Lưu ý" not in reply
    # Hai cảnh báo khác nhau gộp trong CÙNG một trường, không rải thành nhiều dòng trong câu trả lời.
    assert "có số liệu chưa đối chiếu được" in notes
    assert "chưa đối chiếu với dữ liệu chính sách/giỏ hàng" in notes


def test_critic_note_not_written_into_reply_body() -> None:
    """Ghi chú kiểm duyệt là dữ liệu có cấu trúc (`critique`/`internal_notes`), không nằm trong nội dung."""
    observations = [{"tool": "tra_cuu_gio_hang", "citations": [{"policy_id": "CATALOG-UNITS"}]}]
    final = _finalize(
        "Anh yên tâm, em cam kết ngân hàng sẽ duyệt vay cho căn này.",
        observations,
        None,
        [],
        _intent(intents.INTENT_COMPOSE_MESSAGE),
        question="tư vấn căn ZEN-A-1205",
    )
    assert "Kiểm duyệt nội bộ" not in final["reply"]
    assert final["critique"]["ok"] is False, "Vẫn phải giữ cảnh báo ở trường có cấu trúc cho UI"
    assert final["critique"]["issues"]
    # Lời nhắc của critic nằm ở trường `critique` (UI gộp hiển thị cùng internal_notes trong MỘT
    # banner) — không nhân đôi vào `internal_notes` để tránh hiện hai lần.
    assert final["critique"]["hints"]


def test_clean_answer_has_no_note_at_all() -> None:
    final = _finalize(
        "Căn ZEN-A-1205 (2PN) giá niêm yết 4.200.000.000 ₫ [CATALOG-UNITS · Căn ZEN-A-1205].",
        [{"tool": "tra_cuu_gio_hang", "summary": "Căn ZEN-A-1205 4.200.000.000 ₫", "citations": [{"policy_id": "CATALOG-UNITS"}]}],
        None,
        [],
        _intent(),
        question="cho anh thông tin căn ZEN-A-1205",
    )
    assert "Ghi chú nội bộ" not in final["reply"]
    assert final["internal_notes"] == ""
    assert final["verified"] is True
    assert final["grounded"] is True


@pytest.mark.parametrize("intent_name", [intents.INTENT_SMALL_TALK])
def test_small_talk_stays_quiet(intent_name: str) -> None:
    final = _finalize("Dạ em chào anh/chị ạ.", [], None, [], _intent(intent_name))
    assert final["grounded"] is True
    assert "Ghi chú nội bộ" not in final["reply"]


# ─── P0.2b: số liệu canonical trong bối cảnh là nguồn hệ thống, không bị gắn cờ oan ──


def test_verifier_accepts_numbers_from_canonical_context() -> None:
    """Đúng ví dụ người dùng: "2,5 tỷ … 6,1 tỷ" là dải giá **canonical của giỏ hàng**.

    Trước P0, câu trả lời bị gắn cờ "có số liệu chưa đối chiếu được" chỉ vì hai con số đó đến từ
    bối cảnh hệ thống thay vì từ Observation của tool.
    """
    from src.agents.copilot import prompts

    reference = "\n".join(prompts.canonical_facts({"transaction_date": "2026-10-02"}))
    result = verifier.verify_reply(
        "Với ngân sách 2 tỷ, chưa có căn 3 ngủ nào khớp. Giỏ đang mở bán có 4 căn, "
        "giá niêm yết từ 2,5 tỷ đến 6,1 tỷ (chưa thuế).",
        _empty_basket_observations(),
        question=QUESTION,
        context=reference,
    )
    assert result.verified is True, result.unsupported
    assert "2,5 tỷ" in result.from_context and "6,1 tỷ" in result.from_context
    assert "2 tỷ" in result.echoed


def test_verifier_rejects_numbers_from_feedback_hints() -> None:
    """Gợi ý học từ phản hồi (`avoid_examples`) do LLM tổng hợp — KHÔNG được coi là nguồn số liệu."""
    from src.agents.copilot import prompts

    context = {"transaction_date": "2026-10-02"}
    assert "avoid_examples" not in "".join(prompts.canonical_facts(context))
    result = verifier.verify_reply(
        "Căn này chỉ 7,7 tỷ.",
        _empty_basket_observations(),
        context="\n".join(prompts.canonical_facts(context)),
    )
    assert result.verified is False
    assert "7,7 tỷ" in result.unsupported


def test_policy_id_from_context_is_not_flagged() -> None:
    from src.agents.copilot import prompts

    reference = "\n".join(prompts.canonical_facts({"transaction_date": "2026-10-02"}))
    result = verifier.verify_reply(
        "Theo CSBH-ZEN-2026-V3.1, chiết khấu thanh toán sớm đang áp dụng.",
        _empty_basket_observations(),
        context=reference,
    )
    assert result.verified is True
    assert "CSBH-ZEN-2026-V3.1" in result.from_context


# ─── P2.1 · P2.3 · P1.6: mỏ neo máy chèn, ghi chú tách riêng, mốc thời gian ─────────


def test_finalize_attaches_machine_inserted_anchors() -> None:
    observations = [
        {
            "tool": "tra_cuu_gio_hang",
            "summary": "Không có căn nào khớp. Căn 3PN mềm nhất là ZEN-B-1502 giá 6.100.000.000 ₫.",
            "citations": [
                {
                    "policy_id": "CATALOG-UNITS",
                    "section": "Căn ZEN-B-1502",
                    "quote": "3PN · 98.2m² · 6.100.000.000 ₫ · AVAILABLE",
                }
            ],
            "data_as_of": "2026-10-02T13:29:19+00:00",
        }
    ]
    final = _finalize(
        "Với ngân sách 2 tỷ[9], căn 3 ngủ mềm nhất là 6,1 tỷ.",
        observations,
        None,
        [],
        _intent(),
        question=QUESTION,
    )
    # LLM gõ [9] sai → máy gỡ và đánh lại.
    assert "[9]" not in final["reply"]
    assert final["reply"].startswith("Với ngân sách **2 tỷ** (ngân sách anh/chị nhập),")
    assert "6,1 tỷ[1]" in final["reply"]
    assert final["anchors"] == [
        {"index": 1, "value": "6,1 tỷ", "citation_index": 0, "label": "CATALOG-UNITS · Căn ZEN-B-1502"}
    ]
    assert final["labeled_inputs"] == ["2 tỷ"]
    assert final["data_as_of"] == "2026-10-02T13:29:19+00:00"
    assert final["internal_notes"] == "", "Mọi con số đều có nguồn → không còn ghi chú rỗng"


def test_finalize_notes_survive_outside_reply() -> None:
    observations = [{"tool": "tra_cuu_gio_hang", "summary": "Không có căn nào khớp.", "citations": []}]
    final = _finalize(
        "Căn này khoảng 9,9 tỷ.",
        observations,
        None,
        [],
        _intent(),
        question=QUESTION,
    )
    assert "9,9 tỷ" in final["reply"], "Nội dung vẫn giữ nguyên"
    assert "_Ghi chú" not in final["reply"] and "Lưu ý" not in final["reply"]
    assert "9,9 tỷ" in final["internal_notes"], "Cảnh báo nêu đích danh con số, ở trường riêng"
