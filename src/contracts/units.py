"""Ánh xạ chuẩn hoá + bộ sinh giá trị cho căn hộ — dùng chung cho API catalog, Copilot và script nạp DB.

Vì sao tách riêng: `src/api/endpoints/catalog.py` cần ánh xạ này, mà `src/agents/copilot/grounding.py`
lại import `catalog` để lấy fixture ⇒ nếu để ánh xạ trong một trong hai file sẽ thành vòng import.
Module này không phụ thuộc gì nên cả hai bên cùng dùng được.
"""

from __future__ import annotations

import re

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


# ─── Sinh giá trị diện tích / view cho dữ liệu chưa có ────────────────────────────
# Bối cảnh (chốt đợt 20): bảng `units` vận hành **thiếu** hai cột `area_m2` và `view`, nên mọi câu trả lời
# về căn phải in "—" hoặc suy diễn. Nay DB có hai cột đó; với 40 căn đang có, script nạp dữ liệu sinh giá
# trị ban đầu theo bảng dưới đây. **Đây là giá trị sinh tự động, không phải số đo thực tế** — khi có dữ
# liệu thật (bản vẽ/giỏ hàng chính thức) thì ghi đè trực tiếp vào DB, không cần sửa code.

#: Diện tích thông thuỷ cơ sở theo loại căn (m²) — mức phổ biến của căn hộ thương mại.
AREA_BY_UNIT_TYPE: dict[str, float] = {
    "STUDIO": 35.0,
    "1BR": 48.5,
    "2BR": 72.0,
    "2BR+": 84.2,
    "3BR": 98.5,
    "4BR": 128.0,
    "SHOPHOUSE": 135.0,
}

#: Nhãn view theo nhóm tháp (suy ra từ tiền tố mã căn — quy ước đặt mã của dự án).
VIEW_BY_CODE_PREFIX: tuple[tuple[tuple[str, ...], str], ...] = (
    (("R-",), "View sông Sài Gòn"),
    (("G-",), "View công viên & hồ cảnh quan"),
    (("SH-", "SHP-"), "Mặt tiền đại lộ thương mại"),
)
DEFAULT_VIEW = "View nội khu"


def _digits_seed(text: str) -> int:
    """Hạt giống tất định lấy từ mã căn: cùng một mã luôn cho cùng một con số."""
    digits = re.sub(r"\D", "", text or "")
    return int(digits[-3:] or 0)


def suggest_area_m2(
    unit_type: str | None,
    floor_number: int | None = None,
    unit_code: str = "",
) -> float:
    """Diện tích gợi ý cho một căn: cơ sở theo loại căn ± chênh lệch nhỏ theo tầng/mã căn.

    Tất định (cùng input → cùng output) để chạy lại script không đổi số, và để test khoá được giá trị.
    """
    key = str(unit_type or "").upper().strip()
    base = AREA_BY_UNIT_TYPE.get(key, 70.0)
    floor = int(floor_number or 0)
    step = ((floor * 7 + _digits_seed(unit_code)) % 5) - 2  # −2..+2
    return round(base + step * 0.5, 1)


def suggest_view(unit_code: str) -> str:
    """View gợi ý theo nhóm tháp (tiền tố mã căn); không khớp quy ước nào thì trả view nội khu."""
    code = str(unit_code or "").upper().strip()
    for prefixes, label in VIEW_BY_CODE_PREFIX:
        if code.startswith(prefixes):
            return label
    return DEFAULT_VIEW
