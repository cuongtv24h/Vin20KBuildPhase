"""R19 — số liệu giỏ hàng trong câu trả lời Copilot phải khớp DB vận hành.

Gồm ba nhóm:
1. `grounding.list_units`: DB là nguồn chính, không cộng trùng fixture, tên dự án lấy từ DB.
2. Bảng giỏ hàng: do MÁY dựng (`inventory_funnel`), cột/hàng cố định, thiếu dữ liệu thì in `—`.
3. `graph._ensure_units_table`: câu trả lời có liệt kê căn luôn mang đúng bảng đó, không phụ thuộc
   việc model có viết lại bảng hay không.
"""

from __future__ import annotations

import pytest

from src.agents.copilot import graph, grounding, inventory_funnel


@pytest.fixture
def db_units(monkeypatch):
    """Giả lập 40 căn đọc từ DB vận hành (2 dự án thật) thay cho psycopg."""
    units = []
    for index in range(20):
        units.append(
            {
                "unit_code": f"ZEN-T-{index + 1:04d}",
                "project_id": "THE_ZEN_PARK",
                "project_name": "The Zen Park",
                "floor": 5 + index,
                "bedrooms": [1, 2, 3][index % 3],
                "area_m2": 0.0,
                "view": "",
                "listed_price_before_tax_vnd": 3_000_000_000 + index * 150_000_000,
                "status": "AVAILABLE",
            }
        )
    for index in range(20):
        units.append(
            {
                "unit_code": f"SAP-T-{index + 1:04d}",
                "project_id": "VLANDFUTURE_SAPPHIRE",
                "project_name": "VLandFuture Sapphire",
                "floor": 10 + index,
                "bedrooms": [2, 3][index % 2],
                "area_m2": 0.0,
                "view": "",
                "listed_price_before_tax_vnd": 5_000_000_000 + index * 180_000_000,
                "status": "SOLD" if index < 2 else "AVAILABLE",
            }
        )
    monkeypatch.setattr(grounding, "_cached_db_units", units, raising=False)
    monkeypatch.setattr(grounding, "_cached_db_project_names", {}, raising=False)
    return units


def test_basket_count_is_db_only_and_never_44(db_units) -> None:
    """40 căn DB + 4 căn fixture cùng dự án ⇒ giỏ hàng phải là 40, không phải 44."""
    basket = grounding.list_units()
    assert len(basket) == 40
    assert not any(u["unit_code"] in {"ZEN-A-0803", "ZEN-A-1205", "ZEN-B-1502", "SAP-01-2204"} for u in basket)
    assert len(grounding.search_units()) == 38, "2 căn SOLD không nằm trong giỏ đang mở bán"


def test_project_names_come_from_db_and_never_invent_riverside(db_units) -> None:
    names = {grounding.project_name(u["project_id"]) for u in grounding.list_units()}
    assert names == {"The Zen Park", "VLandFuture Sapphire"}
    assert all("Riverside" not in name for name in names)


def test_unknown_project_id_falls_back_to_its_own_id_not_a_fake_name(db_units) -> None:
    assert grounding.project_name("PROJECT-NOT-IN-DB") == "PROJECT-NOT-IN-DB"


def test_bedroom_histogram_matches_db(db_units) -> None:
    histogram = inventory_funnel.bedroom_histogram()
    assert sum(histogram.values()) == 38
    assert histogram[2] == len([u for u in grounding.search_units(bedrooms=2)])


def test_units_listing_has_basket_table_from_the_machine() -> None:
    observation = {"tool": "tra_cuu_gio_hang", "summary": "2 căn phù hợp:\n" + inventory_funnel.render_matches(
        grounding.search_units(bedrooms=2)[:2]
    )}
    table = graph._units_table_from_observations([observation])
    assert table.splitlines()[0] == (
        "| Mã căn | Dự án | Phòng ngủ | Diện tích | Giá niêm yết (trước thuế) | Tầng* | View* |"
    )


def test_reply_without_table_gets_basket_table_appended() -> None:
    table = inventory_funnel.render_matches(grounding.search_units(bedrooms=1))
    text = graph._ensure_units_table("Còn 1 căn 1 ngủ đang mở bán ạ.", table)
    assert text.endswith(table)
    assert text.startswith("Còn 1 căn 1 ngủ đang mở bán ạ.")


def test_model_rewritten_table_is_replaced_by_the_canonical_one() -> None:
    """Model tự viết bảng thiếu cột ⇒ bảng phải bị thay bằng bảng máy dựng (chống mất cột/lệch hàng)."""
    canonical = inventory_funnel.render_matches(grounding.search_units(bedrooms=1))
    model_table = "| Mã căn | Diện tích | Giá niêm yết (trước thuế) |\n|---|---|---|\n| ZEN-A-0803 | 52m² | 2.500.000.000 ₫ |"
    text = graph._ensure_units_table(f"Đây là căn phù hợp:\n{model_table}", canonical)
    assert "| Dự án |" in text, "bảng trả về phải có cột Dự án"
    assert "| Phòng ngủ |" in text, "bảng trả về phải có cột Phòng ngủ"
    assert "| Diện tích | 52m² |" not in text, "bảng model tự viết bị thay, không giữ lại ô bịa"


def test_non_unit_table_is_kept_and_basket_table_is_added() -> None:
    canonical = inventory_funnel.render_matches(grounding.search_units(bedrooms=2))
    policy_table = "| Chính sách | Nội dung |\n|---|---|\n| CSBH | Chiết khấu 8% |"
    text = graph._ensure_units_table(policy_table, canonical)
    assert policy_table in text
    assert canonical in text


def test_identical_table_is_not_duplicated() -> None:
    canonical = inventory_funnel.render_matches(grounding.search_units(bedrooms=2))
    text = graph._ensure_units_table(f"Giỏ hàng:\n{canonical}", canonical)
    assert text.count("| Mã căn |") == 1


def test_missing_table_source_leaves_reply_untouched() -> None:
    assert graph._ensure_units_table("Không có căn nào phù hợp.", "") == "Không có căn nào phù hợp."
