# 下一任务

> 唯一入口任务。新会话恢复时读本文件，选择编号最小且依赖已完成的 pending 包。
> 执行 Agent 开始前必须阅读并遵守 `SELF_TEST_GATE.md`；未提交完整自测报告不得标记完成或进入下一包。

## 当前状态

**无 in_progress 工作包。**

- **WP00** ✅ 已完成（`82a2ef4` → `ec82843`）
- **WP01** ✅ 已完成（`b2a0f39`）：pytest 6/6, ruff 0, pyright 0, uvicorn 200 OK, alembic 隔离到测试库, compose `${VAR:?}` 无硬编码凭据

## 下一包（WP02：组织、知识集合和 ACL）

**前置**：WP01 已完成，无阻塞。

WP02 内容（07 计划）：

- 创建 `iam.organization_unit`、`knowledge.collection`、`collection_acl`
- 实现最小用户身份适配器和权限服务
- 写 public/internal/confidential/restricted 四级保密 fixtures
- 实现检索前授权函数，不接入检索正文
- **不创建证书、资产等其他业务表**

WP02 验证门槛：

- 教材部能读内部教材集合
- 运营部不能读 restricted 教辅集合
- 无权请求返回 403，响应和日志不包含集合标题或正文
- 所有 FK/CHECK 失败用例通过

WP02 完成前必须执行 `SELF_TEST_GATE.md` 的通用门禁和专项自测，并输出 `WP02 SELF-TEST REPORT`。任一项失败时保持 `in_progress`。

WP02 停止点：提交 `feat: add organization collections and acl`。

## compact / 新会话边界提示

- WP01 完成后适合 compact 或开新会话。
- 禁止在 migration 半途、数据回填、API 半切换时 compact。
