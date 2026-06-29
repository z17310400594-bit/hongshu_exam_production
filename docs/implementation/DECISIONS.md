# 决策记录

> 记录迁移过程中的技术与业务决策，每条标日期、决策者、理由、影响。
> 格式：ADR-lite（背景/决策/后果）。

## 待决策（阻塞 WP01+）

### DEC001 · 后端代码放置位置 — 待用户确认

- **背景**：当前后端散落在 `docs/dify/v3/`（policy_api.py 等），仓库根无 `api/` `db/`。
- **选项**：
  - A：在当前 `taro_workbench` 仓库内新建 `api/` `db/` `infra/`（混合仓，monorepo）。
  - B：单独建后端仓库。
- **倾向**：A（方案 07 文档 WP01 已假定此结构，且前端/后端同仓便于 feature flag 联动与一次提交）。
- **状态**：待用户拍板。阻塞 WP01 启动。

### DEC002 · Python 依赖与栈 — 待用户确认

- **背景**：方案推荐 FastAPI + SQLAlchemy 2 + Alembic + psycopg pool + pytest/Testcontainers；当前 `policy_api.py` 用 FastAPI + pg8000 手写连接池。
- **倾向**：采纳方案推荐栈，WP01 建 `pyproject.toml` 锁版本，从零建工程（不复用 pg8000 手写池，方案 §五明确反对）。
- **状态**：待用户确认。阻塞 WP01。

## 已决策

### DEC000 · 启动 WP00 并执行 pg_dump — 已确认 2026-06-29

- **背景**：07 计划要求 Agent 首次只做 WP00 并报告 6 条。
- **决策**：用户授权执行 pg_dump（"现在还不是真正的生产环境"），并要求先跑一遍 WP00 报告再正式提交。
- **后果**：WP00 完成 pg_dump + 哈希 + 状态文件，提交前停手等用户确认。

## 密钥轮换清单

> 只记录位置与轮换状态，**不在此处或任何提交文件中记录真实值**。
> WP00 任务之一是建立此清单；实际轮换在 WP14 完成，前端密钥删除在 WP13/WP14。

| 编号 | 位置 | 类型 | WP00 状态 | 计划处理 |
|---|---|---|---|---|
| K001 | `src/services/dify.ts`（前端硬编码） | Dify API Key | 已识别存在 | WP14 删除前端直连，Key 后端化 |
| K002 | `.env.development` 变量 `TARO_APP_DIFY_API_KEY` | Dify API Key | 已识别存在 | WP13/WP14 改读后端代理，轮换该 Key |
| K003 | `docs/dify/v3/policy_api.py:41` 默认 `policy123` | 数据库密码 | 已识别存在 | WP01 起 V2 读环境变量；旧 API 轮换需另行安排 |
| K004 | `docs/dify/v3/policy_api.py:46` `CORS allow_origins=["*"]` | 跨域全开 | 已识别存在 | WP12 API V2 收紧为白名单 |

> 注：V2 全新工程（WP01 起）一律通过环境变量注入凭证，`infra/compose.yaml` 与 `.env.example` 只保留变量名，不放真实值。
