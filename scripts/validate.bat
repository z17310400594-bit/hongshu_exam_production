@echo off
REM ============================================
REM WP01+ unified validation — Windows version.
REM Fails fast: exits on first non-zero return code.
REM ============================================
setlocal

echo === Ruff ===
python -m ruff check api/ db/
if %errorlevel% neq 0 exit /b %errorlevel%

echo === Pyright ===
python -m pyright api/ db/ --pythonversion 3.12
if %errorlevel% neq 0 exit /b %errorlevel%

echo === Pytest ===
python -m pytest api/tests/ db/tests/ -v
if %errorlevel% neq 0 exit /b %errorlevel%

echo === Alembic check ===
python -m alembic check
if %errorlevel% neq 0 exit /b %errorlevel%

echo.
echo ALL CHECKS PASSED
