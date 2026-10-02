"""Test lớp chuẩn hoá câu trả lời (P1.5b hình thức · P2.5 chống lộ tên nội bộ).

Ca test quan trọng nhất dùng **đúng câu trả lời thật** người dùng gửi (bảng dính câu văn +
`gia_toi_da_vnd = 0`) để bảo đảm lỗi không tái phát.
"""

from __future__ import annotations

from src.agents.copilot import reply_format

BROKEN_REPLY = (
    "Em đã lọc giỏ hàng The Zen Park với điều kiện **giá trên** 3 tỷ **(số anh/chị nhập)** "
    "(gia_toi_da_vnd = 0, tức không giới hạn trần, sau đó em loại căn dưới 3 tỷ): hiện có **3 căn** "
    "đáp ứng. | Mã căn | Phòng ngủ | Diện tích | Giá niêm yết (trước thuế) | |---|---|---|---| "
    "| **ZEN-B-0803** | 3PN | 98.0 m² | **3.800.000.000 ₫** | | **ZEN-C-1501** | 3PN | 105.5 m² "
    "| **4.200.000.000 ₫** | | **ZEN-D-2202** | 4PN | 128.0 m² | **6.100.000.000 ₫** | "
    "➡️ Tổng cộng giỏ hàng The Zen Park có **4 căn**, trong đó **1 căn dưới** 3 tỷ** **(ZEN-A-1205, "
    "2PN) và** 3 căn trên **3 tỷ như bảng trên."
)


# ─── P1.5b — bảng không được dính câu văn ─────────────────────────────────────────


def test_glued_table_is_split_into_own_lines() -> None:
    out = reply_format.normalize_markdown(BROKEN_REPLY)
    lines = out.split("\n")
    table_lines = [line for line in lines if line.startswith("|")]
    assert table_lines[0] == "| Mã căn | Phòng ngủ | Diện tích | Giá niêm yết (trước thuế) |"
    assert table_lines[1] == "| --- | --- | --- | --- |"
    assert len(table_lines) == 5, "tiêu đề + phân cách + 3 dòng dữ liệu"
    # Không còn dòng nào vừa có chữ vừa có ô bảng.
    assert not any("|" in line and not line.startswith("|") for line in lines)


def test_glued_table_keeps_before_and_after_text_on_their_own_lines() -> None:
    out = reply_format.normalize_markdown(BROKEN_REPLY)
    paragraphs = [line for line in out.split("\n") if line and not line.startswith("|")]
    assert any(line.startswith("Em đã lọc giỏ hàng The Zen Park") for line in paragraphs)
    assert any("Tổng cộng giỏ hàng The Zen Park có" in line for line in paragraphs)


def test_blank_line_before_and_after_table() -> None:
    out = reply_format.normalize_markdown(BROKEN_REPLY)
    lines = out.split("\n")
    first = next(i for i, line in enumerate(lines) if line.startswith("|"))
    last = max(i for i, line in enumerate(lines) if line.startswith("|"))
    assert lines[first - 1] == ""
    assert lines[last + 1] == ""


def test_table_cells_are_cleaned_and_aligned() -> None:
    out = reply_format.normalize_markdown(BROKEN_REPLY)
    row = next(line for line in out.split("\n") if line.startswith("| ZEN-B-0803"))
    assert row == "| ZEN-B-0803 | 3PN | 98.0 m² | 3.800.000.000 ₫ |", "ô bảng bỏ đậm, canh lại khoảng trắng"


def test_arrow_becomes_bullet_and_broken_bold_is_removed() -> None:
    out = reply_format.normalize_markdown(BROKEN_REPLY)
    assert "➡️" not in out
    assert not any(line.strip().startswith("- -") for line in out.split("\n"))
    # Dòng đậm mở nửa câu: không còn dấu ** lẻ làm rác văn bản.
    tail = [line for line in out.split("\n") if "Tổng cộng giỏ hàng The Zen Park có" in line][0]
    assert tail.count("**") % 2 == 0
    assert "3 tỷ (ZEN-A-1205" in tail, "cặp đậm rỗng không được làm hai chữ dính vào nhau"


def test_normalize_is_idempotent() -> None:
    once = reply_format.normalize_markdown(BROKEN_REPLY)
    twice = reply_format.normalize_markdown(once)
    assert once == twice, "áp lại phải cho cùng kết quả (dùng được cho dữ liệu cũ)"


def test_properly_formatted_table_is_untouched() -> None:
    good = (
        "4 căn phù hợp tiêu chí trong toàn giỏ đang mở bán (giá chưa gồm VAT):\n\n"
        "| Mã căn | Phòng ngủ | Diện tích | Giá niêm yết (trước thuế) |\n"
        "| --- | --- | --- | --- |\n"
        "| ZEN-A-0803 | 1PN | 52.0 m² | 2.500.000.000 ₫ |\n"
    )
    assert reply_format.normalize_markdown(good).strip() == good.strip()


def test_header_glued_but_divider_on_next_line() -> None:
    broken = "Có 2 căn phù hợp: | Mã căn | Giá |\n|---|---|\n| A | 2 tỷ |\n| B | 3 tỷ |"
    out = reply_format.normalize_markdown(broken)
    lines = out.split("\n")
    assert lines[0] == "Có 2 căn phù hợp:"
    assert lines[2] == "| Mã căn | Giá |"
    assert lines[3] == "| --- | --- |"


# ─── P2.5 — không lộ tên nội bộ ───────────────────────────────────────────────────


def test_internal_parameter_parenthesis_is_removed() -> None:
    cleaned, found = reply_format.strip_internal_names(BROKEN_REPLY)
    assert "gia_toi_da_vnd" not in cleaned
    assert "= 0" not in cleaned
    assert "gia_toi_da_vnd" in found


def test_tool_name_becomes_business_wording() -> None:
    cleaned, found = reply_format.strip_internal_names(
        "Em gọi tool tinh_phuong_an_thanh_toan để lấy bảng dòng tiền."
    )
    assert "tinh_phuong_an_thanh_toan" not in cleaned
    assert "phương án thanh toán chi tiết" in cleaned
    assert "tinh_phuong_an_thanh_toan" in found


def test_bare_snake_case_token_is_dropped() -> None:
    cleaned, _ = reply_format.strip_internal_names("Em lọc theo so_phong_ngu rồi trả kết quả.")
    assert "so_phong_ngu" not in cleaned
    assert "Em lọc theo" in cleaned and "rồi trả kết quả." in cleaned


def test_clean_reply_is_untouched() -> None:
    text = "Phân khúc **3PN** hiện có 1 căn, giá mềm nhất 6,1 tỷ."
    cleaned, found = reply_format.strip_internal_names(text)
    assert cleaned == text
    assert found == []


def test_normalize_does_not_touch_accents_or_money() -> None:
    text = "Vốn tự có tối thiểu 31.8% ≈ 2.171.600.000 ₫ (đã gồm VAT và phí bảo trì)."
    assert reply_format.normalize_markdown(text) == text


# ─── Tích hợp: `_finalize` áp cả hai lớp (đúng đường đi thật của câu trả lời) ─────


def test_finalize_applies_format_and_scrubs_internal_names() -> None:
    import json

    from src.agents.copilot import intents
    from src.agents.copilot.graph import _finalize
    from src.agents.copilot.tools import tra_cuu_gio_hang

    observations = [json.loads(tra_cuu_gio_hang.invoke({"du_an": "The Zen Park"}))]
    final = _finalize(
        BROKEN_REPLY,
        observations,
        None,
        [],
        intents.IntentResult(intents.INTENT_BROWSE_UNITS, 0.9),
        question="Có căn 3 ngủ nào trên 3 tỷ không?",
    )

    reply = final["reply"]
    assert "gia_toi_da_vnd" not in reply, "P2.5: tên tham số không được ra tới người dùng"
    assert "➡️" not in reply
    lines = reply.split("\n")
    assert not any("|" in line and not line.startswith("|") for line in lines), "bảng phải nằm riêng dòng"
    assert len([line for line in lines if line.startswith("|")]) == 5
    # Số bịa trong ví dụ vẫn bị verifier bắt (ghi chú nội bộ), không im lặng cho qua.
    assert "chưa đối chiếu" in final["internal_notes"]
