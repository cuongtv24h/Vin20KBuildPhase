"""Lệnh gạch chéo không được rò vào câu trả lời Copilot.

Bối cảnh lỗi thật: Sale gõ `/chinh-sach` → chuỗi thô đi vào LLM → model nhắc lại lệnh trong câu
trả lời ("Anh/chị gõ /chinh-sach để tra cứu"), làm sai nội dung. Test khoá cả hai đầu:
chuẩn hoá input và dọn output, đồng thời **không** được ăn nhầm "Anh/chị" hay "/api/v1".
"""

from __future__ import annotations

from src.agents.copilot import commands


class TestNormalizeUserMessage:
    def test_dich_lenh_thanh_cau_tu_nhien(self) -> None:
        assert commands.normalize_user_message("/chinh-sach") == "Tra cứu chính sách đang hiệu lực"
        assert commands.normalize_user_message("/tinh-lai") == "Lập báo giá mới theo chính sách đang hiệu lực"

    def test_giu_phan_tham_so_sau_lenh(self) -> None:
        assert commands.normalize_user_message("/tim-khach Nguyễn Văn An") == "Tìm khách hàng Nguyễn Văn An"
        assert (
            commands.normalize_user_message("/baogia căn ZEN-A-1205") == "Xem pipeline báo giá căn ZEN-A-1205"
        )

    def test_lenh_tro_khong_gui_chuoi_tho_cho_llm(self) -> None:
        out = commands.normalize_user_message("/ch")
        assert not out.startswith("/")
        assert out == "ch"

    def test_cau_tu_nhien_khong_bi_doi(self) -> None:
        assert commands.normalize_user_message("chinh sach chiet khau con hieu luc?") == "chinh sach chiet khau con hieu luc?"

    def test_lich_su_cu_cung_duoc_chuan_hoa(self) -> None:
        history = [{"role": "user", "content": "/chinh-sach"}, {"role": "assistant", "content": "Dạ…"}]
        out = commands.sanitize_history(history)
        assert out[0]["content"] == "Tra cứu chính sách đang hiệu lực"
        assert out[1]["content"] == "Dạ…"


class TestStripCommandMentions:
    def test_bo_cau_chi_dan_cach_bam_lenh(self) -> None:
        text = "Dạ em hỗ trợ được. Anh/chị gõ /chinh-sach để tra cứu nhé."
        assert commands.strip_command_mentions(text) == "Dạ em hỗ trợ được."

    def test_bo_lenh_long_trong_ngoac_nhung_giu_noi_dung(self) -> None:
        text = "Chính sách EARLY_PAY giảm 8% (xem thêm /chinh-sach)."
        assert commands.strip_command_mentions(text) == "Chính sách EARLY_PAY giảm 8%."

    def test_khong_an_nham_anh_chi_va_duong_dan(self) -> None:
        text = "Anh/chị kiểm tra giúp em. Tốc độ 60km/h, log ở /api/v1/quotes."
        assert commands.strip_command_mentions(text) == text

    def test_cau_tra_loi_sach_thi_giu_nguyen(self) -> None:
        text = "Căn R-02.02 còn hàng, giá 4.600.000.000 VNĐ."
        assert commands.strip_command_mentions(text) == text

    def test_chi_con_lenh_thi_tra_ve_rong(self) -> None:
        assert commands.strip_command_mentions("Anh/chị gõ /chinh-sach nhé.") == ""


def test_moi_lenh_trong_ui_deu_co_ban_dich() -> None:
    """Danh mục lệnh ở FE và bảng dịch ở backend phải khớp tên — lệch là lệnh sẽ lọt qua."""
    ui_commands = {
        "/tao-khach",
        "/tim-khach",
        "/khach-hang",
        "/baogia",
        "/soan-tin",
        "/chinh-sach",
        "/tinh-lai",
        "/gio-hang",
    }
    assert ui_commands == set(commands.SLASH_COMMAND_MAP)
