# 当前进度 handoff：V2 MVP 从 WP06 继续

> 目的：让另一台设备或新的执行 Agent 不依赖当前聊天上下文，也能从现有进度继续。不要把本文当完整规格；本文只指向当前状态、执行口径和下一步入口。

## 当前仓库状态

- 工作目录：`D:\taro_project\workbench\taro_workbench`
- 分支：`feat/v2-knowledge-platform`
- 远端：`origin git@github.com:z17310400594-bit/hongshu_exam_production.git`
- 当前代码基线：`4adc1a7 docs: clarify mvp applies after wp06`
- 本 handoff/设计包提交会在该基线之后；新设备应拉取包含 `docs/implementation/CURRENT_HANDOFF.md` 的最新提交。
- 当前本地分支领先远端 `origin/feat/v2-knowledge-platform` 7 个提交。
- 另一台设备继续前，需要先把本地提交同步过去：
  - 推荐：在当前设备执行 `git push origin feat/v2-knowledge-platform`
  - 如果不能 push：导出 git bundle 或压缩整个工作区。

## 最近关键提交

```text
4adc1a7 docs: clarify mvp applies after wp06
6349624 docs: add wp06 mvp execution plan
878a035 chore: finalize wp05 self-test report
63dd920 feat: add reusable knowledge graph
33426b3 chore: record accepted mixed baseline
8a50c15 chore: finalize wp04 self-test report
125677b fix: wp04 make minio test self-contained
b91488c chore: sync skills, dify v4 pipeline, wp04 assets, data docs
```

## 已完成工作包

- WP00-WP04：按较完整的生产级基础建设口径完成。
- WP05：已完成 MVP 转向过渡包。
  - 实现提交：`63dd920 feat: add reusable knowledge graph`
  - 报告提交：`878a035 chore: finalize wp05 self-test report`
  - 结果：`77 passed`，ruff 0，pyright 0，Alembic clean，metadata `diff_count=0`，真实 API smoke 通过。

## 当前执行口径

从 WP06 开始，后续所有包默认按 MVP 执行，不是只有 WP06 是 MVP。

必须先读：

1. `docs/implementation/MVP_PLAN_WP06_PLUS.md`
2. `docs/implementation/NEXT_TASK.md`
3. 当前工作包文件，例如 `docs/implementation/work-packages/WP06.md`
4. `docs/implementation/design-package/20260629/` 下的目标设计资料
5. `docs/implementation/SELF_TEST_GATE.md`

关键规则：

- WP06 完成后，WP07/WP08/WP09 等不得自动切回桌面完整生产级计划。
- 桌面交接包/项目内设计包是目标蓝图，不是当前每包执行强度。
- 黄金集、双读、灰度、完整生产级前端验收，后移到用户明确批准的生产化阶段。
- 后端/数据库包没改前端时，可以不跑完整前端 build/typecheck/lint，但报告必须说明。

## 项目内设计交接包

桌面交接包已复制到：

```text
docs/implementation/design-package/20260629/
```

包含：

- `01-数据模型与字段字典.md`
- `02-schema-v2.sql`
- `03-测试数据模板.md`
- `04-部署迁移与验收.md`
- `05-API与前端接入.md`
- `06-实施思路与完整性保障.md`
- `07-按步骤实施计划.md`
- `HANDOFF.md`
- `README.md`
- `PROJECT_README.md`

注意：`07-按步骤实施计划.md` 仍是原完整目标计划。WP06+ 实际执行以 `MVP_PLAN_WP06_PLUS.md` 为准。

## 下一步：WP06

当前 `NEXT_TASK.md` 指向：

```text
WP06：政策版本、条款和报考规则
停止点：feat: add policy rules MVP
```

建议 WP06 MVP 做到：

1. 创建 `work-packages/WP06.md`，先补需求追踪矩阵；
2. 建最小 policy 模型：
   - policy_document
   - policy_version
   - policy_clause
   - eligibility_rule
   - eligibility_rule_evidence
3. 规则关联 WP05 knowledge point；
4. 证据关联 WP04 fragment；
5. `published` 规则必须 `approved` 且至少一条 `primary` evidence；
6. 查询只返回有效、未废止、已审核规则；
7. 无法判断时返回 `insufficient_data`，不要猜；
8. API 只做最小 `eligibility/evaluate` 或 service 查询 smoke。

## 验证基线

后端统一门禁：

```bat
cmd.exe /c scripts\validate.bat
```

WP05 最后结果：

```text
77 passed
ruff 0
pyright 0
alembic check clean
ALL CHECKS PASSED
```

有 migration 的后续包必须额外记录：

```text
upgrade head 成功
metadata compare diff_count=0
fresh process Base.metadata.tables 包含本包表
```

有 API 的后续包必须做真实 Uvicorn smoke：

```text
/health/live = 200
/health/ready = 200 database=connected
一个允许请求
一个拒绝/无权限请求
一个匿名请求
一个未知资源请求
```

## 已知注意事项

- `b91488c` 是用户此前混合提交，已被登记为 accepted mixed baseline。不要在后续 WP 反复追责它，但 WP06+ 不得继续夹带 skills、Dify、前端或数据说明范围外改动。
- `.env` 不入库；不要在文档或日志复述真实密钥。
- 前端当前有历史 typecheck/lint 基线问题。未改前端的后端包不必按生产级跑完整前端门禁，但报告必须说明。
- 本地忽略项如 `.tmp/`、`.stylelintcache`、Dify backup、`__pycache__` 不要提交。

## 建议使用的 skills

- `implement`：执行 WP06 代码和文档变更。
- `database-migrations`：设计和验证 Alembic migration。
- `postgres-patterns`：检查 schema、索引、约束。
- `fastapi-patterns`：新增 service/API 时保持现有 FastAPI 风格。
- `review`：完成后做本地两轴复核。
- `handoff`：如果再次换设备或换模型，生成新的交接摘要。

## 新设备启动 checklist

1. 获取最新代码：`git fetch` 后切到 `feat/v2-knowledge-platform`，确保包含 `docs/implementation/CURRENT_HANDOFF.md` 所在提交。
2. 阅读 `docs/implementation/CURRENT_HANDOFF.md`。
3. 阅读 `docs/implementation/MVP_PLAN_WP06_PLUS.md`。
4. 阅读 `docs/implementation/NEXT_TASK.md`。
5. 阅读 `docs/implementation/design-package/20260629/` 中 WP06 相关来源。
6. 执行 `git status --short`，确认工作区干净。
7. 开始 WP06，不要开启 WP07。
