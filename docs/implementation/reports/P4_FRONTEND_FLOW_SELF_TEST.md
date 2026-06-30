# P4 Frontend Business Flow Self Test

Date: 2026-06-30

Scope: P4 only — API/frontend business-loop enhancement for the current V2 MVP sample data. This package adds a Taro H5 entry for the P2/P3 real-data loop and does not change database schema, migrations, seed data, Dify keys, MinIO, or production feature flags.

## What changed

- Added a V2 business-flow API facade:
  - `src/services/v2BusinessFlowApi.ts`
- Added shared frontend DTOs for:
  - certificate detail
  - eligibility evaluation
  - knowledge search
  - question bank
  - generation result/citations
- Added a new workbench page:
  - `src/pages/workbench/components/V2BusinessFlow/index.tsx`
  - `src/pages/workbench/components/V2BusinessFlow/index.scss`
- Added a left-nav entry:
  - label: `V2闭环`
  - feature flag: `TARO_APP_SHOW_V2_FLOW=false` hides the entry/page
- Kept existing rollback path:
  - existing `TARO_APP_USE_V2_CERTIFICATE_API=false` still controls the earlier certificate dropdown fallback.

## Runtime behavior

The page uses the backend as the source of truth. The frontend stores only demo identifiers/config defaults, not policy facts, exam dates, document text, Dify keys, or private source data.

Default demo identifiers:

| Setting | Default | Purpose |
| --- | --- | --- |
| `TARO_APP_V2_FLOW_CERTIFICATE_CODE` | `pharmacist_licensed` | Complete P2/P3 sample chain |
| `TARO_APP_V2_FLOW_GAP_CERTIFICATE_CODE` | `cls1_constructor` | Known data-gap sample |
| `TARO_APP_V2_FLOW_PAPER_CODE` | `P2_PHARMACIST_YAO1_SAMPLE` | Question-bank sample |
| `TARO_APP_V2_FLOW_COLLECTION_CODE` | `coll_internal` | Internal knowledge collection |
| `TARO_APP_V2_FLOW_RESTRICTED_ORG_CODE` | `org_operations` | Permission-denial sample |
| `TARO_APP_V2_FLOW_KNOWLEDGE_QUERY` | `AUC` | Knowledge retrieval sample |
| `TARO_APP_V2_FLOW_AS_OF` | `2026-06-30` | Deterministic eligibility evaluation |

Displayed cards:

1. certificate detail
2. 2026 exam event/phases
3. eligibility decision with citations
4. knowledge search hit with citation source
5. question-bank sample with source asset
6. restricted access denial without leaking private title/content
7. known first-constructor eligibility data gap
8. optional backend generation run with citations

## Verification

Commands run:

```powershell
npm.cmd run build:h5
npm.cmd run typecheck
$out = npm.cmd run typecheck 2>&1; $out | Select-String "src\\|src/"
npm.cmd run lint
npx.cmd eslint src\services\v2BusinessFlowApi.ts src\pages\workbench\components\V2BusinessFlow\index.tsx src\pages\workbench\components\LeftNav.tsx src\pages\workbench\index.tsx src\store\workbenchStore.ts src\types\api.ts
py -m pytest api\tests db\tests -q
py scripts\p3_golden_eval.py docs\implementation\evaluation\p3_golden_cases.batch001.jsonl
py -m ruff check api db scripts
py -m pyright api db --pythonversion 3.12
```

Results:

| Gate | Result | Notes |
| --- | --- | --- |
| H5 build | PASS | Webpack compiled successfully; existing asset-size warnings remain. |
| Frontend typecheck | BASELINE FAIL | Full command still fails on existing Taro/node_modules/config type issues. Filtered `src\|src/` output was empty, so P4 introduced no src-level type errors. |
| Frontend lint | BASELINE FAIL | Full command still reports existing `ExamArticle`/`TopicFinder` issues: `confirm`, forbidden `<select>`, hook dependency. |
| P4 scoped lint | PASS | Changed/new P4 files pass eslint. |
| Backend tests | PASS | `149 passed in 9.99s`. |
| P3 golden set | PASS | 10/10 structured accuracy; citation accuracy 1.0; restricted leak rate 0.0. |
| Ruff | PASS | `All checks passed!` |
| Pyright | PASS | `0 errors, 0 warnings, 0 informations`. |

## Security and data-leak checks

- The frontend does not store or read Dify keys.
- Generation is created through `/api/v2/generations`; the browser only receives task/result/citation data.
- Restricted knowledge search is intentionally executed with `X-Org-Code: org_operations`; the UI treats the expected 403 as success and displays only the error code/message, not asset title or fragment content.
- The page does not connect directly to DB, MinIO, old policy-api, or Dify.

## Known limitations

- Question bank still uses the existing governed endpoint `/papers/{paper_code}/questions`, not a new `/api/v2/papers/...` alias. It is acceptable for P4 because ACL and source-asset governance are already enforced, but a future cleanup can add a V2 alias for naming consistency.
- The page is a validation/business-loop panel, not the final business UI. It is intentionally small so P5/P6 can continue without waiting for a full design pass.
- Full frontend lint/typecheck remain blocked by pre-existing project baseline issues unrelated to P4.

## Next recommended step

Proceed to `P5` only after the user confirms P4 UI behavior is acceptable in H5, or run `P2-expand` first if the business wants a richer subject/certificate dataset before model-gateway integration.
