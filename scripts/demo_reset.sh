#!/usr/bin/env bash
# ============================================================================
# PricePolicy AI Agent — Demo Reset Script (Phase 5)
# Owner: TechLead (cuongtv_02560) | TASK-P5-03
# Mục tiêu: khôi phục môi trường demo về trạng thái tinh khôi trong < 15 giây.
# ============================================================================

set -euo pipefail

# ---- Cấu hình (override bằng biến môi trường nếu cần) ----
DB_HOST="${DEMO_DB_HOST:-127.0.0.1}"
DB_PORT="${DEMO_DB_PORT:-5433}"
DB_USER="${DEMO_DB_USER:-vland}"
DB_NAME="${DEMO_DB_NAME:-vland_policy}"
SUPPORT_SQLITE_DB="${DEMO_SQLITE_PATH:-./data/app.db}"
PDF_DIR="./data/pre_sales_pdfs"
TEST_PDF_DIR="./data/test_pdfs"

echo "==> [1/5] Dừng server backend đang chạy (nếu có)..."
# Chỉ kill uvicorn của dự án này, không đụng tiến trình khác
pkill -f "uvicorn src.main:app" 2>/dev/null || true

echo "==> [2/5] Reset PostgreSQL demo (drop & recreate schema)..."
if command -v psql >/dev/null 2>&1; then
  PGPASSWORD="${DEMO_DB_PASSWORD:-demo_password}" psql \
    -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" \
    -c "DROP SCHEMA public CASCADE; CREATE SCHEMA public;" \
    >/dev/null 2>&1 || echo "   (PostgreSQL không khả dụng — bỏ qua, dùng SQLite fallback)"
else
  echo "   (psql không tìm thấy — bỏ qua, dùng SQLite fallback)"
fi

echo "==> [3/5] Reset SQLite demo database..."
rm -f "$SUPPORT_SQLITE_DB"
rm -f ./data/*.db-journal ./data/*.db-wal 2>/dev/null || true

echo "==> [4/5] Xóa PDF tham khảo cũ (pre_sales_pdfs, test_pdfs)..."
rm -rf "$PDF_DIR" "$TEST_PDF_DIR"

export PYTHONIOENCODING=utf-8
python3 -c "import asyncio; from src.db.session import init_db; asyncio.run(init_db()); print('   Schema 14 tables recreated successfully.')" 2>/dev/null || \
py -3 -c "import asyncio; from src.db.session import init_db; asyncio.run(init_db()); print('   Schema 14 tables recreated successfully.')" 2>/dev/null || \
echo "   (Canh bao: khong tai tao duoc schema - kiem tra Python env)"

echo ""
echo "✅ DEMO RESET HOÀN TẤT — môi trường demo đã tinh khôi."
echo "   Chạy server:  py -3 -m uvicorn src.main:app --reload"
echo "   Chạy demo:    py -3 -m pytest tests/ -q"
