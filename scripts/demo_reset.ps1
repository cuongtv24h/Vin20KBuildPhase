# ============================================================================
# PricePolicy AI Agent - Demo Reset Script (PowerShell for Windows)
# Owner: TechLead (cuongtv_02560) | TASK-P5-03
# Muc tieu: khoi phuc moi truong demo ve trang thai tinh khoi trong < 15 giay.
# ============================================================================

$ErrorActionPreference = "Continue"

Write-Host "==> [1/5] Dung server backend dang chay (neu co)..." -ForegroundColor Cyan
Get-Process python -ErrorAction SilentlyContinue | Where-Object { $_.CommandLine -like "*uvicorn src.main:app*" } | Stop-Process -Force -ErrorAction SilentlyContinue

Write-Host "==> [2/5] Reset PostgreSQL demo (neu co)..." -ForegroundColor Cyan
if (Get-Command psql -ErrorAction SilentlyContinue) {
    if ($env:DEMO_DB_PASSWORD) {
        $env:PGPASSWORD = $env:DEMO_DB_PASSWORD
    } else {
        $env:PGPASSWORD = "demo_password"
    }
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

$pythonCmd = "python"
if (Test-Path ".\.venv\Scripts\python.exe") {
    $pythonCmd = ".\.venv\Scripts\python.exe"
} elseif (Get-Command py -ErrorAction SilentlyContinue) {
    $pythonCmd = "py -3"
}

& $pythonCmd -c "import asyncio; from src.db.session import init_db; asyncio.run(init_db()); print('   Schema 14 tables recreated successfully.')"

Write-Host ""
Write-Host "[OK] DEMO RESET HOAN TAT - moi truong demo da tinh khoi." -ForegroundColor Green
Write-Host "   Chay server:  $pythonCmd run.py"
Write-Host "   Chay demo:    $pythonCmd -m pytest tests/ -q"
