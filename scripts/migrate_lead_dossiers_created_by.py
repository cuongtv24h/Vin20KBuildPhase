#!/usr/bin/env python3
"""Thêm cột `lead_dossiers.created_by` — cơ sở cho quy tắc "Sale chỉ xoá khách do mình tạo".

Vì sao cần: trước đây bảng `lead_dossiers` chỉ có `assigned_sales_id` (Sale *phụ trách*), và cả hai
đường tạo hồ sơ đều không ghi ai là người tạo. Không có chủ sở hữu thì endpoint xoá không thể phân biệt
"khách của tôi" với "khách của người khác", và bất kỳ ai biết `dossier_id` cũng xoá được. Script này:

1. `ALTER TABLE lead_dossiers ADD COLUMN IF NOT EXISTS created_by varchar(64)` — chạy lại nhiều lần
   không lỗi, không mất dữ liệu (đúng lối các migration thủ công của repo, chưa dùng Alembic).
2. Tạo index `ix_lead_dossiers_created_by` (có guard `pg_indexes`, chạy lại an toàn).
3. **Backfill chủ sở hữu cho hồ sơ cũ, theo thứ tự bằng chứng**:
   a. `assigned_sales_id` — Sale đang phụ trách (nếu từng được gán qua `PUT/PATCH /leads/{id}`).
   b. `quotes.created_by` của báo giá liên kết (`lead_dossiers.quote_id`) — hồ sơ đã chuyển báo giá thì
      người lập báo giá chính là người chăm khách đó. Đây là bằng chứng thật, không phải suy đoán.
   c. Không có bằng chứng nào ⇒ giữ `created_by = NULL`. Hồ sơ vô chủ **chỉ ADMIN xoá được**; ADMIN cấp
      chủ sở hữu bằng `POST /api/v1/leads/{dossier_id}/assign-sale` (gán Sale phụ trách = đóng dấu người
      tạo) hoặc ngay trên màn CRM. Không gán bừa một tài khoản cho dữ liệu mình không biết ai tạo.

Vì sao không nới luật cho hồ sơ NULL: trên DB vận hành hiện KHÔNG hồ sơ nào có `created_by` (cột mới, và
`assigned_sales_id` cũng trống vì chưa đường nào ghi), nên "NULL ⇒ ai đăng nhập cũng xoá được" đồng nghĩa
toàn bộ khách hàng bị bỏ ngỏ — đúng lỗi người dùng đã phát hiện khi chạy script này.

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

#: (a) Sale đang phụ trách là chủ sở hữu.
BACKFILL_FROM_ASSIGNMENT = """
    UPDATE lead_dossiers
    SET created_by = assigned_sales_id
    WHERE created_by IS NULL AND assigned_sales_id IS NOT NULL
"""

#: (b) Hồ sơ đã chuyển báo giá: lấy đúng người lập báo giá làm chủ sở hữu.
BACKFILL_FROM_QUOTE = """
    UPDATE lead_dossiers AS d
    SET created_by = q.created_by
    FROM quotes AS q
    WHERE d.quote_id = q.quote_id
      AND d.created_by IS NULL
      AND q.created_by IS NOT NULL
"""

#: Đếm triển vọng (chỉ SELECT — dùng cho --dry-run, không ghi gì).
PROSPECT_STATEMENT = """
    SELECT
        count(*) AS total,
        count(*) FILTER (WHERE created_by IS NULL AND assigned_sales_id IS NOT NULL) AS from_assignment,
        count(*) FILTER (
            WHERE created_by IS NULL AND assigned_sales_id IS NULL AND quote_id IS NOT NULL
        ) AS from_quote_candidate,
        count(*) FILTER (
            WHERE created_by IS NULL AND assigned_sales_id IS NULL AND quote_id IS NULL
        ) AS no_evidence
    FROM lead_dossiers;
"""

COUNT_STATEMENT = """
    SELECT
        count(*) AS total,
        count(created_by) AS with_owner,
        count(*) FILTER (WHERE created_by IS NULL) AS ownerless,
        count(*) FILTER (WHERE assigned_sales_id IS NULL) AS unassigned
    FROM lead_dossiers;
"""

SELECT_STATEMENT = """
    SELECT d.dossier_id, d.customer_name, d.assigned_sales_id, d.created_by, d.quote_id
    FROM lead_dossiers AS d
    ORDER BY d.created_at, d.dossier_id;
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
                print("- Chạy thử (dry-run): không ALTER, không backfill, chỉ đọc.")
            else:
                for statement in ALTER_STATEMENTS:
                    cur.execute(statement)
                cur.execute(CREATE_INDEX_STATEMENT)
                conn.commit()
                print("- Da bao dam cot `created_by` va index `ix_lead_dossiers_created_by` ton tai.")

            cur.execute(COLUMN_EXISTS_STATEMENT)
            has_column = cur.fetchone() is not None

            if not has_column:
                print(
                    "- Cột `created_by` CHƯA có trên DB này — chạy thật (không --dry-run) để tạo cột "
                    "trước khi backfill."
                )
                cur.execute(COUNT_STATEMENT)
                total, _with_owner, _ownerless, unassigned = cur.fetchone()
                print(f"\nTổng {total} hồ sơ · chưa gán Sale phụ trách: {unassigned}")
                print("\nChạy lại không kèm --dry-run để ghi vào DB.")
                return total

            if dry_run:
                cur.execute(PROSPECT_STATEMENT)
                total, from_assignment, from_quote_candidate, no_evidence = cur.fetchone()
                print(f"- Sẽ gán chủ sở hữu theo Sale phụ trách: {from_assignment} hồ sơ.")
                print(
                    f"- Sẽ thử gán theo người lập báo giá (hồ sơ có quote_id): "
                    f"{from_quote_candidate} hồ sơ."
                )
                print(f"- Không có bằng chứng, giữ NULL (chỉ ADMIN xoá được): {no_evidence} hồ sơ.")
                cur.execute(SELECT_STATEMENT)
                rows = cur.fetchall()
                cur.execute(COUNT_STATEMENT)
                total, with_owner, _ownerless_now, unassigned = cur.fetchone()
                # Ước tính sau backfill: chỉ nhóm "không có bằng chứng nào" là còn vô chủ.
                ownerless = no_evidence
            else:
                cur.execute(BACKFILL_FROM_ASSIGNMENT)
                filled_assignment = cur.rowcount
                cur.execute(BACKFILL_FROM_QUOTE)
                filled_quote = cur.rowcount
                conn.commit()
                print(f"- Đã coi Sale đang phụ trách là người tạo: {filled_assignment} hồ sơ.")
                print(f"- Đã coi người lập báo giá là người tạo: {filled_quote} hồ sơ.")
                cur.execute(COUNT_STATEMENT)
                total, with_owner, ownerless, unassigned = cur.fetchone()
                cur.execute(SELECT_STATEMENT)
                rows = cur.fetchall()

    print(
        f"\nTổng {total} hồ sơ · có chủ sở hữu: {with_owner} · chưa có chủ (chỉ ADMIN xoá): {ownerless} "
        f"· chưa gán Sale phụ trách: {unassigned}"
    )
    if rows:
        header = f"{'Mã hồ sơ':<26}{'Khách hàng':<24}{'Sale phụ trách':<20}{'Người tạo':<14}{'Báo giá'}"
        print("\n" + header)
        print("-" * len(header))
        for dossier_id, customer_name, assigned_sales_id, created_by, quote_id in rows[:40]:
            print(
                f"{dossier_id:<26}{str(customer_name or '')[:22]:<24}"
                f"{str(assigned_sales_id or '—'):<20}{str(created_by or '—'):<14}"
                f"{str(quote_id or '—')}"
            )
        if len(rows) > 40:
            print(f"… và {len(rows) - 40} hồ sơ nữa.")
    if ownerless:
        print(
            f"\n{ownerless} hồ sơ chưa có người tạo: Sale KHÔNG xoá được (403). ADMIN gán chủ sở hữu bằng "
            "POST /api/v1/leads/{dossier_id}/assign-sale (body {\"sales_id\": \"...\"}) hoặc nút "
            "\"Gán Sale phụ trách\" trên màn CRM."
        )
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
