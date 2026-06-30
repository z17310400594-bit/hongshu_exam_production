# 当前进度 handoff：V2 MVP 已完成，等待统一复核

> 目的：让另一台设备或新的执行 Agent 不依赖当前聊天上下文，也能理解最新进度。本文已在 2026-06-30 根据 Mac 设备提交 `825648f` 后更新；更完整流程见 `docs/implementation/V2_MVP_FULL_FLOW.md`。

## 当前仓库状态

- 工作目录：`D:\taro_project\workbench\taro_workbench`
- 分支：`feat/v2-knowledge-platform`
- 远端：`origin git@github.com:z17310400594-bit/hongshu_exam_production.git`
- 当前 MVP 实现提交：`825648f feat: complete v2 knowledge platform mvp`
- 当前工作区已从远端 fast-forward 到 `825648f`。

## 最近关键提交

```text
825648f feat: complete v2 knowledge platform mvp
b690439 docs: add current handoff and design package
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
- WP06-WP16：已由 Mac 设备统一完成并提交到 `825648f`。
  - 结果见 `IMPLEMENTATION_STATUS.md` 和 `V2_MVP_FULL_FLOW.md`。

## 已采用的执行口径

从 WP06 开始，后续所有包已按 MVP 执行，不是只有 WP06 是 MVP。后续若继续新增 WP 或修复 `825648f`，仍应沿用这个口径，除非用户明确批准进入生产化补证阶段。

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

## 下一步：统一复核

当前 `NEXT_TASK.md` 指向：

```text
WP00-WP16 MVP 已完成。
下一步等待用户确认：审计 825648f、补真实数据，或进入生产化补证。
```

建议优先做 `825648f` 的统一 review，不要直接当生产版本切流。

## 验证基线

后端统一门禁：

```bat
cmd.exe /c scripts\validate.bat
```

最新 MVP 结果：

```text
WP06-WP16 已在 825648f 中完成。
最终记录：WP16 142 tests, ruff 0, pyright 0, alembic clean, release sample PASS, secret scan PASS。
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

- `review`：优先用于审计 `825648f` 的代码、schema、权限和验收证据。
- `implement`：仅在 review 后修复明确问题或新增后续 WP 时使用。
- `database-migrations`：涉及 Alembic migration 修复或生产化迁移补证时使用。
- `postgres-patterns`：检查 schema、索引、约束和查询性能风险。
- `fastapi-patterns`：新增 service/API 或调整现有路由时保持现有 FastAPI 风格。
- `handoff`：如果再次换设备或换模型，生成新的交接摘要。

## 新设备启动 checklist

1. 获取最新代码：`git fetch` 后切到 `feat/v2-knowledge-platform`，确保包含 `825648f` 或更晚提交。
2. 阅读 `docs/implementation/CURRENT_HANDOFF.md`。
3. 阅读 `docs/implementation/V2_MVP_FULL_FLOW.md`。
4. 阅读 `docs/implementation/NEXT_TASK.md`。
5. 按需阅读 `docs/implementation/MVP_PLAN_WP06_PLUS.md` 和 `docs/implementation/design-package/20260629/`。
6. 执行 `git status --short`，确认工作区干净。
7. 不要直接生产切流；先 review `825648f`。
