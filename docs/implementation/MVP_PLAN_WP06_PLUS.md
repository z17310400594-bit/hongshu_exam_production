# WP06 之后统一 MVP 实施计划

> 适用范围：从 WP06 开始的所有后续工作包，直到用户明确宣布进入生产化验收/灰度阶段为止。WP00-WP04 保持已完成的生产级基础建设口径；WP05 是 MVP 转向的过渡包，已完成。后续执行 Agent 必须先读本文，再读桌面交接包和当前工作包文件。
>
> 硬规则：WP06 完成后，WP07、WP08、WP09……不得自动切回桌面计划书的完整生产级模式；每个下一包入口都必须继续引用本文。

## 1. 为什么从 WP06 开始切 MVP

原桌面交接包的 `07-按步骤实施计划.md` 是目标架构计划，包含完整迁移、双读、黄金集、安全验收、灰度和旧库退役。这个计划适合生产上线前，但不适合当前阶段逐包探索。

当前阶段目标改为：

```text
asset/version/fragment
→ knowledge point
→ policy/content reference
→ API query
→ frontend call
```

也就是说，先跑通业务闭环，再把生产级验收逐步补上。

## 2. 执行口径优先级

从 WP06 开始，执行 Agent 按以下优先级理解需求。这个优先级会持续适用于 WP07、WP08、WP09 以及后续包，除非用户明确修改口径。

1. `docs/implementation/MVP_PLAN_WP06_PLUS.md`：WP06 之后所有后续包的当前 MVP 执行口径。
2. `docs/implementation/NEXT_TASK.md`：下一包入口。
3. `docs/implementation/work-packages/WPxx.md`：当前包追踪矩阵。
4. 桌面交接包：目标架构和字段来源。
5. `SELF_TEST_GATE.md`：基础质量门禁；若与本文冲突，以本文的 MVP 裁剪为准。

桌面交接包不是废弃，而是目标蓝图；本文决定每包现在做到哪里停。

## 3. MVP 保留的硬底线

以下要求不因为 MVP 而降低：

- migration 必须能从空库升级到 head；
- ORM registry、Alembic check、metadata diff 不得假绿；
- 后端核心测试、ruff、pyright 必须通过；
- API 必须通过真实 Uvicorn smoke；
- ACL 不得绕过；
- restricted/private 内容不得对无权主体泄漏；
- `.env`、Dify key、数据库密码、Bearer token 不得入库；
- 每包必须有 `WPxx.md` 需求矩阵和 `reports/WPxx_SELF_TEST.md`；
- 每包结束必须独立提交并更新 `IMPLEMENTATION_STATUS.md` / `NEXT_TASK.md`。

## 4. MVP 暂缓项

除非当前包明确修改前端或用户特别要求，WP06 之后的 MVP 包都暂缓：

- 每包都跑完整前端 `build:h5/typecheck/lint`；
- 100 条黄金问题集；
- 新旧双读对账；
- 生产量级迁移压测；
- 完整灰度/回滚演练；
- 完整 Dify/生成工作流；
- 完整 CSV/staging 全量导入；
- 所有前端页面一次性接入。

这些不删除，后移到用户明确批准的生产化阶段；不能由执行 Agent 在 WP07/WP08/WP09 等后续包中自行恢复完整模式。

## 5. WP06-WP14 MVP 工作包边界

| 包 | MVP 目标 | 本阶段必须做 | 暂缓 |
|---|---|---|---|
| WP06 | 政策文档、版本、条款、报考规则最小闭环 | policy_document/version/clause/eligibility_rule/evidence；published 必须 approved + primary evidence；API/service 可做最小查询 | 全量政策导入、复杂地区规则全集、黄金集 |
| WP07 | 考试场次和合格线最小可查 | exam_event/phase/subject_score_rule；年度/地区/日期约束；基础查询 | 历史全量清洗、复杂多地区发布流程 |
| WP08 | 教材/教辅章节最小承接 | product/version/chapter/chapter_kp；章节关联 WP04 asset 和 WP05 kp | 完整编辑状态机、前端章节编辑器 |
| WP09 | 题库最小承接 | paper/question/question_kp；题型/答案 JSON 基础约束 | 全量题库导入、覆盖率报表 |
| WP10 | 生成引用最小审计 | generation_run/citation/output；输出引用片段；保密级别不降级 | 完整 Dify 编排、多模型路由、内容指标全量 |
| WP11 | 最小 staging/校验框架 | import_batch/validation_error；少量 valid/invalid fixtures | 全量桌面 CSV 迁移 |
| WP12 | 最小 API V2 闭环 | certificates、eligibility/evaluate、knowledge/search 的 MVP 查询 | 全接口分页/性能/双读 |
| WP13 | 前端最小接入 | 统一 httpClient；feature flag；接一个最小查询流 | 全页面重构 |
| WP14 | 生成流程最小后端化 | 前端不直连 Dify；后端任务 + 引用展示最小链路 | 完整 SSE、审核大后台 |

WP15/WP16 属于生产化验收候选包；只有 MVP 闭环跑通且用户明确批准后才能进入。执行 Agent 不得因为编号推进到 WP15/WP16 就自行恢复完整生产模式。

## 6. 每包最小自测模板

后端/数据库包必须至少运行：

```bat
python -m pytest <新增测试文件> -q
python -m pytest api/tests db/tests -q
python -m ruff check api db
python -m pyright api db --pythonversion 3.12
python -m alembic check
cmd.exe /c scripts\validate.bat
```

有 migration 时还必须记录：

```text
upgrade head 成功
metadata compare diff_count=0
fresh process Base.metadata.tables 包含本包表
```

有 API 时还必须跑真实服务 smoke：

```text
/health/live = 200
/health/ready = 200 database=connected
一个允许请求
一个拒绝/无权限请求
一个匿名请求
一个未知资源请求
```

前端验证规则：

- 当前包没有修改前端：报告写 `Frontend: NOT RUN for MVP backend/db package`，并引用本文；
- 当前包修改前端：必须跑 `npm.cmd run build:h5`，并至少检查相关文件不新增 type/lint 问题；
- WP13/WP14 若实际修改前端或生成流程，按“修改到哪里验证到哪里”的 MVP 前端验证执行，不自动恢复生产级全量验收；
- WP15/WP16 只有在用户明确宣布进入生产化验收/灰度阶段后，才按完整生产门禁执行。

## 7. 下一包路由规则

每完成一个工作包，更新 `NEXT_TASK.md` 时必须保留以下语义：

```text
执行 Agent 必须先读取 docs/implementation/MVP_PLAN_WP06_PLUS.md。
从 WP06 起后续包持续按 MVP 口径执行。
不得因为进入 WP07/WP08/WP09 等后续编号而切回桌面完整生产级计划。
```

如果某个后续包确实需要恢复完整生产级门禁，必须由用户明确批准，并在 `DECISIONS.md` 记录。

## 8. WP06 执行提示

WP06 不要一口气实现完整政策事实平台。先做：

1. 建 `policy_document`、`policy_version`、`policy_clause`、`eligibility_rule`、`eligibility_rule_evidence`；
2. 规则关联 WP05 knowledge point，证据关联 WP04 fragment；
3. `published` 规则必须 `approved` 且至少一条 `primary` evidence；
4. 当前查询只返回有效、未废止、已审核规则；
5. 无法判断时返回 `insufficient_data`，不要猜；
6. API 只做一个最小 `eligibility/evaluate` 或 service 查询 smoke。

停止点建议：

```text
feat: add policy rules MVP
```

## 9. 给执行 Agent 的一句话

从 WP06 开始，后续所有包默认都是 MVP 执行。不要在 WP07、WP08、WP09 或后续包又切回桌面计划书里的生产级完整迁移。每包只打通当前 MVP 链路，保留数据安全、权限、migration 和测试硬底线；黄金集、双读、灰度和全量前端验收后移到用户明确批准的生产化阶段。
