# 决策记录

> 记录迁移过程中的技术与业务决策，每条标日期、决策者、理由、影响。
> 格式：ADR-lite（背景/决策/后果）。

## 已决策

### DEC001 · 后端代码放置位置 — 已决 2026-06-29

- **背景**：当前后端散落在 `docs/dify/v3/`。
- **决策**：在当前仓库内新建 `api/` `db/` `infra/`（混合仓），WP01 已落地。
- **后果**：前端/后端同仓，feature-flag 联动与一次提交更方便。

### DEC002 · Python 依赖与栈 — 已决 2026-06-29

- **背景**：方案推荐 FastAPI + SQLAlchemy 2 + Alembic + psycopg pool + pytest。
- **决策**：采纳方案推荐栈，WP01 已建立 `pyproject.toml`，从零建工程不复用 pg8000 手写池。
- **后果**：`pyproject.toml` 锁了所有版本范围；pytest 6/6 通过。

### DEC000 · 启动 WP00 并执行 pg_dump — 已决 2026-06-29

- **背景**：07 计划要求 Agent 首次只做 WP00 并报告 6 条。
- **决策**：用户授权执行 pg_dump（"现在还不是真正的生产环境"）。
- **后果**：WP00 完成并已通过审计修正。

## 密钥轮换清单

> 只记录位置与轮换状态，**不在此处或任何提交文件中记录真实值**。
> 实际轮换在 WP14 完成，前端密钥删除在 WP13/WP14。

| 编号 | 位置 | 类型 | 状态 | 计划处理 |
|---|---|---|---|---|
| K001 | `src/services/dify.ts`（前端硬编码） | Dify API Key | 已识别 | WP14 删除前端直连，Key 后端化 |
| K002 | `.env.development` 变量 `TARO_APP_DIFY_API_KEY` | Dify API Key | 已识别 | WP13/WP14 改读后端代理 |
| K003 | `docs/dify/v3/policy_api.py:41` 存在硬编码默认数据库密码 | 数据库密码 | 已识别，**需立即轮换** | V2 WP01 起读环境变量；旧 API 轮换需另行安排 |
| K004 | `docs/dify/v3/policy_api.py:46` `CORS allow_origins=["*"]` | 跨域全开 | 已识别 | WP12 API V2 收紧为白名单 |

> V2 工程（WP01 起）通过环境变量注入凭证，`compose.yaml` 使用 `${VAR:?}` 强制、`.env.example` 只保留变量名与 dev 默认值。
