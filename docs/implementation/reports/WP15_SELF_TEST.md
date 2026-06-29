# WP15 SELF-TEST REPORT

Base SHA: `origin/feat/v2-knowledge-platform` + local WP06-WP14 uncommitted work

Implementation SHA: `local-not-committed`

Scope: WP15 MVP only — dual-read/golden/security acceptance framework. This package does not switch traffic, run production-scale migration/performance tests, or claim final business sign-off for a real 100-case golden set.

Key files:

- `api/services/acceptance.py`
- `api/tests/test_acceptance.py`
- `scripts/wp15_acceptance.py`
- `docs/implementation/evaluation/wp15_golden_cases.sample.jsonl`
- `docs/implementation/evaluation/WP15_USAGE.md`
- `docs/implementation/work-packages/WP15.md`
- `docs/implementation/IMPLEMENTATION_STATUS.md`
- `docs/implementation/NEXT_TASK.md`

Requirements coverage: PASS 6/6, see `docs/implementation/work-packages/WP15.md`.

## Migration / Metadata

WP15 did not add or modify database schema.

Command:

```bash
VIRTUAL_ENV=/Users/zzp/Documents/chat/hongshu_exam_production/.venv PATH=/Users/zzp/Documents/chat/hongshu_exam_production/.venv/bin:$PATH .venv/bin/python -m alembic current
```

Exit code: 0

Key output:

```text
c6f1a2b9d304 (head)
```

Command:

```bash
VIRTUAL_ENV=/Users/zzp/Documents/chat/hongshu_exam_production/.venv PATH=/Users/zzp/Documents/chat/hongshu_exam_production/.venv/bin:$PATH .venv/bin/python -m alembic check
```

Exit code: 0

Key output:

```text
No new upgrade operations detected.
```

Migration: PASS

Metadata: PASS

## Cold imports

Command:

```bash
VIRTUAL_ENV=/Users/zzp/Documents/chat/hongshu_exam_production/.venv PATH=/Users/zzp/Documents/chat/hongshu_exam_production/.venv/bin:$PATH .venv/bin/python -c "import api.services.acceptance; print('wp15_imports_ok')"
```

Exit code: 0

Key output:

```text
wp15_imports_ok
```

Cold imports: PASS

## Special tests

Command:

```bash
VIRTUAL_ENV=/Users/zzp/Documents/chat/hongshu_exam_production/.venv PATH=/Users/zzp/Documents/chat/hongshu_exam_production/.venv/bin:$PATH .venv/bin/python -m pytest api/tests/test_acceptance.py -q
```

Exit code: 0

Key output:

```text
5 passed in 0.46s
```

Coverage:

- clean sample passes structured/citation/leak/no-evidence gates
- missing citation + restricted leak fails as expected
- difference classification covers `old_wrong`, `new_wrong`, `business_ambiguous`, `data_missing`, `security_leak`
- secret scan redacts key previews
- CLI evaluates sample JSONL successfully

Special tests: PASS

## Golden / comparison CLI

Command:

```bash
VIRTUAL_ENV=/Users/zzp/Documents/chat/hongshu_exam_production/.venv PATH=/Users/zzp/Documents/chat/hongshu_exam_production/.venv/bin:$PATH .venv/bin/python scripts/wp15_acceptance.py evaluate docs/implementation/evaluation/wp15_golden_cases.sample.jsonl
```

Exit code: 0

Key output:

```json
{
  "status": "pass",
  "metrics": {
    "totalCases": 3,
    "structuredAccuracy": 1.0,
    "citationAccuracy": 1.0,
    "restrictedLeakRate": 0.0,
    "noEvidenceFacts": 0
  }
}
```

Golden/comparison CLI: PASS

## Pytest / Ruff / Pyright

Command:

```bash
VIRTUAL_ENV=/Users/zzp/Documents/chat/hongshu_exam_production/.venv PATH=/Users/zzp/Documents/chat/hongshu_exam_production/.venv/bin:$PATH .venv/bin/python -m pytest api/tests db/tests -q
```

Exit code: 0

Key output:

```text
138 passed in 57.94s
```

Command:

```bash
VIRTUAL_ENV=/Users/zzp/Documents/chat/hongshu_exam_production/.venv PATH=/Users/zzp/Documents/chat/hongshu_exam_production/.venv/bin:$PATH .venv/bin/python -m ruff check api db scripts/wp15_acceptance.py
```

Exit code: 0

Key output:

```text
All checks passed!
```

Command:

```bash
VIRTUAL_ENV=/Users/zzp/Documents/chat/hongshu_exam_production/.venv PATH=/Users/zzp/Documents/chat/hongshu_exam_production/.venv/bin:$PATH .venv/bin/python -m pyright api db --pythonversion 3.12
```

Exit code: 0

Key output:

```text
0 errors, 0 warnings, 0 informations
```

Pytest: PASS

Ruff: PASS

Pyright: PASS

## API smoke

WP15 did not add or modify API routes. Real API smoke was not rerun for this pure acceptance-framework package; WP14 generation route smoke remains the latest API-route smoke evidence.

API smoke: NOT RUN for MVP non-API package.

Leak/downstream: PASS by WP15 framework tests and secret scan; no runtime retrieval path was modified in this package.

## Frontend

WP15 did not modify frontend source.

Frontend: NOT RUN for MVP backend/tooling package, per `docs/implementation/MVP_PLAN_WP06_PLUS.md`.

## Security / diff

Command:

```bash
VIRTUAL_ENV=/Users/zzp/Documents/chat/hongshu_exam_production/.venv PATH=/Users/zzp/Documents/chat/hongshu_exam_production/.venv/bin:$PATH .venv/bin/python scripts/wp15_acceptance.py secret-scan api db src scripts .env.example .env.development .env.production .env.test
```

Exit code: 0

Key output:

```json
{
  "findings": [],
  "status": "pass"
}
```

Command:

```bash
git diff --check
```

Exit code: 0

Security/diff: PASS

## Test cleanup

- No temporary DB, port, process, or temp file was created by WP15.
- All WP15 tests are fixture/JSONL based.

Test cleanup: PASS

## Status consistency

Updated:

- `docs/implementation/work-packages/WP15.md`
- `docs/implementation/IMPLEMENTATION_STATUS.md`
- `docs/implementation/NEXT_TASK.md`
- `docs/implementation/reports/WP15_SELF_TEST.md`

Status consistency: PASS

Validation command exit code: N/A — equivalent MVP gates were run individually and recorded above. Full `scripts/validate.sh` is not used as a single PASS signal in this branch because the project has known frontend baseline typecheck/lint failures and WP15 did not modify frontend code.

Overall: PASS
