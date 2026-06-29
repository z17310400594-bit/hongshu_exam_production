# V2 实施状态

> 本文件是 V2 迁移的唯一状态真相源。状态只能是 `pending / in_progress / completed / blocked`。
> 每包开始改 `in_progress`，结束改 `completed` 并填 commit 与验证结果。
> 新会话恢复时：先读本文件 + `NEXT_TASK.md`，选编号最小且依赖已完成的 pending 包。
> 强制门禁：每包必须先按 `SELF_TEST_GATE.md` 完成自测并输出报告；未满足时禁止填写 `PASS`。

## 工作包状态

| 包 | 状态 | Commit | 验证 | 阻塞 | 备注 |
|---|---|---|---|---|---|
| WP00 | completed | 7fc8e3d | PASS | - | 基线/备份/状态文件（已修正通过审计） |
| WP01 | completed | b2a0f39 | PASS | - | 后端骨架（pytest 6/6, ruff 0, pyright 0, uvicorn 200 OK, alembic隔离, compose干净） |
| WP02 | completed | d6253d0 | PASS | - | iam/organization/collection/ACL + HTTP 403 + 循环导入已解（27/27, ruff 0, pyright 0, alembic check clean） |
| WP03 | in_progress | - | - | - | certificate/alias/exam_subject — 证书、别名、科目主数据 |
| WP04 | pending | - | - | WP02 | asset/version/fragment/MinIO |
| WP05 | pending | - | - | WP03,WP04 | knowledge_point/relation/scope |
| WP06 | pending | - | - | WP05 | policy document/version/clause/eligibility |
| WP07 | pending | - | - | WP03 | exam_event/phase/score_rule |
| WP08 | pending | - | - | WP05 | content product/version/chapter |
| WP09 | pending | - | - | WP05,WP07 | paper/question/kp |
| WP10 | pending | - | - | WP04,WP05 | generation run/citation/output + analytics |
| WP11 | pending | - | - | WP03-WP10 | staging/validation/数据迁移（可拆11A-11D）|
| WP12 | pending | - | - | WP06-WP11 | API V2 查询+生成 |
| WP13 | pending | - | - | WP12 | Taro 前端低风险接入 |
| WP14 | pending | - | - | WP10,WP12,WP13 | 生成流程+审核接入 |
| WP15 | pending | - | - | WP12-WP14 | 双读/评测/安全验收 |
| WP16 | pending | - | - | WP15 | 灰度/恢复演练/旧库退役 |

## 实施分支

- 分支：`feat/v2-knowledge-platform`（从 `master` 切出）
- WP00 开始时工作区有 90 条用户已有未提交改动（主要是 `.agents/` 与 `.claude/` 的 skills 文件 + 少量 src/docs），**实施全程不得覆盖或提交这些非本包改动**。

## 基线记录（WP00 采集，迁移前既有状态）

### 数据库（容器 policy-db，postgres:15-alpine，5433->5432）

- 库名：`policy_fact`，owner `policy`，14 张表。
- 备份：`backups/policy_fact_baseline_20260629.sql`（102605 字节，1115 行，含 14 CREATE TABLE + 14 COPY 数据）。
- 各表行数画像（见 `DATA_ISSUES.md` 数据分布一节）。

### API（容器 policy-api，端口 8400）

- `/health` → `{"status":"ok","database":"connected"}`
- `/query/certs` → 17 证书，样本存 `baseline/api-contracts/v1_query_certs.json`（3164 字节）。
- `/query/policy` (cls1_constructor) → **子表全空**，样本存 `baseline/api-contracts/v1_query_policy_sample.json`（284 字节）。详见 `DATA_ISSUES.md`。

### 前端构建基线（迁移前既有，非本次引入）

- `npm run typecheck`：**1046 个 TS 错误**。其中 1045 个在 `node_modules/`（webpack-chain / webpack-dev-server / webpack 的 `.d.ts` 类型冲突），**1 个在 `config/index.ts:7`**（TS6198：All destructured elements are unused）。
- `npm run lint`：7 errors + 3 warnings，均为 `src/` 既有问题（`confirm` 全局、`<select>` 应用 Picker、hooks deps）。**非本次迁移引入。**
- `npm run build:h5`：编译成功；webpack 报告 2 个体积类 warning（asset size limit、entrypoint size limit），另有 cache serialization 与 deprecated hash 提示，均非 error。
- 后续 WP 若上述指标恶化才视为回归；既有值本身不阻塞迁移。
