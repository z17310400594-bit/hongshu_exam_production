# 下一任务

> 唯一入口任务。新会话恢复时读本文件，选择编号最小且依赖已完成的 pending 包。
> 执行 Agent 开始前必须阅读并遵守 `SELF_TEST_GATE.md`；完成前必须提交 `reports/WPxx_SELF_TEST.md`，并在最终提交后完成冷启动复验。

## 当前状态

- **WP00** ✅ 已完成
- **WP01** ✅ 已完成
- **WP02** ✅ 已完成（`d6253d0`）：27/27 tests, ruff 0, pyright 0, HTTP 200/401/403

## 下一包（WP03：证书、别名、科目主数据）

**前置**：WP02 已完成。
WP03 内容：创建 certificate、certificate_alias、exam_subject；规范别名和唯一约束。
停止点：提交 `feat: add governed certificate master data`。
