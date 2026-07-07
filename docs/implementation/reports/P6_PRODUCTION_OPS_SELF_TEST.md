# P6 运维生产化补证自测报告

Date: 2026-06-30  
Scope: P6 — 数据库/对象存储恢复证据、恢复对比、API 性能/监控摘要、回滚/旧库只读报告入口。

## 变更范围

- `api/services/ops_evidence.py`
  - 关键表 manifest 采集；
  - 恢复前后 row count / hash / reference 对比；
  - API 样本转监控指标：5xx、P95、检索命中、权限拒绝、生成失败、缺引用。
- `scripts/p6_ops.py`
  - `db-manifest`
  - `compare-restore`
  - `summarize-api-samples`
- `api/tests/test_ops_evidence.py`
  - 覆盖恢复对比、失败差异、API 监控摘要、CLI。
- `docs/implementation/release/P6_USAGE.md`
  - P6 执行说明。
- `docs/implementation/release/p6_*.sample.*`
  - manifest 和 API 样本。
- `docs/implementation/reports/P6_*.sample.md`
  - 上线、恢复、旧库退役决策模板。

## 自测命令

```powershell
py -m pytest api\tests\test_ops_evidence.py api\tests\test_release_readiness.py -q
py -m ruff check api\services\ops_evidence.py api\tests\test_ops_evidence.py scripts\p6_ops.py
py -m pyright api\services\ops_evidence.py api\tests\test_ops_evidence.py scripts\p6_ops.py --pythonversion 3.12
py scripts\p6_ops.py compare-restore --source docs\implementation\release\p6_db_manifest.source.sample.json --restored docs\implementation\release\p6_db_manifest.restored.sample.json
py scripts\p6_ops.py summarize-api-samples --input docs\implementation\release\p6_api_samples.sample.jsonl
py scripts\wp16_release.py docs\implementation\release\wp16_release_plan.sample.json
py scripts\p6_ops.py db-manifest --output .tmp\p6_db_manifest.local.json
py -m pytest api\tests db\tests -q
py -m ruff check api db scripts
py -m pyright api db scripts --pythonversion 3.12
py scripts\p3_golden_eval.py docs\implementation\evaluation\p3_golden_cases.batch001.jsonl
npm.cmd run build:h5
rg -n "(sk-[A-Za-z0-9_-]{20,}|app-[A-Za-z0-9_-]{20,}|Bearer\s+[A-Za-z0-9._-]{20,}|DIFY_API_KEY\s*=\s*[^\s#<]+|TARO_APP_DIFY|password\s*=\s*[^\s#]+|secret\s*=\s*[^\s#]+)" api db src config docs\implementation infra .env.example .env.development .env.production .env.test -S
```

## 当前结果

| Gate | Result | Evidence |
| --- | --- | --- |
| 定向测试 | PASS | `8 passed` |
| 定向 ruff | PASS | `All checks passed!` |
| 定向 pyright | PASS | `0 errors, 0 warnings, 0 informations` |
| 恢复样例对比 | PASS | rowCountsMatch=true, hashesMatch=true, referencesValid=true, tableCount=4 |
| API 样本摘要 | PASS | sampleCount=7, P95=420ms, 5xx=0, retrievalHit=1.0, permissionDenied=0, generationFailure=0, missingCitation=0 |
| WP16 发布门禁样例 | PASS | `status=pass`, summary passed=6 failed=0 total=6 |
| 本地 DB manifest smoke | PASS | 当前本地 V2 库关键表全部 present；generation/fragment/question/chapter 引用检查 invalidCount 均为 0；输出仅写入 `.tmp`，不提交环境 manifest |
| 全量后端测试 | PASS | `160 passed in 11.18s` |
| 全量 ruff | PASS | `All checks passed!` |
| pyright | PASS | `0 errors, 0 warnings, 0 informations` |
| P3 黄金集 | PASS | `status=pass`, structuredAccuracy 1.0, citationAccuracy 1.0, restrictedLeakRate 0.0 |
| H5 build | PASS | `webpack compiled with 2 warnings`，仅既有 asset/entrypoint size warning |
| Secret scan | PASS | 仅命中历史文档/测试里的占位说明：WP13/WP14/P5 文档、`test_acceptance.py` 的 fake key 测试和扫描命令文本；未发现真实 Dify key |

## 真实执行说明

P6 本次不切真实生产 feature flag，不修改旧库权限，也不删除旧库。真实上线前必须在独立恢复库/只读副本上执行：

1. 源库 `db-manifest`；
2. 恢复库 `db-manifest`；
3. `compare-restore`；
4. API 样本压测或 smoke 后 `summarize-api-samples`；
5. 回填 `wp16_release_plan.*.json`；
6. `wp16_release.py` 通过后再进入 P7 灰度。
