@echo off
setlocal EnableExtensions EnableDelayedExpansion
REM Cross-platform Python launcher for AI log hooks (Windows cmd.exe).
REM Prefer the repository virtual environment, then try Python launchers on PATH.
REM Exits 0 silently if no Python is found - hooks must never block the AI tool.

if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" --version >nul 2>nul
  if not errorlevel 1 (
    ".venv\Scripts\python.exe" %*
    exit /b !ERRORLEVEL!
  )
)

where python >nul 2>nul
if not errorlevel 1 (
  python --version >nul 2>nul
  if not errorlevel 1 (
    python %*
    exit /b !ERRORLEVEL!
  )
)

where python3 >nul 2>nul
if not errorlevel 1 (
  python3 --version >nul 2>nul
  if not errorlevel 1 (
    python3 %*
    exit /b !ERRORLEVEL!
  )
)

where py >nul 2>nul
if not errorlevel 1 (
  py -3 --version >nul 2>nul
  if not errorlevel 1 (
    py -3 %*
    exit /b !ERRORLEVEL!
  )
)

exit /b 0
