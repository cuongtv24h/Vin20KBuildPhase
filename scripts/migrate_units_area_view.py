#!/usr/bin/env python3
"""Thêm 2 cột `area_m2` và `view` vào bảng `units` + sinh giá trị cho các căn đang có.

Vì sao cần (chốt đợt 20): bảng `units` vận hành chỉ có mã căn, dự án, loại căn, tầng, giá, ngày bàn giao và
trạng thái. Thiếu diện tích và hướng/view nên câu trả lời của Copilot và bảng giỏ hàng phải in "—", hoặc
tệ hơn là suy diễn theo loại căn (lỗi đã bị gỡ ở đợt 19). Script này:

1. `ALTER TABLE units ADD COLUMN IF NOT EXISTS area_m2 double precision` / `view varchar(128)` — chạy lại
   nhiều lần không lỗi, không mất dữ liệu.
2. Sinh giá trị **tất định** cho các căn còn thiếu (`area_m2 IS NULL`), dùng chung hàm với lớp đọc DB
   (`src.contracts.units.suggest_area_m2` / `suggest_view`) để mọi môi trường ra cùng con số.
3. In bảng đối chiếu trước/sau để người chạy kiểm được bằng mắt.

Giá trị sinh ra là **giá trị khởi tạo hợp lý theo loại căn + nhóm tháp**, KHÔNG phải số đo thực tế. Khi có
dữ liệu chính thức thì `UPDATE` trực tiếp vào DB (hoặc chạy lại `--all` sau khi sửa `AREA_BY_UNIT_TYPE`).

Cách dùng:
    .venv/bin/python scripts/migrate_units_area_view.py --dry-run   # xem trước, không ghi
    .venv/bin/python scripts/migrate_units_area_view.py             # chỉ điền các căn còn thiếu
    .venv/bin/python scripts/migrate_units_area_view.py --all       # ghi đè toàn bộ theo bảng sinh
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from src.contracts.units import suggest_area_m2, suggest_view  # noqa: E402

ALTER_STATEMENTS = (
    "ALTER TABLE units ADD COLUMN IF NOT EXISTS area_m2 double precision",
    "ALTER TABLE units ADD COLUMN IF NOT EXISTS view varchar(128)",
)

COLUMN_EXISTS_STATEMENT = """
    SELECT column_name FROM information_schema.columns
    WHERE table_name = 'units' AND column_name IN ('area_m2', 'view');
"""

#: Hai câu SELECT: dùng cột thật khi đã có, còn `--dry-run` trên DB cũ thì đọc NULL để không phải sửa gì.
SELECT_WITH_COLUMNS = """
    SELECT unit_code, project_id, unit_type, floor_number, area_m2, view
    FROM units
    ORDER BY unit_code;
"""
SELECT_LEGACY = """
    SELECT unit_code, project_id, unit_type, floor_number, NULL::double precision, NULL::varchar
    FROM units
    ORDER BY unit_code;
"""

UPDATE_STATEMENT = "UPDATE units SET area_m2 = %s, view = %s WHERE unit_code = %s;"


def _connect() -> object:
    """Mở kết nối Postgres theo đúng cấu hình ứng dụng (`Settings.database_url`)."""
    import psycopg

    from src.config import get_settings

    settings = get_settings()
    db_url = settings.database_url.replace("+asyncpg", "")
    if not db_url.startswith(("postgres://", "postgresql://")):
        raise SystemExit(
            "DATABASE_URL hiện không phải Postgres (đang là "
            f"{db_url.split(':', 1)[0]}://…). Script này chỉ chạy trên DB vận hành — "
            "đặt DATABASE_URL trong .env rồi chạy lại."
        )
    return psycopg.connect(db_url, connect_timeout=10)


def run(dry_run: bool = False, overwrite_all: bool = False) -> int:
    with _connect() as conn:  # type: ignore[attr-defined]
        with conn.cursor() as cur:
            if not dry_run:
                for statement in ALTER_STATEMENTS:
                    cur.execute(statement)
                conn.commit()
                print("✓ Đã bảo đảm 2 cột `area_m2`, `view` tồn tại trên bảng `units`.")
            else:
                print("• Chạy thử (dry-run): không ALTER, không UPDATE.")

            cur.execute(COLUMN_EXISTS_STATEMENT)
            existing_columns = {row[0] for row in cur.fetchall()}
            ready = {"area_m2", "view"} <= existing_columns
            cur.execute(SELECT_WITH_COLUMNS if ready else SELECT_LEGACY)
            rows = cur.fetchall()

    if not rows:
        print("Bảng `units` chưa có dòng nào — không có gì để sinh giá trị.")
        return 0
    if not ({"area_m2", "view"} <= existing_columns):
        print("• DB hiện CHƯA có 2 cột — chạy thật (không --dry-run) để tạo cột rồi mới ghi được.")

    planned: list[tuple[str, str, int | None, float | None, str | None, float, str]] = []
    for unit_code, project_id, unit_type, floor_number, area_m2, view in rows:
        needs_area = area_m2 is None or float(area_m2 or 0) <= 0
        needs_view = not str(view or "").strip()
        if overwrite_all or needs_area or needs_view:
            new_area = suggest_area_m2(unit_type, floor_number, unit_code)
            new_view = suggest_view(unit_code)
            planned.append((unit_code, project_id, floor_number, area_m2, view, new_area, new_view))

    if not planned:
        print(f"✓ {len(rows)} căn đều đã có đủ diện tích và view — không cần cập nhật.")
        return 0

    with _connect() as conn:  # type: ignore[attr-defined]
        with conn.cursor() as cur:
            for unit_code, _project, _floor, _old_area, _old_view, new_area, new_view in planned:
                if not dry_run:
                    cur.execute(UPDATE_STATEMENT, (new_area, new_view, unit_code))
            if not dry_run:
                conn.commit()

    header = f"{'Mã căn':<16}{'Loại':<10}{'Tầng':>5}  {'Diện tích cũ → mới':<24}{'View mới'}"
    print("\n" + header)
    print("-" * len(header))
    for unit_code, project_id, floor_number, old_area, old_view, new_area, new_view in planned:
        old_text = "—" if old_area is None else f"{float(old_area):g}"
        print(f"{unit_code:<16}{project_id[:8]:<10}{str(floor_number or ''):>5}  {old_text + ' → ' + f'{new_area:g}':<24}{new_view}")

    verb = "Sẽ cập nhật" if dry_run else "Đã cập nhật"
    print(f"\n{verb} {len(planned)}/{len(rows)} căn.")
    if dry_run:
        print("Chạy lại không kèm --dry-run để ghi vào DB.")
    return len(planned)


def main() -> None:
    parser = argparse.ArgumentParser(description="Thêm cột area_m2/view và sinh giá trị cho bảng units")
    parser.add_argument("--dry-run", action="store_true", help="Chỉ in kế hoạch, không ghi DB")
    parser.add_argument(
        "--all",
        action="store_true",
        help="Ghi đè cả những căn đã có diện tích/view (dùng khi muốn sinh lại toàn bộ)",
    )
    args = parser.parse_args()
    run(dry_run=args.dry_run, overwrite_all=args.all)


if __name__ == "__main__":
    main()
