# WP16 灰度/恢复/回滚校验工具使用说明

WP16 当前交付的是“发布演练校验框架 MVP”，不是实际生产切流。它用于在真正变更 feature flag、API 路由或旧库权限之前，先用 JSON runbook 把恢复、回滚、灰度、监控和旧库只读保留计划跑一遍机器门禁。

## 1. 运行样例计划

```bash
python scripts/wp16_release.py docs/implementation/release/wp16_release_plan.sample.json
```

返回 `status=pass` 才说明这份计划满足最小门槛。返回 `fail` 时，看 `gates[]` 中失败项。

## 2. Release plan 字段

### restoreDrill

用于记录 V2 数据库和对象存储恢复演练结果。

必须全部为 `true`：

- `databaseRestored`
- `objectStorageRestored`
- `rowCountsMatch`
- `hashesMatch`
- `referencesValid`

### rollbackDrill

用于证明前端 feature flag 和 API 回滚能在约定时间内完成。

- `featureFlags`：所有 V2 flag 必须切回 `old` / `v1` / `false`
- `apiRollback`：必须为 `true`
- `elapsedMinutes`：默认必须小于等于 30 分钟

### rollout

灰度阶段必须按顺序：

1. `internal`：内部用户，`trafficPercent=0`
2. `canary`：小比例业务流量，`0 < trafficPercent < 100`
3. `full`：全量，`trafficPercent=100`

每个阶段必须 `approved=true`。

### monitors

必须包含：

- `five_xx_rate`
- `query_latency_p95_ms`
- `retrieval_hit_rate`
- `permission_denial_rate`
- `generation_failure_rate`
- `missing_citation_rate`

每个指标使用：

```json
{"actual": 0.01, "threshold": 0.02, "direction": "lte"}
```

`direction` 可为：

- `lte`：actual 必须小于等于 threshold
- `gte`：actual 必须大于等于 threshold

### oldDatabase

旧库必须：

- `mode=readonly`
- `retentionReleaseCycles >= 2`
- `deleteScheduled=false`

### reports

必须记录三类报告入口：

- `launchReport`
- `restoreReport`
- `retirementDecision`

模板：

- `docs/implementation/reports/WP16_LAUNCH_REPORT.sample.md`
- `docs/implementation/reports/WP16_RESTORE_REPORT.sample.md`
- `docs/implementation/reports/WP16_OLD_DB_RETIREMENT_DECISION.sample.md`

## 3. 真正生产执行前的提醒

本工具只校验计划文件，不会真正：

- 切 feature flag；
- 修改 API 网关；
- 改旧库只读权限；
- 恢复数据库或对象存储；
- 删除、归档或退役旧库。

真实执行前，需要业务负责人确认 WP15 的真实黄金集差异清单，并在独立生产变更窗口内操作。
