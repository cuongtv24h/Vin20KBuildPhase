"""
Đối soát schema READ-ONLY: src/db/models.py (SQLAlchemy metadata) vs PostgreSQL thật.

- Chỉ chạy SELECT trên information_schema/pg_catalog — KHÔNG CREATE/ALTER/DROP.
- So sánh: bảng thiếu/thừa, cột thiếu/thừa, kiểu, nullable, PK.
- Cách chạy: py -3 scripts/verify_schema.py
- Exit code: 0 = khớp, 1 = có lệch (in chi tiết ra stdout).
"""

from __future__ import annotations

import asyncio
import sys

sys.path.insert(0, ".")

from dotenv import dotenv_values  # noqa: E402,F401  (đọc .env trước khi import config)

from src.config import Settings  # noqa: E402
from src.db import models  # noqa: E402,F401  (đăng ký mọi model vào metadata)
from src.db.session import Base  # noqa: E402

INSPECT_TABLES = """
SELECT tablename FROM pg_tables WHERE schemaname = 'public' ORDER BY 1
"""

INSPECT_COLUMNS = """
SELECT column_name, data_type, is_nullable, character_maximum_length
FROM information_schema.columns
WHERE table_schema = 'public' AND table_name = $1
"""

INSPECT_PK = """
SELECT kcu.column_name
FROM information_schema.table_constraints tc
JOIN information_schema.key_column_usage kcu
  ON tc.constraint_name = kcu.constraint_name AND tc.table_schema = kcu.table_schema
WHERE tc.constraint_type = 'PRIMARY KEY' AND tc.table_schema = 'public' AND tc.table_name = $1
"""


def sa_to_pg(type_obj: object) -> str:
    """Chuyển type SQLAlchemy sang tên kiểu Postgres tương đương để so sánh."""
    try:
        from sqlalchemy.dialects import postgresql

        raw = type_obj.compile(dialect=postgresql.dialect())  # type: ignore[attr-defined]
    except Exception:
        return type(type_obj).__name__.upper()
    # SQLAlchemy compile ra FLOAT, information_schema trả double precision
    val = raw.lower().replace("double precision", "float")
    if val.endswith("[]"):
        return "array"
    if val.startswith("vector"):
        return "user-defined"
    return val


def pg_type_of(row: object) -> str:
    """Chuẩn hoá kiểu từ information_schema: nối length cho varchar, map double precision."""
    t = str(row["data_type"]).lower()
    max_len = row["character_maximum_length"]
    if t == "character varying" and max_len:
        t = f"varchar({max_len})"
    return t.replace("double precision", "float")


async def main() -> int:
    settings = Settings()
    dsn = settings.database_url.replace("postgresql+asyncpg://", "postgresql://")

    import asyncpg

    try:
        conn = await asyncpg.connect(dsn, timeout=15, ssl="prefer")
    except Exception as exc:
        print(f"KHONG KET NOI DUOC DB: {type(exc).__name__}: {exc}")
        return 1

    try:
        pg_tables = {row["tablename"] for row in await conn.fetch(INSPECT_TABLES)}
        sa_tables = set(Base.metadata.tables.keys())

        missing_in_db = sorted(sa_tables - pg_tables)
        extra_in_db = sorted(pg_tables - sa_tables)

        print(f"SQLAlchemy models : {len(sa_tables)} bang ({', '.join(sorted(sa_tables))})")
        print(f"PostgreSQL that   : {len(pg_tables)} bang")
        print()

        issues: list[str] = []
        if missing_in_db:
            issues.append(f"BANG THIEU tren DB (co trong models.py): {', '.join(missing_in_db)}")
        if extra_in_db:
            print(f"[info] Bang tren DB nhung khong co trong models.py: {', '.join(extra_in_db)}")

        common = sorted(sa_tables & pg_tables)
        for table in common:
            sa_cols: dict[str, tuple[str, bool, bool]] = {}
            for name, col in Base.metadata.tables[table].columns.items():
                sa_cols[name] = (
                    sa_to_pg(col.type).lower(),
                    bool(col.nullable),
                    bool(col.primary_key),
                )
            pk_rows = await conn.fetch(INSPECT_PK, table)
            pk_cols = {r["column_name"] for r in pk_rows}
            pg_rows = await conn.fetch(INSPECT_COLUMNS, table)
            pg_cols: dict[str, tuple[str, bool, bool]] = {}
            for r in pg_rows:
                pg_cols[r["column_name"]] = (
                    pg_type_of(r),
                    r["is_nullable"] == "YES",
                    r["column_name"] in pk_cols,
                )

            only_sa = sorted(set(sa_cols) - set(pg_cols))
            only_pg = sorted(set(pg_cols) - set(sa_cols))
            if only_sa:
                issues.append(f"{table}: cot THIEU tren DB: {', '.join(only_sa)}")
            if only_pg:
                print(f"[info] {table}: cot tren DB nhung khong co trong model: {', '.join(only_pg)}")
            for cname in sorted(set(sa_cols) & set(pg_cols)):
                sa_t, sa_n, sa_p = sa_cols[cname]
                pg_t, pg_n, pg_p = pg_cols[cname]
                # So sánh kiểu: giống base; độ dài varchar chỉ báo lỗi khi CẢ HAI đều khai báo và khác nhau
                sa_base, _, sa_len = sa_t.partition("(")
                pg_base, _, pg_len = pg_t.partition("(")
                sa_len = sa_len.rstrip(")")
                pg_len = pg_len.rstrip(")")
                if sa_base != pg_base:
                    issues.append(f"{table}.{cname}: kieu lech - model={sa_t} | db={pg_t}")
                elif sa_len and pg_len and sa_len != pg_len:
                    issues.append(f"{table}.{cname}: do dai lech - model=varchar({sa_len}) | db=varchar({pg_len})")
                if sa_n != pg_n:
                    issues.append(f"{table}.{cname}: nullable lech - model={sa_n} | db={pg_n}")
                if sa_p != pg_p:
                    issues.append(f"{table}.{cname}: PK lech - model={sa_p} | db={pg_p}")

        print()
        if issues:
            print(f"=== LECH ({len(issues)} di) ===")
            for item in issues:
                print(f" - {item}")
            print()
            print("Luu y: DB do DDL mydoc/4.2 tao - model SQLAlchemy la source of truth cua code,")
            print("nen lech o day la rui ro that khi ORM ghi du lieu (runtime error).")
            return 1
        print(f"OK: {len(common)} bang khop hoan toan (cot/kieu/nullable/PK), 0 lech.")
        return 0
    finally:
        await conn.close()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
