"""P2 — mỏ neo `[n]` do máy chèn (Trust Engine), và nhãn riêng cho số của Sale.

Bốn luật được khoá ở đây:
1. `[n]` do **máy** chèn, khớp con số với citation theo **giá trị số học** (`6,1 tỷ` ↔ `6.100.000.000 ₫`).
2. Mỏ neo LLM tự gõ bị **gỡ và đánh lại** — mô hình hay đánh sai số thứ tự.
3. Số **của Sale** (có trong câu hỏi) **không** gắn mỏ neo, chỉ in đậm + nhãn.
4. Con số không có nguồn **không** bị gắn mỏ neo (để tầng cảnh báo nội bộ nói ra).
"""

from __future__ import annotations

from src.agents.copilot import anchors

CATALOG = {
    "policy_id": "CATALOG-UNITS",
    "section": "Căn ZEN-B-1502",
    "quote": "3PN · 96m² · 6.100.000.000 ₫ · AVAILABLE",
    "source": "CANONICAL_CATALOG",
}
POLICY = {
    "policy_id": "CSBH-ZEN-2026-V3.1",
    "section": "Điều 4, Khoản 2b",
    "quote": "Chiết khấu 8.0% cho khách thanh toán sớm 95% trong 15 ngày.",
    "clause_id": "Điều 4",
}


def test_anchor_inserted_for_number_from_citation() -> None:
    result = anchors.annotate_reply("Căn 3 ngủ giá 6,1 tỷ.", [CATALOG])
    assert result.text == "Căn 3 ngủ giá 6,1 tỷ[1]."
    assert [a.index for a in result.anchors] == [1]
    assert result.anchors[0].citation_index == 0
    assert result.anchors[0].label == "CATALOG-UNITS · Căn ZEN-B-1502"


def test_percent_anchor_and_reuse_for_same_value() -> None:
    reply = "Chiết khấu 8% khi thanh toán sớm, và 8% là mức tốt."
    result = anchors.annotate_reply(reply, [POLICY])
    assert result.text.count("[1]") == 2, "Cùng con số + cùng nguồn phải dùng lại một mỏ neo"
    assert len(result.anchors) == 1


def test_two_numbers_get_two_anchors_in_order() -> None:
    reply = "Giỏ có căn 6,1 tỷ, chiết khấu 8%."
    result = anchors.annotate_reply(reply, [CATALOG, POLICY])
    assert result.text == "Giỏ có căn 6,1 tỷ[1], chiết khấu 8%[2]."
    assert [a.index for a in result.anchors] == [1, 2]
    assert [a.citation_index for a in result.anchors] == [0, 1]


def test_llm_written_anchors_are_replaced() -> None:
    """Mô hình đánh sai số thứ tự → máy gỡ hết và đánh lại."""
    result = anchors.annotate_reply("Căn này 6,1 tỷ[9] và chiết khấu 8%[7].", [CATALOG, POLICY])
    assert "[9]" not in result.text and "[7]" not in result.text
    assert result.text == "Căn này 6,1 tỷ[1] và chiết khấu 8%[2]."


def test_sale_number_is_not_anchored_but_labelled() -> None:
    result = anchors.annotate_reply(
        "Với ngân sách 2 tỷ, chưa có căn 3 ngủ nào khớp.",
        [CATALOG],
        question="Khách hàng có 2 tỷ, cần mua căn 3 ngủ",
    )
    assert "[1]" not in result.text, "Số của Sale không được gắn mỏ neo"
    assert "**2 tỷ** (ngân sách anh/chị nhập)" in result.text
    assert result.labeled_inputs == ["2 tỷ"]
    assert result.anchors == []


def test_sale_number_labelled_once_only() -> None:
    result = anchors.annotate_reply(
        "Ngân sách 2 tỷ chưa đủ; nếu vẫn giữ 2 tỷ thì cần vay thêm.",
        [],
        question="khách có 2 tỷ",
    )
    assert result.text.count("(ngân sách anh/chị nhập)") == 1
    assert result.text.count("**2 tỷ**") == 2, "Lần thứ hai vẫn in đậm nhưng không lặp nhãn"


def test_non_budget_number_gets_generic_label() -> None:
    result = anchors.annotate_reply("Khách muốn 3 ngủ và 2 tỷ.", [], question="khách có 2 tỷ và 3 ngủ")
    assert "(số anh/chị nhập)" in result.text


def test_number_without_source_is_left_alone() -> None:
    result = anchors.annotate_reply("Con số 9,9 tỷ không có trong hệ thống.", [CATALOG])
    assert "[1]" not in result.text
    assert result.anchors == []


def test_policy_code_in_reply_is_anchored() -> None:
    result = anchors.annotate_reply("Theo CSBH-ZEN-2026-V3.1 thì được chiết khấu.", [POLICY])
    assert "CSBH-ZEN-2026-V3.1[1]" in result.text


def test_existing_bold_number_is_not_double_bolded() -> None:
    result = anchors.annotate_reply("Ngân sách **2 tỷ** là mức hiện tại.", [], question="khách có 2 tỷ")
    assert "****" not in result.text
    assert "**2 tỷ** (ngân sách anh/chị nhập)" in result.text


def test_annotation_is_idempotent_for_anchor_count() -> None:
    first = anchors.annotate_reply("Căn 6,1 tỷ, chiết khấu 8%.", [CATALOG, POLICY], question="có 2 tỷ")
    second = anchors.annotate_reply(first.text, [CATALOG, POLICY], question="có 2 tỷ")
    assert second.text == first.text
    assert [a.index for a in second.anchors] == [1, 2]


def test_payload_shape_for_ui() -> None:
    result = anchors.annotate_reply("Căn 6,1 tỷ.", [CATALOG])
    payload = result.as_dict()
    assert payload["anchors"] == [
        {"index": 1, "value": "6,1 tỷ", "citation_index": 0, "label": "CATALOG-UNITS · Căn ZEN-B-1502"}
    ]
