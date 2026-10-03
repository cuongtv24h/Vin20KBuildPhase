"""Test luật gộp giỏ hàng DB + fixture (`src.contracts.units.merge_units`) — chốt R19.

Bối cảnh: bản cũ cộng thẳng hai nguồn nên giỏ hàng báo 40 căn DB + 4 căn fixture = "44 căn".
"""

from __future__ import annotations

from src.contracts.units import (
    AREA_BY_UNIT_TYPE,
    BEDROOMS_BY_UNIT_TYPE,
    DEFAULT_VIEW,
    merge_units,
    suggest_area_m2,
    suggest_view,
)


def _unit(code: str, project_id: str, project_name: str = "") -> dict:
    return {"unit_code": code, "project_id": project_id, "project_name": project_name or project_id}


def test_db_is_primary_and_fixture_supplements_missing_projects() -> None:
    db_units = [_unit("ZEN-T-0001", "THE_ZEN_PARK", "The Zen Park")]
    fixture = [
        _unit("ZEN-A-1205", "THE_ZEN_PARK", "The Zen Park"),  # cùng dự án DB ⇒ bỏ
        _unit("OTHER-01", "OTHER_PROJECT", "Other Project"),  # dự án DB chưa có ⇒ giữ
    ]
    merged = merge_units(db_units, fixture)
    assert [u["unit_code"] for u in merged] == ["ZEN-T-0001", "OTHER-01"]


def test_fixture_unit_with_same_code_is_dropped() -> None:
    db_units = [_unit("ZEN-A-1205", "SOME_NEW_PROJECT", "Some New Project")]
    fixture = [_unit("ZEN-A-1205", "THE_ZEN_PARK", "The Zen Park")]
    assert [u["unit_code"] for u in merge_units(db_units, fixture)] == ["ZEN-A-1205"]


def test_empty_db_returns_fixture_untouched() -> None:
    fixture = [_unit("ZEN-A-0803", "THE_ZEN_PARK", "The Zen Park")]
    assert merge_units([], fixture) == fixture


def test_household_counts_of_the_44_unit_bug() -> None:
    """Đúng kịch bản lỗi: 40 căn DB + 4 căn fixture cùng hai dự án ⇒ phải còn 40, không phải 44."""
    db_units = [_unit(f"DB-{i:04d}", "THE_ZEN_PARK" if i % 2 else "VLANDFUTURE_SAPPHIRE") for i in range(40)]
    fixture = [
        _unit("ZEN-A-1205", "THE_ZEN_PARK", "The Zen Park"),
        _unit("ZEN-A-0803", "THE_ZEN_PARK", "The Zen Park"),
        _unit("ZEN-B-1502", "THE_ZEN_PARK", "The Zen Park"),
        _unit("SAP-01-2204", "VLANDFUTURE_SAPPHIRE", "VLandFuture Sapphire"),
    ]
    assert len(merge_units(db_units, fixture)) == 40


def test_project_matching_is_case_and_space_insensitive() -> None:
    db_units = [_unit("DB-01", "vlandfuture_sapphire", "VLandFuture  Sapphire")]
    fixture = [_unit("SAP-01-2204", "VLANDFUTURE_SAPPHIRE", "VLandFuture Sapphire")]
    assert [u["unit_code"] for u in merge_units(db_units, fixture)] == ["DB-01"]


def test_bedroom_map_covers_every_unit_type_used_in_db() -> None:
    # Ánh xạ nghiệp vụ, không suy diễn số liệu: mỗi loại căn trong DB có số phòng ngủ tương ứng.
    assert BEDROOMS_BY_UNIT_TYPE == {
        "STUDIO": 0,
        "1BR": 1,
        "2BR": 2,
        "3BR": 3,
        "4BR": 4,
        "SHOPHOUSE": 0,
    }


# ─── Sinh diện tích / view cho dữ liệu chưa có (đợt 20) ────────────────────────────


def test_suggested_area_is_deterministic_and_near_type_baseline() -> None:
    """Cùng một căn luôn ra cùng con số (chạy lại script không đổi số), và bám sát mức của loại căn."""
    first = suggest_area_m2("2BR", 11, "ZEN-A-1101")
    assert first == suggest_area_m2("2BR", 11, "ZEN-A-1101")
    assert abs(first - AREA_BY_UNIT_TYPE["2BR"]) <= 1.0, "dao động tối đa ±1m² quanh mức loại căn"


def test_suggested_area_separates_unit_types() -> None:
    """Studio/1PN/2PN/3PN phải ra các mức khác nhau — không dùng chung một số cho mọi loại."""
    values = {t: suggest_area_m2(t, 10, f"X-{t}") for t in ("STUDIO", "1BR", "2BR", "3BR")}
    assert values["STUDIO"] < values["1BR"] < values["2BR"] < values["3BR"]


def test_suggested_area_handles_unknown_and_missing_type() -> None:
    """Loại căn lạ/None ⇒ dùng mức trung tính 70m² (±1m²), không vỡ và không trả 0."""
    assert abs(suggest_area_m2(None, None, "") - 70.0) <= 1.0
    assert suggest_area_m2("Loai-La", 3, "X-01") > 0


def test_suggested_view_follows_tower_prefix() -> None:
    assert suggest_view("R-02.02") == "View sông Sài Gòn"
    assert suggest_view("G-03.02") == "View công viên & hồ cảnh quan"
    assert suggest_view("SH-01.01") == "Mặt tiền đại lộ thương mại"
    assert suggest_view("ZEN-A-1101") == DEFAULT_VIEW, "không khớp quy ước tháp ⇒ view nội khu"


def test_unit_model_has_area_and_view_columns() -> None:
    """Chốt đợt 20: 2 cột phải có trong model + metadata để migration/seed ghi được."""
    from src.db.models import UnitModel

    columns = set(UnitModel.__table__.columns.keys())
    assert {"area_m2", "view"} <= columns
    assert UnitModel.__table__.columns["area_m2"].nullable is True
    assert UnitModel.__table__.columns["view"].nullable is True
