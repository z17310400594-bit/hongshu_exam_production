#!/usr/bin/env bash
# WP01+ unified validation script — run before every commit.
# Usage: bash scripts/validate.sh
set -euo pipefail

echo "=== Ruff ==="
python -m ruff check api/ db/

echo ""
echo "=== Pyright ==="
python -m pyright api/ db/ --pythonversion 3.12

echo ""
echo "=== Pytest (API + DB) ==="
python -m pytest api/tests/ db/tests/ -v

echo ""
echo "=== Alembic current ==="
python -m alembic current

echo ""
echo "=== Typecheck (frontend) ==="
npm run typecheck --silent 2>&1 | tail -3

echo ""
echo "=== Lint (frontend) ==="
npm run lint --silent 2>&1 | tail -3

echo ""
echo "=== Build H5 ==="
npm run build:h5 --silent 2>&1 | tail -3

echo ""
echo "ALL CHECKS PASSED"
