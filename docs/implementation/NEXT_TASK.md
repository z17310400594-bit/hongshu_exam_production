# 下一任务

> 唯一入口任务。本文只负责导航，不是完整规格。执行 Agent 必须读取 `SELF_TEST_GATE.md` 和下方工作包文件；完成前必须提交 `reports/WPxx_SELF_TEST.md`。

## 当前状态

- **WP00** ✅ 已完成
- **WP01** ✅ 已完成
- **WP02** ✅ 已完成
- **WP03** ✅ 已完成（`a4e560d` + registry fix）：52 tests, validate.bat ALL CHECKS PASSED
- **WP04** ✅ 已完成（`125677b`）：69 tests, real MinIO fixture, API smoke, validate.bat ALL CHECKS PASSED

## 下一包（WP05：知识点及资料映射）

**前置**：WP03、WP04 已完成。
建议先创建 `work-packages/WP05.md`，按 `SELF_TEST_GATE.md` 补全需求追踪矩阵后再编码。

执行 Agent 不得仅按本文件摘要实现；必须读取桌面交接包和工作包文件。
停止点：提交 `feat: add reusable knowledge graph`。
