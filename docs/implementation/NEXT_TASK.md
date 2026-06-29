# 下一任务

> 唯一入口任务。新会话恢复时读本文件，选择编号最小且依赖已完成的 pending 包。
> 执行 Agent 开始前必须阅读并遵守 `SELF_TEST_GATE.md`；未提交完整自测报告不得标记完成或进入下一包。

## 当前状态

**无 in_progress 工作包。**

- **WP00** ✅ 已完成（`82a2ef4` → `ec82843`）
- **WP01** ✅ 已完成（`b2a0f39`）：pytest 6/6, ruff 0, pyright 0, uvicorn 200 OK
- **WP02** ✅ 已完成（`8633068`）：23/23 tests, ruff 0, pyright 0, ACL 矩阵全覆盖

## 下一包（WP03：证书、别名、科目主数据）

**前置**：WP02 已完成，无阻塞。

WP03 内容：创建 certificate、certificate_alias、exam_subject；规范别名和唯一约束；旧 ID 映射草案；清洗重复别名。

WP03 停止点：提交 `feat: add governed certificate master data`。
