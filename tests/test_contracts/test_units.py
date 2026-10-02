"""Test luật gộp giỏ hàng DB + fixture (`src.contracts.units.merge_units`) — chốt R19.

Bối cảnh: bản cũ cộng thẳng hai nguồn nên giỏ hàng báo 40 căn DB + 4 căn fixture = "44 căn".
"""

from __future__ import annotations

from src.contracts.units import BEDROOMS_BY_UNIT_TYPE, merge_units


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
