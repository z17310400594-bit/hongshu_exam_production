# WP13 SELF-TEST REPORT

## Summary

- Base SHA: `feat/v2-knowledge-platform` local state after WP12 (`c6f1a2b9d304` Alembic head)
- Implementation SHA: `local-not-committed`
- Scope: Taro frontend low-risk V2 certificate/exam adoption
  - `.env.development`
  - `.env.example`
  - `.env.production`
  - `.env.test`
  - `src/types/api.ts`
  - `src/services/httpClient.ts`
  - `src/services/certificateApi.ts`
  - `src/services/dify.ts`
  - `src/hooks/useCertPresets.ts`
  - `src/pages/workbench/components/ExamArticle/index.tsx`
  - `docs/implementation/work-packages/WP13.md`
  - `docs/implementation/reports/WP13_SELF_TEST.md`
  - `docs/implementation/IMPLEMENTATION_STATUS.md`
  - `docs/implementation/NEXT_TASK.md`
- Requirements coverage: 6/6 in `docs/implementation/work-packages/WP13.md`
- Overall: PASS with known pre-existing frontend type/lint baseline

## MVP Scope Notes

WP13 follows `docs/implementation/MVP_PLAN_WP06_PLUS.md`.

Implemented:

- Added V2 frontend DTOs and `ApiError`.
- Added `apiFetch()` with `X-Request-ID`, `X-Org-Code`, optional Bearer token, and V2 error parsing.
- Switched the ExamArticle certificate dropdown to V2 by default.
- Added `TARO_APP_USE_V2_CERTIFICATE_API=false` fallback to legacy `policy-api /query/certs`.
- Selecting a V2 certificate now refreshes exam date from `/api/v2/certificates/{code}/exam-events`.
- Removed hard-coded Dify API key from tracked frontend code/config; generation still uses the existing Dify workflow protocol when a runtime key is provided.

Deferred:

- No `/api/v2/generations` or SSE frontend integration; WP14 owns generation backendization.
- No full page refactor or Picker migration.
- No real login integration; MVP identity comes from `TARO_APP_ORG_CODE`, defaulting to `org_teaching_materials` for local development.

## Frontend Build

First sandboxed attempt:

```text
npm run build:h5
```

Result:

```text
Taro/Rust native system-configuration panic in sandbox and command was interrupted after it appeared stuck.
```

Rerun outside sandbox:

```bash
npm run build:h5
```

Result:

```text
✔ Webpack
Compiled successfully in 26.57s
webpack 5.91.0 compiled with 2 warnings in 26598 ms
```

Warnings are the known bundle size warnings:

```text
AssetsOverSizeLimitWarning: js/861.e841c550.js (262 KiB)
EntrypointsOverSizeLimitWarning: app (281 KiB)
```

## Frontend Typecheck

Command:

```bash
npm run typecheck -- --pretty false
```

Result:

```text
exit code 2
```

This matches the known frontend baseline dominated by Taro/node_modules type declaration issues. To check project files:

```bash
npm run typecheck -- --pretty false 2>&1 | rg "^(src|config)/"
```

Result:

```text
config/index.ts(7,55): error TS6198: All destructured elements are unused.
```

Conclusion:

- No new `src/` TypeScript error from WP13 files.
- The remaining project-file error is the already documented baseline `config/index.ts`.

## Frontend Lint

Command:

```bash
npm run lint -- --format unix
```

Result:

```text
8 problems
```

Output:

```text
ExamArticle/index.tsx:141:10 Unexpected use of 'confirm'
ExamArticle/index.tsx:238:12 Unexpected use of 'confirm'
ExamArticle/index.tsx:491:6 React Hook useCallback has a missing dependency: 'openRewrite'
ExamArticle/index.tsx:659:14 <select> is forbidden
ExamArticle/index.tsx:673:14 <select> is forbidden
ExamArticle/index.tsx:774:14 <select> is forbidden
ExamArticle/index.tsx:867:20 <select> is forbidden
TopicFinder/index.tsx:102:12 <select> is forbidden
```

Conclusion:

- Known lint baseline was 7 errors + 3 warnings.
- WP13 result is 7 errors + 1 warning.
- No new lint regression; warning count decreased by fixing new hook dependency warnings.

## Backend Regression Gates

Although WP13 is frontend-only, backend gates were rerun because WP06-WP12 remain uncommitted in the same worktree.

Command:

```bash
VIRTUAL_ENV=/Users/zzp/Documents/chat/hongshu_exam_production/.venv \
PATH=/Users/zzp/Documents/chat/hongshu_exam_production/.venv/bin:$PATH \
.venv/bin/python -m pytest api/tests db/tests -q
```

Result:

```text
130 passed in 38.66s
```

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

## API / Manual Flow Coverage

No real browser E2E runner exists in this repo. Coverage is by build + static contract:

- `useCertPresets()` uses V2 by default and maps `certificate.code` into `ExamCategory.id`.
- `ExamArticle` shows `考试类型（V2）` when V2 flag is enabled.
- First loaded certificate applies the list `nextExam` date and then refreshes from `/exam-events`.
- Manual certificate selection also calls `resolveExamDate()` and updates `store.examDate`.
- `TARO_APP_USE_V2_CERTIFICATE_API=false` switches hook back to the old `fetchLegacyCerts()` path.

## Security / Secrets

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
rg -n "app-[A-Za-z0-9]|Bearer\s+[A-Za-z0-9._-]+|DB_PASSWORD=|MINIO_SECRET_KEY=|api[_-]?key|secret|password|DIFY_API_KEY" api db src config docs/implementation infra .env.example .env.development .env.production .env.test -S --glob '!**/node_modules/**' --glob '!dist/**'
```

Result:

```text
No app-... Dify key remains in src or tracked frontend env files.
Matches are empty Dify env variable names, security guidance text, existing local-dev placeholders in .env.example, config field names, and test placeholder values.
```

Command:

```bash
git status --short --branch
```

Result:

```text
Branch: feat/v2-knowledge-platform
WP06-WP13 remain local-not-committed.
```

## Test Cleanup

PASS.

- `npm run build:h5` generated ignored `dist/` output only.
- No new test databases beyond backend regression test fixtures; pytest fixtures dropped their test DBs.
- No service process left running.

## Status Consistency

PASS.

- `IMPLEMENTATION_STATUS.md` marks WP13 completed local-not-committed.
- `NEXT_TASK.md` routes to WP14.
- No commit was created, per current user instruction to commit later together.
