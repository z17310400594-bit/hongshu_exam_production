# WP12 SELF-TEST REPORT

## Summary

- Base SHA: `feat/v2-knowledge-platform` local state after WP11 (`c6f1a2b9d304` Alembic head)
- Implementation SHA: `local-not-committed`
- Scope: API V2 MVP query layer only
  - `api/services/v2_api.py`
  - `api/main.py`
  - `api/tests/test_v2_api.py`
  - `docs/implementation/work-packages/WP12.md`
  - `docs/implementation/reports/WP12_SELF_TEST.md`
  - `docs/implementation/IMPLEMENTATION_STATUS.md`
  - `docs/implementation/NEXT_TASK.md`
- Requirements coverage: 7/7 in `docs/implementation/work-packages/WP12.md`
- Overall: PASS

## MVP Scope Notes

WP12 follows `docs/implementation/MVP_PLAN_WP06_PLUS.md`.

Implemented:

- `GET /api/v2/certificates`
- `GET /api/v2/certificates/{certificateCode}`
- `GET /api/v2/certificates/{certificateCode}/exam-events`
- `POST /api/v2/eligibility/evaluate`
- `POST /api/v2/knowledge/search`
- V2 request id and error envelope for auth, not found, bad request, and database unavailable paths.

Deferred by MVP plan:

- `/api/v2/generations`, SSE events, approval endpoints.
- Dedicated read-only DB role.
- Production search ranking, vector recall, full pagination/performance work.
- Frontend integration; WP13 owns Taro low-risk adoption.

## Special Tests

Command:

```bash
VIRTUAL_ENV=/Users/zzp/Documents/chat/hongshu_exam_production/.venv \
PATH=/Users/zzp/Documents/chat/hongshu_exam_production/.venv/bin:$PATH \
.venv/bin/python -m pytest api/tests/test_v2_api.py -q
```

Result:

```text
5 passed in 2.11s
```

Covered:

- certificate query returns alias and next exam.
- eligibility response contains `decision`, `requirements`, `citations`.
- knowledge search filters by ACL, collection, KP, asset type, status and validity.
- V2 routes require identity and use stable error model/requestId.
- simulated database failure returns `503 DATABASE_UNAVAILABLE`.

## Full Pytest

Command:

```bash
VIRTUAL_ENV=/Users/zzp/Documents/chat/hongshu_exam_production/.venv \
PATH=/Users/zzp/Documents/chat/hongshu_exam_production/.venv/bin:$PATH \
.venv/bin/python -m pytest api/tests db/tests -q
```

Result:

```text
130 passed in 13.43s
```

## Ruff

Command:

```bash
VIRTUAL_ENV=/Users/zzp/Documents/chat/hongshu_exam_production/.venv \
PATH=/Users/zzp/Documents/chat/hongshu_exam_production/.venv/bin:$PATH \
.venv/bin/python -m ruff check api db
```

Result:

```text
All checks passed!
```

## Pyright

Command:

```bash
VIRTUAL_ENV=/Users/zzp/Documents/chat/hongshu_exam_production/.venv \
PATH=/Users/zzp/Documents/chat/hongshu_exam_production/.venv/bin:$PATH \
.venv/bin/python -m pyright api db --pythonversion 3.12
```

Result:

```text
0 errors, 0 warnings, 0 informations
```

## Migration / Alembic

WP12 adds no database schema or migration.

Command:

```bash
VIRTUAL_ENV=/Users/zzp/Documents/chat/hongshu_exam_production/.venv \
PATH=/Users/zzp/Documents/chat/hongshu_exam_production/.venv/bin:$PATH \
.venv/bin/python -m alembic current
```

Result:

```text
c6f1a2b9d304 (head)
```

Command:

```bash
VIRTUAL_ENV=/Users/zzp/Documents/chat/hongshu_exam_production/.venv \
PATH=/Users/zzp/Documents/chat/hongshu_exam_production/.venv/bin:$PATH \
.venv/bin/python -m alembic check
```

Result:

```text
No new upgrade operations detected.
```

## Metadata

Command:

```bash
VIRTUAL_ENV=/Users/zzp/Documents/chat/hongshu_exam_production/.venv \
PATH=/Users/zzp/Documents/chat/hongshu_exam_production/.venv/bin:$PATH \
.venv/bin/python - <<'PY'
from alembic.migration import MigrationContext
from alembic.autogenerate import compare_metadata
from api.database import sync_engine
from api.models import Base
import api.models.iam, api.models.knowledge, api.models.core, api.models.policy, api.models.assessment, api.models.content, api.models.generation, api.models.ingestion

with sync_engine.connect() as conn:
    context = MigrationContext.configure(conn, opts={"include_schemas": True})
    diff = compare_metadata(context, Base.metadata)
print('diff_count=', len(diff))
PY
```

Result:

```text
diff_count= 0
```

## Cold Imports

Command:

```bash
VIRTUAL_ENV=/Users/zzp/Documents/chat/hongshu_exam_production/.venv \
PATH=/Users/zzp/Documents/chat/hongshu_exam_production/.venv/bin:$PATH \
.venv/bin/python -c "import api.database; import api.deps; import api.main; import api.services.v2_api; print('imports_ok')"
```

Result:

```text
imports_ok
```

## Real Uvicorn Smoke

Setup:

- Created isolated DB `knowledge_platform_v2_smoke_wp12`.
- Ran Alembic upgrade to `c6f1a2b9d304`.
- Seeded WP02/WP03/WP06/WP07/WP12 MVP records.
- Started:

```bash
DB_NAME=knowledge_platform_v2_smoke_wp12 \
VIRTUAL_ENV=/Users/zzp/Documents/chat/hongshu_exam_production/.venv \
PATH=/Users/zzp/Documents/chat/hongshu_exam_production/.venv/bin:$PATH \
.venv/bin/python -m uvicorn api.main:app --host 127.0.0.1 --port 18086
```

Probe result:

```text
live (200, {'status': 'ok'})
ready (200, {'status': 'ok', 'database': 'connected'})
anonymous (401, {'error': {'code': 'UNAUTHENTICATED', 'message': 'Missing X-Org-Code header', 'fieldErrors': [], 'requestId': 'req_182dd5e6bcde4b15acf3a97011695843'}})
certs 200 c_constructor_1 WP12_SMOKE_2026 None
eligibility 200 eligible WP12_SMOKE_RULE 1
search 200 SMOKE_FRAGMENT
deny 403 ACCESS_DENIED False
unknown 404 NOT_FOUND
```

Cleanup:

```text
Uvicorn stopped with Ctrl-C.
smoke_db_dropped=knowledge_platform_v2_smoke_wp12
```

## Leak / Downstream

PASS.

- Contract test asserts denied V2 knowledge search does not contain restricted body or requested restricted collection code.
- Real smoke denied path output: `deny 403 ACCESS_DENIED False`, where `False` means the serialized error body did not contain the restricted query/body marker.
- Unauthorized collection requests fail before search SQL returns rows.

## Frontend

Frontend: NOT RUN for MVP backend/API package.

Reason: WP12 did not modify frontend files. Per `docs/implementation/MVP_PLAN_WP06_PLUS.md`, WP06+ backend/API MVP packages may defer full frontend build/typecheck/lint unless the package changes frontend code. WP13 owns the low-risk Taro integration.

## Validation Command

`cmd.exe /c scripts\validate.bat` was not run on this macOS device because `cmd.exe` is unavailable. Equivalent Python backend gates from `validate.bat` were run individually and passed:

- ruff: PASS
- pyright: PASS
- pytest: PASS
- alembic check: PASS

## Security / Diff

PASS.

Command:

```bash
git diff --check
```

Result:

```text
exit code 0
```

Command:

```bash
rg -n "app-[A-Za-z0-9]|Bearer\s+[A-Za-z0-9._-]+|DB_PASSWORD=|MINIO_SECRET_KEY=|api[_-]?key|secret|password" api db docs/implementation infra -S
```

Result:

```text
Only matched security guidance text, config field names, and test placeholder values such as top_secret/secret.
No real .env, Dify key, database password, Bearer token, or generated dependency directory was introduced.
```

Command:

```bash
git status --short --branch
git diff --stat
```

Result:

```text
Branch: feat/v2-knowledge-platform
WP06-WP12 remain local-not-committed.
Tracked diff stat includes api/main.py plus implementation status docs; new WP06-WP12 files are untracked until the final combined commit.
```

## Test Cleanup

PASS.

- `knowledge_platform_v2_test_wp12_api` is dropped by pytest fixture teardown.
- `knowledge_platform_v2_smoke_wp12` was dropped after smoke.
- Uvicorn smoke process was stopped.

## Status Consistency

PASS.

- `IMPLEMENTATION_STATUS.md` marks WP12 completed local-not-committed with 130 tests.
- `NEXT_TASK.md` routes to WP13.
- No commit was created, per current user instruction to commit later together.
