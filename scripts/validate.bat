@echo off
REM ============================================
REM WP01+ unified validation — Windows version.
REM Runs every check except those that need Bash.
REM ============================================

echo === Ruff ===
python -m ruff check api/ db/
if %errorlevel% neq 0 exit /b %errorlevel%

echo === Pyright ===
python -m pyright api/ db/ --pythonversion 3.12
if %errorlevel% neq 0 exit /b %errorlevel%

echo === Pytest ===
python -m pytest api/tests/ db/tests/ -v
if %errorlevel% neq 0 exit /b %errorlevel%

echo === Alembic current ===
python -m alembic current

echo.
echo ALL CHECKS PASSED
