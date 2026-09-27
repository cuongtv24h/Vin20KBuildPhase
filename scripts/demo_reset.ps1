# ============================================================================
# PricePolicy AI Agent — Demo Reset Script (PowerShell for Windows)
# Owner: TechLead (cuongtv_02560) | TASK-P5-03
# Mục tiêu: khôi phục môi trường demo về trạng thái tinh khôi trong < 15 giây.
# ============================================================================

$ErrorActionPreference = "Continue"

Write-Host "==> [1/5] Dung server backend dang chay (neu co)..." -ForegroundColor Cyan
Get-Process python -ErrorAction SilentlyContinue | Where-Object { $_.CommandLine -like "*uvicorn src.main:app*" } | Stop-Process -Force -ErrorAction SilentlyContinue

Write-Host "==> [2/5] Reset PostgreSQL demo (neu co)..." -ForegroundColor Cyan
if (Get-Command psql -ErrorAction SilentlyContinue) {
    $env:PGPASSWORD = $env:DEMO_DB_PASSWORD ?? "demo_password"
    psql -h "127.0.0.1" -p 5433 -U "vland" -d "vland_policy" -c "DROP SCHEMA public CASCADE; CREATE SCHEMA public;" 2>$null
} else {
    Write-Host "   (psql khong tim thay - bo qua, dung SQLite fallback)"
}

Write-Host "==> [3/5] Reset SQLite demo database..." -ForegroundColor Cyan
Remove-Item -Path "./data/app.db" -Force -ErrorAction SilentlyContinue
Remove-Item -Path "./data/*.db-journal" -Force -ErrorAction SilentlyContinue
Remove-Item -Path "./data/*.db-wal" -Force -ErrorAction SilentlyContinue

Write-Host "==> [4/5] Xoa PDF tham khao cu..." -ForegroundColor Cyan
Remove-Item -Path "./data/pre_sales_pdfs" -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item -Path "./data/test_pdfs" -Recurse -Force -ErrorAction SilentlyContinue

Write-Host "==> [5/5] Tai tao schema + du lieu sach..." -ForegroundColor Cyan
$env:PYTHONIOENCODING = "utf-8"
py -3 -c "
import asyncio

async def create_all():
    from src.db.models import Base
    from src.db.session import engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

asyncio.run(create_all())
print('   Schema 14 tables recreated successfully.')
"

Write-Host ""
Write-Host "✅ DEMO RESET HOAN TAT — moi truong demo da tinh khoi." -ForegroundColor Green
Write-Host "   Chay server:  py -3 -m uvicorn src.main:app --reload"
Write-Host "   Chay demo:    py -3 -m pytest tests/ -q"
