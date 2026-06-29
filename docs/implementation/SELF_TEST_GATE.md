# 工作包自测与验收门禁

> 适用于 WP02-WP16。执行 Agent 必须先完成自测并留下证据，才能把工作包标记为 `completed / PASS`。

## 强制执行顺序

1. 读取 `IMPLEMENTATION_STATUS.md`、`NEXT_TASK.md`、`DECISIONS.md`，确认前置包完成。
2. 将当前包改为 `in_progress`，只修改本包范围。
3. 先写失败用例再实现；覆盖正常、拒绝、约束失败和信息泄漏。
4. 依次运行专项测试、Python 门禁、迁移门禁、真实服务冒烟和前端回归。
5. 检查 diff、凭据和工作包边界。
6. 全部通过后，才允许标记 `completed / PASS` 并提交。

任一必测项失败：保持 `in_progress`，修复后重跑完整门禁；禁止用“环境问题”或“已有问题”掩盖新增回归。

## 通用门禁

在 Windows 仓库根目录执行：

```bat
scripts\validate.bat
python -m pytest api/tests db/tests -q
python -m ruff check api db
python -m pyright api db --pythonversion 3.12
python -m alembic current
python -m alembic check
python -m api.run
```

另开终端请求 `/health/live`、`/health/ready`：都必须 HTTP 200，ready 必须为 `database=connected`。必须通过真实 Uvicorn 入口，不能只用 ASGITransport；验证后关闭服务。

迁移测试必须使用独立测试库，执行 upgrade → downgrade → upgrade，最终位于 head；不得对开发库或基线库执行 `downgrade base`，并要证明开发库未被迁移或回滚。

前端即使未修改也要运行：

```bat
npm.cmd run build:h5
npm.cmd run typecheck
npm.cmd run lint
```

- 构建必须成功。
- typecheck 基线 1046 个错误，lint 基线 7 errors、3 warnings，均不得增加。
- 若修改前端，涉及文件不得新增错误，不能只看总数。

最后检查 `git diff --check`、`git status --short`、`git diff --stat`、`git diff --name-only`，并扫描 api/db/infra 的 password、secret、API key、Bearer。不得包含真实凭据、缓存/构建产物、越界文件或用户原有改动；真实 `.env` 不得入库。

## WP02 专项自测

| 场景 | 数据 | 期望 |
|---|---|---|
| internal 允许 | 教材部用户读教材部内部集合 | allow |
| restricted 拒绝 | 运营部用户读教辅部 restricted 集合 | HTTP 403 |
| public 允许 | 有效用户读 public 集合 | allow |
| 默认拒绝 | 无身份、未知部门或无 ACL | HTTP 403 |
| 检索前授权 | 无权请求进入检索入口 | 不调用正文/向量检索 |
| 防泄漏 | 请求存在但无权访问的集合 | 响应及日志不含标题、正文、内部 ID、密级详情 |
| FK/CHECK | 不存在引用、非法密级/主体类型/层级 | 数据库拒绝 |
| 唯一性 | 重复组织、集合标识或 ACL | 数据库拒绝 |
| 迁移回环 | 测试库 upgrade → downgrade → upgrade | 成功且位于 head |

测试必须包括：

- `db/tests/`：schema、FK、CHECK、UNIQUE、隔离迁移回环。
- `api/tests/`：身份适配、授权矩阵、403、防泄漏、检索前拦截。
- fixtures：教材部、教辅部、运营部，四级密级，以及允许/拒绝样本。

WP02 不得创建证书、资产、知识点、试卷等后续业务表，不得接入真实检索正文。正向测试必须连接真实测试库；负向 mock 必须符合真实同步/异步协议；pytest 不得有 warning；403 防泄漏必须同时检查响应和日志。

## 完成报告

```text
WPxx SELF-TEST REPORT
Scope: <修改范围>
Migration: PASS/FAIL（测试库、upgrade/downgrade/upgrade）
Special tests: PASS/FAIL（通过数/总数）
Pytest: PASS/FAIL（通过数、warning 数）
Ruff: PASS/FAIL（错误数）
Pyright: PASS/FAIL（错误数）
API smoke: live=<结果>, ready=<结果>
Frontend: build=<结果>, typecheck=<当前/基线>, lint=<当前/基线>
Security/diff: PASS/FAIL
Commit: <sha；提交前写 pending>
Overall: PASS/FAIL
```

只有 `Overall: PASS` 且没有 warning、没有未解释回归时，才允许更新状态文档。
