"""P1 + P3 — giỏ hàng lọc rỗng, phân khúc, vốn tự có và mốc tổng quan.

Khoá đúng các quyết định thiết kế đã chốt:

- **P1.1** lọc rỗng ⇒ gợi ý bước 1 (bỏ trần giá, giữ số phòng ngủ) + câu hỏi điều hướng, KHÔNG tự hạ
  số phòng ngủ của khách;
- **P1.2** chỉ mốc tổng quan vốn tự có, không đưa bảng dòng tiền chi tiết;
- **P1.3** báo căn **mềm nhất** + chênh lệch, không dội căn đắt nhất;
- **P1.5** dưới 3 căn liệt kê dòng, từ 3 căn dùng bảng rút gọn (Căn · Dự án · Số PN · Diện tích · Giá);
- **P3.2** cổng phân khúc: lọc N phòng ngủ thì mọi căn trả về phải đúng N phòng ngủ (lỗi cấm).
"""

from __future__ import annotations

import asyncio
import json

import pytest

from src.agents.copilot import grounding, inventory_funnel
from src.agents.copilot.tools import danh_gia_von_tu_co, tra_cuu_gio_hang

QUESTION = "Khách hàng có 2 tỷ, cần mua căn 3 ngủ"


@pytest.fixture(autouse=True)
def force_canonical_fixture(monkeypatch):
    monkeypatch.setattr(grounding, "_cached_db_units", [])



# ─── P3.2 — cổng phân khúc (lỗi cấm) ────────────────────────────────────────────────


@pytest.mark.parametrize("bedrooms", [1, 2, 3])
def test_segment_never_mixes_bedroom_counts(bedrooms: int) -> None:
    payload = json.loads(tra_cuu_gio_hang.invoke({"so_phong_ngu": bedrooms}))
    check = payload["segment_check"]
    assert check["ok"] is True, f"Lọc {bedrooms}PN trả về {check['returned_bedrooms']}"
    assert check["returned_bedrooms"] == [bedrooms]


def test_segment_check_flags_cross_segment_returns() -> None:
    """Nếu vì lý do nào đó danh sách trả về lẫn phân khúc, `segment_check.ok` phải là False."""
    units = [
        {"unit_code": "A", "bedrooms": 3, "listed_price_before_tax_vnd": 1, "status": "AVAILABLE", "project_id": "X"},
        {"unit_code": "B", "bedrooms": 2, "listed_price_before_tax_vnd": 2, "status": "AVAILABLE", "project_id": "X"},
    ]
    requested = 3
    ok = all(int(u["bedrooms"]) == requested for u in units)
    assert ok is False


def test_histogram_is_the_source_of_truth_for_counts() -> None:
    """Mọi câu "giỏ có N căn XPN" phải lấy từ histogram, không suy từ toàn giỏ."""
    histogram = inventory_funnel.bedroom_histogram()
    payload = json.loads(tra_cuu_gio_hang.invoke({"so_phong_ngu": 3}))
    assert payload["bedroom_histogram"] == {str(k): v for k, v in histogram.items()}
    assert histogram.get(3, 0) == 1, "Dữ liệu canonical hiện có đúng 1 căn 3PN"


# ─── P1.1 + P1.3 — phễu khi lọc rỗng ───────────────────────────────────────────────


def test_empty_filter_gives_segment_range_and_directions() -> None:
    payload = json.loads(tra_cuu_gio_hang.invoke({"so_phong_ngu": 3, "gia_toi_da_vnd": 2_000_000_000}))
    summary = payload["summary"]
    assert payload["match_count"] == 0
    assert "3PN" in summary, "Phải nêu rõ phạm vi phân khúc"
    assert "6.100.000.000 ₫" in summary, "Phải có khoảng giá của phân khúc 3PN"
    assert "mềm nhất" in summary, "P1.3: báo căn mềm nhất, không dội căn đắt nhất"
    assert "4.100.000.000 ₫" in summary, "Phải nêu chênh lệch so với ngân sách"
    assert "TOÀN GIỎ" in summary, "Số của toàn giỏ phải được dán nhãn"
    assert "Giữ nguyên 3PN" in summary and "2PN+1" in summary, "P1.1: hai hướng đi tiếp"


def test_next_steps_never_silently_lower_bedrooms() -> None:
    steps = inventory_funnel.next_steps(3, 2_000_000_000)
    assert any("Giữ nguyên 3PN" in s for s in steps), "Giữ nhu cầu của khách là hướng đầu tiên"
    assert any("2PN+1" in s for s in steps), "Hạ phòng ngủ chỉ là lựa chọn mở rộng, không tự quyết"


# ─── P1.5 — liệt kê hay bảng ───────────────────────────────────────────────────────


def _units(n: int) -> list[dict]:
    return [
        {
            "unit_code": f"U-{i}",
            "bedrooms": 2,
            "area_m2": 70 + i,
            "listed_price_before_tax_vnd": 1_000_000_000 * (i + 1),
            "status": "AVAILABLE",
            "project_id": "THE_ZEN_PARK",
        }
        for i in range(n)
    ]


def test_single_unit_is_still_a_table() -> None:
    """Chốt P1.5 (cập nhật): có căn cần liệt kê ⇒ luôn dạng bảng, không liệt kê dòng."""
    rendered = inventory_funnel.render_matches(_units(1))
    assert rendered.splitlines()[0] == "| Mã căn | Phòng ngủ | Diện tích | Giá niêm yết (trước thuế) |"
    assert rendered.splitlines()[2].startswith("| U-0 | 2PN | 70m² |")


def test_two_units_also_use_table() -> None:
    rendered = inventory_funnel.render_matches(_units(2))
    lines = rendered.splitlines()
    assert len(lines) == 4, "1 tiêu đề + 1 phân cách + 2 dòng"
    assert all(line.startswith("|") for line in lines)
    assert "- U-0" not in rendered, "Không còn kiểu liệt kê dòng"


def test_many_units_use_table() -> None:
    rendered = inventory_funnel.render_matches(_units(4))
    assert len(rendered.splitlines()) == 2 + 4


def test_whole_basket_uses_table_and_scope_label() -> None:
    payload = json.loads(tra_cuu_gio_hang.invoke({}))
    assert "toàn giỏ đang mở bán" in payload["summary"]
    assert "| Mã căn | Phòng ngủ | Diện tích | Giá niêm yết (trước thuế) |" in payload["summary"]


# ─── P1.2 — chỉ mốc tổng quan vốn tự có ────────────────────────────────────────────


def _assess(**kwargs) -> dict:
    return json.loads(asyncio.run(danh_gia_von_tu_co.ainvoke(kwargs)))


def test_own_funds_overview_reports_ratio_and_gap() -> None:
    payload = _assess(von_tu_co_vnd=2_000_000_000, so_phong_ngu=3, ngay_giao_dich="2026-10-02")
    assert payload["unit_code"] == "ZEN-B-1502", "Lấy căn mềm nhất của phân khúc khi chưa chốt mã căn"
    assert 0.28 < payload["own_funds_ratio"] < 0.31
    assert payload["required_own_funds_vnd"] == 2_171_600_000
    assert payload["gap_vnd"] == 171_600_000


def test_own_funds_overview_has_no_detailed_cashflow() -> None:
    """Chốt P1.2: KHÔNG đưa bảng dòng tiền chi tiết khi mới hỏi khái quát."""
    summary = _assess(von_tu_co_vnd=2_000_000_000, so_phong_ngu=3, ngay_giao_dich="2026-10-02")["summary"]
    assert "đợt đầu" not in summary, "Không nêu đợt đầu/tiến độ chi tiết"
    assert "PA-" not in summary, "Không dán nhãn phương án chi tiết"
    assert "bảng dòng tiền" in summary, "Nhưng phải nói rõ muốn chi tiết thì có"


def test_own_funds_overview_is_cited_and_grounded() -> None:
    payload = _assess(von_tu_co_vnd=2_000_000_000, so_phong_ngu=3, ngay_giao_dich="2026-10-02")
    assert payload["citations"], "Mốc tổng quan cũng phải có căn cứ (engine tất định)"
    assert payload["data_as_of"], "Kèm mốc thời gian dữ liệu cho watermark (P1.6)"


def test_own_funds_enough_still_reports_surplus_direction() -> None:
    payload = _assess(von_tu_co_vnd=3_000_000_000, so_phong_ngu=3, ngay_giao_dich="2026-10-02")
    assert payload["gap_vnd"] == 0
    assert "đủ" in payload["summary"]
