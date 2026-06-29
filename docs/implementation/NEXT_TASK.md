# 下一任务

> 唯一入口任务。本文只负责导航，不是完整规格。执行 Agent 必须读取 `MVP_PLAN_WP06_PLUS.md`、`SELF_TEST_GATE.md` 和下方工作包文件；完成前必须提交 `reports/WPxx_SELF_TEST.md`。

## 当前状态

- **WP00** ✅ 已完成
- **WP01** ✅ 已完成
- **WP02** ✅ 已完成
- **WP03** ✅ 已完成（`a4e560d` + registry fix）：52 tests, validate.bat ALL CHECKS PASSED
- **WP04** ✅ 已完成（`125677b`）：69 tests, real MinIO fixture, API smoke, validate.bat ALL CHECKS PASSED
- **WP05** ✅ 已完成（`63dd920`）：77 tests, knowledge point MVP API smoke, metadata diff_count=0
- **WP06** ✅ 已完成（local-not-committed）：87 tests, policy rules MVP API/DB checks, ruff 0, pyright 0, alembic clean
- **WP07** ✅ 已完成（local-not-committed）：95 tests, exam schedule MVP API/DB checks, ruff 0, pyright 0, alembic clean, smoke OK
- **WP08** ✅ 已完成（local-not-committed）：103 tests, content chapter MVP API/DB checks, ruff 0, pyright 0, alembic clean, smoke OK
- **WP09** ✅ 已完成（local-not-committed）：110 tests, question bank MVP API/DB checks, ruff 0, pyright 0, alembic clean, smoke OK
- **WP10** ✅ 已完成（local-not-committed）：117 tests, generation citation MVP API/DB checks, ruff 0, pyright 0, alembic clean, smoke OK
- **WP11** ✅ 已完成（local-not-committed）：125 tests, import validation MVP API/DB checks, ruff 0, pyright 0, alembic clean, smoke OK
- **WP12** ✅ 已完成（local-not-committed）：130 tests, API V2 query MVP checks, ruff 0, pyright 0, alembic clean, smoke OK
- **WP13** ✅ 已完成（local-not-committed）：Taro V2 certificate/exam MVP, H5 build OK, frontend type/lint no new scoped issues, backend 130 tests
- **WP14** ✅ 已完成（local-not-committed）：生成流程最小后端化，133 tests, ruff 0, pyright 0, alembic clean, real API smoke OK, H5 build OK, frontend type/lint no new scoped issues
- **WP15** ✅ 已完成（local-not-committed）：双读/黄金集/安全验收框架 MVP，138 tests, ruff 0, pyright 0, alembic clean, acceptance sample PASS, secret scan PASS
- **WP16** ✅ 已完成（local-not-committed）：灰度/恢复/回滚/旧库只读校验框架 MVP，142 tests, ruff 0, pyright 0, alembic clean, release sample PASS, secret scan PASS

## 下一步（V2 MVP 工作包已全部完成）

WP00-WP16 已按本地 MVP 口径完成，当前尚未统一提交。

建议下一步由用户明确选择：

1. 统一 review 并提交 WP06-WP16 本地改动；
2. 补真实数据：100 条黄金集、业务负责人差异确认、生产量级恢复/压测证据；
3. 接入真实 Dify/生产网关/灰度系统。

停止点：等待用户确认是否提交或进入真实生产化补数/验收阶段。
