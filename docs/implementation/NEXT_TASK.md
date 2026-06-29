# 下一任务

> 唯一入口任务。新会话恢复时读本文件，执行其中第一个 in_progress 任务。

## 当前状态

**无 in_progress 工作包。**

- **WP00** 已完成、提交并验证通过（主体提交 `82a2ef4`，审计修正 `7fc8e3d`）。
- **WP01** 被 DEC001（后端代码位置）和 DEC002（Python 栈选择）阻塞，待用户确认后开始。

## 下一动作

1. 用户确认 DEC001 / DEC002。
2. 将 WP01 状态改为 `in_progress`。
3. 按 WP01 范围实施并在验证通过后独立提交。

## 下一包（WP01，需先解锁 DEC001/DEC002）

**前置**：DEC001（后端位置）、DEC002（Python 栈）由用户确认。

WP01 内容（07 计划）：

- 创建 `api/`、`db/migrations/`、`db/tests/`、`infra/compose.yaml`；
- 初始化 FastAPI + SQLAlchemy 2 + Alembic + psycopg pool；
- 建 PostgreSQL、MinIO、Redis 本地容器；
- 增加 `/health/live` 和 `/health/ready`；
- 创建最小 CI/验证脚本；
- **不创建业务表**。

WP01 验证门槛：

- 空环境 `docker compose up` 成功；
- Alembic 可 upgrade 和 downgrade 一个空 migration；
- ready 检查数据库，live 不依赖数据库；
- API 测试、前端原有 build/typecheck/lint 均通过（不恶化基线）。

WP01 停止点：提交 `chore: scaffold v2 api and migration runtime`。

## compact / 新会话边界提示

- WP00 提交完成后适合 compact 或开新会话。
- 禁止在 migration 半途、数据回填、API 半切换、测试失败时 compact。
