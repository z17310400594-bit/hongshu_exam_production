@echo off
setlocal enabledelayedexpansion

echo [1/4] Ruff
python -m ruff check api/ db/
if %errorlevel% neq 0 exit /b %errorlevel%

echo [2/4] Pyright
python -m pyright api/ db/ --pythonversion 3.12
if %errorlevel% neq 0 exit /b %errorlevel%

echo [3/4] Pytest
python -m pytest api/tests/ db/tests/ -q
if %errorlevel% neq 0 exit /b %errorlevel%

echo [4/4] Alembic check
python -m alembic check
if %errorlevel% neq 0 exit /b %errorlevel%

echo.
echo ALL CHECKS PASSED
