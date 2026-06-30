# P6 运维生产化补证使用说明

P6 的目标是证明 V2 出问题时能恢复、能回滚、能观察。它不直接切生产流量，也不删除旧库；它要求先产生可审计证据，再进入 P7 灰度。

## 1. 生成数据库关键表 manifest

在源库和恢复库分别运行：

```powershell
py scripts\p6_ops.py db-manifest --output docs\implementation\release\p6_db_manifest.source.json
py scripts\p6_ops.py db-manifest --output docs\implementation\release\p6_db_manifest.restored.json
```

manifest 会记录：

- 关键表是否存在；
- 关键表行数；
- 关键表稳定 SHA256；
- 引用关系检查：
  - `generation.citation -> knowledge.fragment`
  - `knowledge.fragment_knowledge_point -> fragment / knowledge_point`
  - `assessment.question_knowledge_point -> question / knowledge_point`
  - `content.chapter_knowledge_point -> chapter / knowledge_point`

生产执行建议在只读副本或恢复演练库上跑，避免在业务高峰对大表做全表 hash。

## 2. 对比恢复结果

```powershell
py scripts\p6_ops.py compare-restore `
  --source docs\implementation\release\p6_db_manifest.source.json `
  --restored docs\implementation\release\p6_db_manifest.restored.json `
  --output docs\implementation\release\p6_restore_comparison.json
```

通过条件：

- `rowCountsMatch=true`
- `hashesMatch=true`
- `referencesValid=true`

这三项可以回填到 `wp16_release_plan.sample.json` 的 `restoreDrill`。

## 3. 汇总 API 性能与监控样本

准备 JSONL 样本，每行一个请求：

```json
{"route":"/api/v2/knowledge/search","statusCode":200,"latencyMs":180,"retrievalHit":true,"requiresCitation":true,"citationCount":1}
{"route":"/api/v2/generations","category":"generation","statusCode":200,"latencyMs":420,"generationStatus":"succeeded","requiresCitation":true,"citationCount":2}
```

运行：

```powershell
py scripts\p6_ops.py summarize-api-samples `
  --input docs\implementation\release\p6_api_samples.sample.jsonl `
  --output docs\implementation\release\p6_api_summary.sample.json
```

输出的 `monitors` 可直接回填到发布计划：

- `five_xx_rate`
- `query_latency_p95_ms`
- `retrieval_hit_rate`
- `permission_denial_rate`
- `generation_failure_rate`
- `missing_citation_rate`

## 4. 运行发布门禁

```powershell
py scripts\wp16_release.py docs\implementation\release\wp16_release_plan.sample.json
```

`status=pass` 才能进入 P7 灰度。

## 5. P6 交付物

- 数据库源库 manifest；
- 数据库恢复库 manifest；
- 恢复对比报告；
- API 性能/监控摘要；
- 上线报告；
- 恢复报告；
- 旧库退役决策。

模板：

- `docs/implementation/reports/P6_LAUNCH_REPORT.sample.md`
- `docs/implementation/reports/P6_RESTORE_REPORT.sample.md`
- `docs/implementation/reports/P6_OLD_DB_RETIREMENT_DECISION.sample.md`

## 6. P6 停止条件

出现以下任一情况，不进入 P7：

- 恢复后行数不一致；
- 关键表 hash 不一致；
- 引用关系检查失败；
- P95 超过阈值；
- 5xx、权限拒绝、生成失败、缺引用指标越线；
- 旧库不能设置只读或不能保留至少两个发布周期；
- 没有明确回滚开关和回滚负责人。

