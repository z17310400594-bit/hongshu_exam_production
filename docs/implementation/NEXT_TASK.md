# 下一任务

> 唯一入口任务。本文只负责导航，不是完整规格。执行 Agent 必须读取 `MVP_PLAN_WP06_PLUS.md`、`SELF_TEST_GATE.md` 和下方工作包文件；完成前必须提交 `reports/WPxx_SELF_TEST.md`。

## 当前状态

- **WP00** ✅ 已完成
- **WP01** ✅ 已完成
- **WP02** ✅ 已完成
- **WP03** ✅ 已完成（`a4e560d` + registry fix）：52 tests, validate.bat ALL CHECKS PASSED
- **WP04** ✅ 已完成（`125677b`）：69 tests, real MinIO fixture, API smoke, validate.bat ALL CHECKS PASSED
- **WP05** ✅ 已完成（`63dd920`）：77 tests, knowledge point MVP API smoke, metadata diff_count=0

## 下一包（WP06：政策版本、条款和报考规则）

**前置**：WP05 已完成。
建议先创建 `work-packages/WP06.md`，按 MVP 节奏补全需求追踪矩阵后再编码。

执行 Agent 不得仅按本文件摘要实现；必须先读取 `docs/implementation/MVP_PLAN_WP06_PLUS.md`，再读取桌面交接包和工作包文件。
MVP 节奏从 WP06 起持续适用于后续所有包：WP06 完成后，WP07/WP08/WP09 等不得自动切回桌面完整生产级计划。当前 WP06 优先打通政策文档/版本/条款/eligibility 到知识点和片段引用的最小闭环；不要一次性展开生产级全量导入、黄金集和前端大改。
停止点：提交 `feat: add policy rules MVP`。
