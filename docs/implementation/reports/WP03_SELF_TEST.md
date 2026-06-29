# WP03 SELF-TEST REPORT

- Base SHA: 7ac333d
- Implementation SHA: 34b54d6
- Scope: 12 files (core schema + certificate/alias/exam_subject tables, models, service, constraint tests, fixtures)

## Migration
- PASS — upgrade → downgrade → upgrade on isolated test DB; head at 3d926df7447d
- Dev DB preserved, no downgrade base on dev

## Metadata
- PASS — 6 tables: iam.organization_unit, knowledge.collection, knowledge.collection_acl, core.certificate, core.certificate_alias, core.exam_subject
- include_schemas=True in both context.configure()
- compare_metadata: diff_count=0

## Cold imports
- PASS — `python -c "import api.database; import api.deps; import api.main; print('imports_ok')"` → imports_ok

## Special tests
- PASS — WP03 constraint tests: 10/10 (cert code UNIQUE, name UNIQUE, status CHECK, alias normalized UNIQUE, alias_type CHECK, alias FK, CASCADE, subject code UNIQUE, subject cert+name UNIQUE, subject FK)

## Pytest
- PASS — 49 passed, 0 failed, 0 warnings

## Ruff
- PASS — 0 errors

## Pyright
- PASS — 0 errors, 0 warnings

## API smoke
- live=200 {"status":"ok"}
- ready=200 {"status":"ok","database":"connected"}

## Leak/downstream
- N/A — WP03 has no HTTP auth routes (certificate service is read-only internal)

## Frontend
- build=compiled successfully (2 webpack cache warnings, not errors)
- typecheck=1046/1046 baseline
- lint=7 errors + 3 warnings baseline

## Security/diff
- PASS — git diff --check clean (only pre-existing CRLF warnings on user files)
- No secrets in committed files

## Test cleanup
- PASS — test DB created and destroyed per test module
- Port 8401 released after uvicorn smoke

## Status consistency
- PASS — IMPLEMENTATION_STATUS.md: WP03 completed 34b54d6
- NEXT_TASK.md ready for WP04 (pending status update)

## Validation command
- Exit code: 0 (re-run after pyright fix)

## Overall
- PASS

---

Validation command (final):
```
cmd.exe /c scripts\validate.bat
```
