# 下一任务

> 唯一入口任务。本文只负责导航，不是完整规格。执行 Agent 必须读取 `MVP_PLAN_WP06_PLUS.md`、`SELF_TEST_GATE.md` 和下方工作包文件；完成前必须提交 `reports/WPxx_SELF_TEST.md`。

## 当前状态

- **WP00** ✅ 已完成
- **WP01** ✅ 已完成
- **WP02** ✅ 已完成
- **WP03** ✅ 已完成（`a4e560d` + registry fix）：52 tests, validate.bat ALL CHECKS PASSED
- **WP04** ✅ 已完成（`125677b`）：69 tests, real MinIO fixture, API smoke, validate.bat ALL CHECKS PASSED
- **WP05** ✅ 已完成（`63dd920`）：77 tests, knowledge point MVP API smoke, metadata diff_count=0
- **WP06** ✅ 已完成（`825648f`）：87 tests, policy rules MVP API/DB checks, ruff 0, pyright 0, alembic clean
- **WP07** ✅ 已完成（`825648f`）：95 tests, exam schedule MVP API/DB checks, ruff 0, pyright 0, alembic clean, smoke OK
- **WP08** ✅ 已完成（`825648f`）：103 tests, content chapter MVP API/DB checks, ruff 0, pyright 0, alembic clean, smoke OK
- **WP09** ✅ 已完成（`825648f`）：110 tests, question bank MVP API/DB checks, ruff 0, pyright 0, alembic clean, smoke OK
- **WP10** ✅ 已完成（`825648f`）：117 tests, generation citation MVP API/DB checks, ruff 0, pyright 0, alembic clean, smoke OK
- **WP11** ✅ 已完成（`825648f`）：125 tests, import validation MVP API/DB checks, ruff 0, pyright 0, alembic clean, smoke OK
- **WP12** ✅ 已完成（`825648f`）：130 tests, API V2 query MVP checks, ruff 0, pyright 0, alembic clean, smoke OK
- **WP13** ✅ 已完成（`825648f`）：Taro V2 certificate/exam MVP, H5 build OK, frontend type/lint no new scoped issues, backend 130 tests
- **WP14** ✅ 已完成（`825648f`）：生成流程最小后端化，133 tests, ruff 0, pyright 0, alembic clean, real API smoke OK, H5 build OK, frontend type/lint no new scoped issues
- **WP15** ✅ 已完成（`825648f`）：双读/黄金集/安全验收框架 MVP，138 tests, ruff 0, pyright 0, alembic clean, acceptance sample PASS, secret scan PASS
- **WP16** ✅ 已完成（`825648f`）：灰度/恢复/回滚/旧库只读校验框架 MVP，142 tests, ruff 0, pyright 0, alembic clean, release sample PASS, secret scan PASS
- **P0** ✅ 已完成：两台设备同步计划和交接文档，远端已推送。
- **P1** ✅ 已完成（`32244f4`）：审计 MVP，实现 Dify key 当前文件清理、证书 alias 去重、P1 报告。
- **P2 Batch 001** ✅ 已完成：旧库 `cert_basic` 证书目录底座 + 执业药师深链路 + 一级建造师 2026 考试日期骨架，见 `reports/P2_BATCH_001_SELF_TEST.md`。

## 下一步（V2 MVP 工作包已全部完成）

WP00-WP16 已按 MVP 口径完成，WP06-WP16 已统一进入提交 `825648f feat: complete v2 knowledge platform mvp`。

后续不再继续按 WP 编号盲推，改按 `docs/implementation/V2_MVP_TO_PRODUCTION_PLAN.md` 的 P0-P7 阶段一步一步执行。

建议下一步由用户明确选择：

1. `P2-fix`：先处理 P2 needs_review 中的高优先级项，例如本地演示库清理、执业药师报考年限官方核验；
2. `P2-expand`：继续补省级报名时间/考区，或把一级建造师从骨架扩为完整闭环；
3. `P3`：开始黄金集与差异确认；
4. `修改计划`：先调整 `V2_MVP_TO_PRODUCTION_PLAN.md` 的阶段或范围。

停止点：等待用户确认从 P2-fix、P2-expand、P3 或修改计划开始；确认前不做功能代码改动。
