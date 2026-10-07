#!/usr/bin/env python3
"""Thêm cột `lead_dossiers.created_by` — cơ sở cho quy tắc "Sale chỉ xoá khách do mình tạo".

Vì sao cần: trước đây bảng `lead_dossiers` chỉ có `assigned_sales_id` (Sale *phụ trách*), và cả hai
đường tạo hồ sơ đều không ghi ai là người tạo. Không có chủ sở hữu thì endpoint xoá không thể phân biệt
"khách của tôi" với "khách của người khác", và bất kỳ ai biết `dossier_id` cũng xoá được. Script này:

1. `ALTER TABLE lead_dossiers ADD COLUMN IF NOT EXISTS created_by varchar(64)` — chạy lại nhiều lần
   không lỗi, không mất dữ liệu (đúng lối các migration thủ công của repo, chưa dùng Alembic).
2. Tạo index `ix_lead_dossiers_created_by` (có guard `information_schema`, chạy lại an toàn).
3. **Backfill**: các hồ sơ cũ có `assigned_sales_id` được coi chủ sở hữu là Sale đang phụ trách —
   `created_by = assigned_sales_id`. Cách này giữ cho hồ sơ cũ vẫn xoá được bởi đúng người phụ trách,
   không khoá dữ liệu lịch sử. Hồ sơ không gán Sale nào giữ `created_by = NULL`: hệ thống vẫn cho xoá
   bởi nhân viên đã đăng nhập (dữ liệu di sản không có chủ để đối chiếu — xem `delete_dossier`).

Cách dùng:
    .venv/bin/python scripts/migrate_lead_dossiers_created_by.py --dry-run   # xem trước, không ghi
    .venv/bin/python scripts/migrate_lead_dossiers_created_by.py             # chạy thật trên DB vận hành
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

ALTER_STATEMENTS = (
    "ALTER TABLE lead_dossiers ADD COLUMN IF NOT EXISTS created_by varchar(64)",
)

COLUMN_EXISTS_STATEMENT = """
    SELECT column_name FROM information_schema.columns
    WHERE table_name = 'lead_dossiers' AND column_name = 'created_by';
"""

INDEX_EXISTS_STATEMENT = """
    SELECT indexname FROM pg_indexes
    WHERE tablename = 'lead_dossiers' AND indexname = 'ix_lead_dossiers_created_by';
"""

CREATE_INDEX_STATEMENT = (
    "CREATE INDEX IF NOT EXISTS ix_lead_dossiers_created_by ON lead_dossiers (created_by)"
)

BACKFILL_STATEMENT = (
    "UPDATE lead_dossiers SET created_by = assigned_sales_id "
    "WHERE created_by IS NULL AND assigned_sales_id IS NOT NULL"
)

COUNT_STATEMENT = """
    SELECT
        count(*) AS total,
        count(created_by) AS with_owner,
        count(*) FILTER (WHERE created_by IS NULL AND assigned_sales_id IS NOT NULL) AS backfillable,
        count(*) FILTER (WHERE assigned_sales_id IS NULL) AS unassigned
    FROM lead_dossiers;
"""

SELECT_STATEMENT = """
    SELECT dossier_id, customer_name, assigned_sales_id, created_by
    FROM lead_dossiers
    ORDER BY dossier_id;
"""


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


def run(dry_run: bool = False) -> int:
    with _connect() as conn:  # type: ignore[attr-defined]
        with conn.cursor() as cur:
            if dry_run:
                print("• Chạy thử (dry-run): không ALTER, không backfill.")
            else:
                for statement in ALTER_STATEMENTS:
                    cur.execute(statement)
                cur.execute(CREATE_INDEX_STATEMENT)
                conn.commit()
                print("✓ Đã bảo đảm cột `created_by` và index `ix_lead_dossiers_created_by` tồn tại.")

            cur.execute(COLUMN_EXISTS_STATEMENT)
            has_column = cur.fetchone() is not None
            cur.execute(COUNT_STATEMENT)
            total, with_owner, backfillable, unassigned = cur.fetchone()

            if not has_column:
                print(
                    "• Cột `created_by` CHƯA có trên DB này — chạy thật (không --dry-run) để tạo cột "
                    "trước khi backfill."
                )
            elif backfillable:
                cur.execute(BACKFILL_STATEMENT)
                if not dry_run:
                    conn.commit()
                verb = "Sẽ coi" if dry_run else "Đã coi"
                print(f"• {verb} Sale đang phụ trách là người tạo cho {backfillable} hồ sơ cũ.")
            else:
                print("• Không có hồ sơ cũ nào cần backfill.")

            if has_column:
                cur.execute(SELECT_STATEMENT)
                rows = cur.fetchall()
            else:
                rows = []

    print(f"\nTổng {total} hồ sơ · có chủ sở hữu: {with_owner} · chưa gán Sale: {unassigned}")
    if rows:
        header = f"{'Mã hồ sơ':<26}{'Khách hàng':<24}{'Sale phụ trách':<20}{'Người tạo'}"
        print("\n" + header)
        print("-" * len(header))
        for dossier_id, customer_name, assigned_sales_id, created_by in rows[:40]:
            print(
                f"{dossier_id:<26}{str(customer_name or '')[:22]:<24}"
                f"{str(assigned_sales_id or '—'):<20}{str(created_by or '—')}"
            )
        if len(rows) > 40:
            print(f"… và {len(rows) - 40} hồ sơ nữa.")
    if dry_run:
        print("\nChạy lại không kèm --dry-run để ghi vào DB.")
    return total


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Thêm cột lead_dossiers.created_by và backfill chủ sở hữu cho hồ sơ cũ"
    )
    parser.add_argument("--dry-run", action="store_true", help="Chỉ in kế hoạch, không ghi DB")
    args = parser.parse_args()
    run(dry_run=args.dry_run)


if __name__ == "__main__":
    main()
