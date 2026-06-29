# 下一任务

> 唯一入口任务。新会话恢复时读本文件，执行其中第一个 in_progress 任务。

## 当前任务（WP00 收尾）

**WP00 等待用户确认后提交。** Agent 已完成 WP00 全部产物，按 07 计划 §8，提交前须向用户报告 6 条并获得确认。报告内容见本会话最后一条消息。

WP00 提交命令（用户确认后执行）：

```bash
git add docs/implementation/ baseline/ backups/README.md
git commit -m "chore: establish v2 migration baseline (WP00)"
```

> **不要 `git add -A`** —— 90 条用户已有未提交改动（.agents/.claude skills 等）必须排除在本次提交外。

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
