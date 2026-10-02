"""Ánh xạ chuẩn hoá của căn hộ — dùng chung cho API catalog và lớp grounding của Copilot.

Vì sao tách riêng: `src/api/endpoints/catalog.py` cần ánh xạ này, mà `src/agents/copilot/grounding.py`
lại import `catalog` để lấy fixture ⇒ nếu để ánh xạ trong một trong hai file sẽ thành vòng import.
Module này không phụ thuộc gì nên cả hai bên cùng dùng được.
"""

from __future__ import annotations

#: Loại căn trong DB → số phòng ngủ. Đây là ánh xạ **nghiệp vụ** ("3BR" = 3 phòng ngủ),
#: không phải suy diễn số liệu. Diện tích/hướng KHÔNG suy ra từ loại căn vì DB không lưu.
BEDROOMS_BY_UNIT_TYPE: dict[str, int] = {
    "STUDIO": 0,
    "1BR": 1,
    "2BR": 2,
    "3BR": 3,
    "4BR": 4,
    "SHOPHOUSE": 0,
}


def merge_units(
    db_units: list[dict], fixture_units: list[dict]
) -> list[dict]:
    """Gộp giỏ hàng DB với fixture theo nguyên tắc **DB là nguồn chính**.

    Vì sao cần: bản cũ cộng thẳng hai nguồn ⇒ giỏ hàng báo 40 căn DB + 4 căn fixture = "44 căn", và Sale
    đọc thấy căn demo (ZEN-A-1205, SAP-01-2204…) lẫn vào giỏ thật. Quy tắc nay:
    1. khử trùng theo mã căn;
    2. bỏ các bản ghi fixture thuộc dự án **đã có dữ liệu trong DB** (mã dự án hoặc tên dự án trùng).

    Fixture chỉ còn tác dụng bù cho dự án mà DB chưa có căn nào (môi trường demo/local).
    """

    def key(value: object) -> str:
        return " ".join(str(value or "").strip().lower().split())

    if not db_units:
        return list(fixture_units)

    db_codes = {key(u.get("unit_code")) for u in db_units}
    db_projects = {key(u.get("project_id")) for u in db_units} | {
        key(u.get("project_name")) for u in db_units
    }
    db_codes.discard("")
    db_projects.discard("")

    extras: list[dict] = []
    for unit in fixture_units:
        if key(unit.get("unit_code")) in db_codes:
            continue
        keys = {key(unit.get("project_id")), key(unit.get("project_name"))}
        keys.discard("")
        if keys & db_projects:
            continue
        extras.append(unit)
    return list(db_units) + extras
