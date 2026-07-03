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
- **P3 Batch 001** ✅ 已完成：基于 P2 已迁数据建立 10 条真实黄金用例，runner 可实际调用 V2 service，见 `reports/P3_GOLDEN_SET_REPORT.md`。
- **P4** ✅ 已完成：Taro 新增 `V2闭环` 入口，展示证书/考试/资格/知识/题库/权限/生成引用闭环，H5 build OK，P4 scoped lint OK，backend 149 tests，P3 golden set PASS，见 `reports/P4_FRONTEND_FLOW_SELF_TEST.md`。
- **P5** ✅ 代码路径已完成：后端模型网关/Dify 配置入口、失败落库、引用非空门禁、前端不持密钥；定向生成测试 6 passed，见 `reports/P5_MODEL_GATEWAY_SELF_TEST.md`。真实 Dify smoke 需在后端密钥环境执行。
- **P6** ✅ 已完成：新增运维证据 CLI，可生成 DB manifest、恢复对比、API 监控摘要；本地 DB manifest smoke 通过，发布门禁样例 pass，见 `reports/P6_PRODUCTION_OPS_SELF_TEST.md`。
- **P8** ❌ 已废弃：小红书策略化生成 MVP 不做了。不要继续识别或执行 `docs/implementation/P8_XHS_STRATEGY_MVP_PLAN.md`，以 `D:\pro_manager\PROJECT_STATE.md` 的最新人工决策为准。

## 下一步（P8 已废弃）

WP00-WP16 已按 MVP 口径完成，WP06-WP16 已统一进入提交 `825648f feat: complete v2 knowledge platform mvp`。

后续不再继续按 WP 编号盲推，改按 `docs/implementation/V2_MVP_TO_PRODUCTION_PLAN.md` 的 P 阶段一步一步执行。

基于 2026-07-03 最新人工决策：

1. P8 小红书策略化生成 MVP 已废弃，不做了；
2. 不要读取 P8 计划作为下一步；
3. 不要继续进入旧修复分支或 P7；
4. 小红书当前标记为阶段 1 已完成；
5. 后续如要继续小红书方向，必须重新开新需求，并先读取 `D:\pro_manager\PROJECT_STATE.md`。

停止点：不做 P8，不做策略管理后台，不做批量内容中台，不做复杂拖拽编辑器，不直接进入 P7 灰度。
