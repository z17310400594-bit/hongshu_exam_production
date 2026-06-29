# WP14 SELF-TEST REPORT

Base SHA: `origin/feat/v2-knowledge-platform` + local WP06-WP13 uncommitted work

Implementation SHA: `local-not-committed`

Scope: WP14 MVP only — route generation through backend, persist generation run/citation/output, expose citations to frontend review UI, remove browser-side Dify key/path.

Key files:

- `api/config.py`
- `api/main.py`
- `api/services/generation_workflow.py`
- `api/tests/test_generation_workflow.py`
- `src/services/dify.ts`
- `src/services/generationApi.ts`
- `src/types/exam-article.ts`
- `src/store/examArticleStore.ts`
- `src/pages/workbench/components/ExamArticle/index.tsx`
- `src/pages/workbench/components/ExamArticle/index.scss`
- `.env.development`, `.env.production`, `.env.test`, `.env.example`
- `docs/implementation/work-packages/WP14.md`
- `docs/implementation/IMPLEMENTATION_STATUS.md`
- `docs/implementation/NEXT_TASK.md`

Requirements coverage: PASS 7/7, see `docs/implementation/work-packages/WP14.md`.

## Migration / Metadata

WP14 did not add new tables or Alembic revisions; it reuses WP10 `generation.run/citation/output`.

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
VIRTUAL_ENV=/Users/zzp/Documents/chat/hongshu_exam_production/.venv PATH=/Users/zzp/Documents/chat/hongshu_exam_production/.venv/bin:$PATH .venv/bin/python -c "import api.config; import api.services.generation_workflow; import api.main; print('wp14_imports_ok')"
```

Exit code: 0

Key output:

```text
wp14_imports_ok
```

Cold imports: PASS

## Special tests

Command:

```bash
VIRTUAL_ENV=/Users/zzp/Documents/chat/hongshu_exam_production/.venv PATH=/Users/zzp/Documents/chat/hongshu_exam_production/.venv/bin:$PATH .venv/bin/python -m pytest api/tests/test_generation_workflow.py -q
```

Exit code: 0

Key output:

```text
3 passed in 7.59s
```

Coverage:

- create `/api/v2/generations` through service and persist run/citation/output
- fetch `/api/v2/generations/{runId}` through service
- anonymous 401
- denied 403 without leaking source title/body
- allowed 200 with citation payload
- unknown run 404
- restricted source stays `confidentiality=restricted` and `modelRoute=internal`

Special tests: PASS

## Pytest / Ruff / Pyright

Command:

```bash
VIRTUAL_ENV=/Users/zzp/Documents/chat/hongshu_exam_production/.venv PATH=/Users/zzp/Documents/chat/hongshu_exam_production/.venv/bin:$PATH .venv/bin/python -m pytest api/tests db/tests -q
```

Exit code: 0

Key output:

```text
133 passed in 33.31s
```

Command:

```bash
VIRTUAL_ENV=/Users/zzp/Documents/chat/hongshu_exam_production/.venv PATH=/Users/zzp/Documents/chat/hongshu_exam_production/.venv/bin:$PATH .venv/bin/python -m ruff check api db
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

Command:

```bash
PYTHONPATH=/Users/zzp/Documents/chat/hongshu_exam_production VIRTUAL_ENV=/Users/zzp/Documents/chat/hongshu_exam_production/.venv PATH=/Users/zzp/Documents/chat/hongshu_exam_production/.venv/bin:$PATH .venv/bin/python /private/tmp/wp14_smoke.py
```

Exit code: 0

Key output:

```json
{"allowed": 200, "anonymous": 401, "citation_asset": "WP14_SMOKE_INTERNAL_SOURCE", "denied": 403, "denied_leak_check": "PASS", "fetched": 200, "live": 200, "ready": 200, "run_id": 1, "unknown": 404}
```

Notes:

- The temporary smoke script created isolated DB `knowledge_platform_v2_smoke_wp14`.
- It started real `uvicorn api.main:app` on `127.0.0.1:18087`.
- It terminated the service and dropped the smoke DB in `finally`.
- `/private/tmp/wp14_smoke.py` was deleted after the run.

API smoke: live=200, ready=200/database connected, anonymous=401, deny=403, allow=200, fetch=200, unknown=404

Leak/downstream: PASS — denied response did not include source asset code or fragment body sample.

## Frontend

Command:

```bash
npm run build:h5
```

Exit code: 0

Key output:

```text
Webpack compiled successfully
webpack 5.91.0 compiled with 2 warnings
```

Warnings are the existing size warnings:

- `AssetsOverSizeLimitWarning`
- `EntrypointsOverSizeLimitWarning`

Command:

```bash
npm run typecheck -- --pretty false
```

Exit code: 2

Result: known baseline failure from Taro/node_modules `.d.ts` conflicts plus existing `config/index.ts(7,55)` unused destructuring.

Scoped command:

```bash
./node_modules/.bin/tsc --noEmit --pretty false --skipLibCheck true
```

Exit code: 2

Key output:

```text
config/index.ts(7,55): error TS6198: All destructured elements are unused.
```

Interpretation: no new `src/` type errors from WP14.

Command:

```bash
npm run lint -- --format unix
```

Exit code: 1

Key output: 8 problems total = 7 errors + 1 warning, matching the existing frontend baseline shape:

- `confirm` restricted global in `ExamArticle`
- `<select>` forbidden in `ExamArticle` / `TopicFinder`
- one existing hook dependency warning

Frontend: PASS for MVP/no-regression scope — build OK, no new scoped type/lint issues.

## Security / diff

Command:

```bash
git diff --check
```

Exit code: 0

Command:

```bash
rg -n "(sk-[A-Za-z0-9_-]{20,}|app-[A-Za-z0-9_-]{20,}|Bearer\\s+[A-Za-z0-9._-]{20,}|DIFY_API_KEY\\s*=\\s*[^\\s#]+|TARO_APP_DIFY|password\\s*=\\s*[^\\s#]+|secret\\s*=\\s*[^\\s#]+)" api db src config docs/implementation infra .env.example .env.development .env.production .env.test -S
```

Exit code: 0

Findings:

- No real secret/key found.
- Matches were documentation references to the old Dify-key risk in `docs/implementation/DECISIONS.md` and `docs/implementation/work-packages/WP13.md`.

Command:

```bash
rg -n "DIFY_API_KEY|TARO_APP_DIFY|/v1/workflows/run|Authorization|Bearer" src .env.example .env.development .env.production .env.test -S
```

Exit code: 0

Findings:

- No frontend Dify env or direct workflow URL remains.
- Only normal runtime `Authorization: Bearer ${token}` construction in `src/services/httpClient.ts`.

Security/diff: PASS

## Test cleanup

- Smoke DB `knowledge_platform_v2_smoke_wp14` dropped by script.
- Smoke uvicorn process terminated by script.
- Temporary `/private/tmp/wp14_smoke.py` deleted.

Test cleanup: PASS

## Status consistency

Updated:

- `docs/implementation/work-packages/WP14.md`
- `docs/implementation/IMPLEMENTATION_STATUS.md`
- `docs/implementation/NEXT_TASK.md`
- `docs/implementation/reports/WP14_SELF_TEST.md`

Status consistency: PASS

Validation command exit code: N/A — `scripts/validate.sh` is not used as a single PASS signal in this branch because the project has known frontend baseline typecheck/lint failures; equivalent MVP gates were run individually and recorded above.

Overall: PASS
