# P1 Review Report — 825648f V2 MVP 实现审计

日期：2026-06-30  
审计对象：`825648f feat: complete v2 knowledge platform mvp`  
当前工作分支：`feat/v2-knowledge-platform`  
审计范围：从 `b690439` 到 `825648f` 引入的 V2 MVP 实现，以及 P0 文档提交后的当前工作树。

## 结论

P1 可以通过，但本轮发现并修复了两个需要尽早处理的问题：

1. 仓库当前文件中存在历史 Dify API Key 明文。
   - 已把当前文件中的真实 key 替换为 `<DIFY_API_KEY>`。
   - 由于 key 曾经进入 git 历史，必须在 Dify 后台轮换/废弃对应 key。
2. V2 证书接口返回别名时可能展示重复中文别名。
   - 已在 `list_certificates()` 和 `get_certificate_detail()` 输出层去重。
   - 已补充回归测试覆盖“同一证书存在相同展示 alias、不同 normalized_alias”的场景。

除上述修复外，未发现阻塞 P2 的数据库迁移、API 契约、权限模型或前端构建问题。

## 本轮代码修复

### 1. 清理当前文件中的 Dify 明文 key

涉及文件：

- `docs/dify/README.md`
- `docs/dify/v3/v3-knowledge-base-design.md`
- `key/hongshu_production.md`

处理方式：

- 将真实 key 替换为 `<DIFY_API_KEY>`。
- 保留配置位置说明，避免后续 agent 不知道应该在哪里填真实环境变量。

后续必须动作：

- 在 Dify 后台轮换/废弃已入库过的旧 key。
- 真正的生产 key 只能放在本机 `.env`、部署平台 Secret、CI Secret 或密码管理器里，不能再写进 markdown、代码或测试快照。

### 2. 证书 aliases 输出去重

涉及文件：

- `api/services/v2_api.py`
- `api/tests/test_v2_api.py`

背景：

- `core.certificate_alias` 使用 `normalized_alias` 做唯一约束。
- 真实数据或烟测数据可能出现同一个展示名，例如“执业药师”或“一建”，对应多个不同 normalized alias。
- 如果接口直接返回所有 alias 行，前端会展示重复标签。

处理方式：

- `list_certificates()` 查询 alias 后按展示文本去重。
- `get_certificate_detail()` 查询 alias 后按展示文本去重。
- 新增测试 `test_v2_certificate_query_deduplicates_display_aliases`。

## 验证结果

| 检查项 | 命令 | 结果 |
|---|---|---|
| V2 API 定向测试 | `py -m pytest api/tests/test_v2_api.py -q` | `6 passed` |
| 后端 + 数据库全量测试 | `py -m pytest api/tests db/tests -q` | `143 passed` |
| Python lint | `py -m ruff check api db` | `All checks passed` |
| Python typecheck | `py -m pyright api db --pythonversion 3.12` | `0 errors` |
| Alembic 漂移检查 | `py -m alembic check` | `No new upgrade operations detected` |
| Dify 明文 key 扫描 | `git grep -n -E 'app-[A-Za-z0-9_-]{20,}\|dify-api-key:app-' -- . ':!.env' ':!node_modules'` | 无命中 |
| 前端 H5 构建 | `npm.cmd run build:h5` | 构建成功，有 webpack 体积 warning |

说明：

- `alembic check` 仍会打印 `Ignoring nullable change on identity column 'fragment.search_tsv'`，这是当前 env.py 中的已知过滤行为，不是新的 schema 漂移。
- `npm.cmd run typecheck` 和 `npm.cmd run lint` 仍存在历史基线问题；本轮 P1 改动不引入新的前端源码问题。
  - typecheck 主要集中在 Taro/node_modules 类型与 `config/index.ts` 的既有问题。
  - lint 主要集中在 `ExamArticle`/`TopicFinder` 中既有的 `confirm`、`select`、hook dependency 问题。

## P1 审计观察

### 数据库结构

- 当前 V2 schema 已覆盖 MVP 主链路所需的核心域：
  - `core`
  - `content`
  - `knowledge`
  - `policy`
  - `assessment`
  - `generation`
  - `ingestion`
  - `iam`
- Alembic 当前模型与迁移无新增漂移。
- PostgreSQL 连接、本地 Docker 数据库、DBeaver 观察到的 schema 与迁移结果一致。

### API 与权限

- 已验证 `/api/v2/*` 主链路能支撑：
  - 证书检索
  - 证书详情
  - 考期/考试科目
  - 报考条件判定
  - 知识检索
  - 试卷题目检索
  - MVP 生成接口
- 权限模型按 `principal_type + principal_code` 控制内部资料可见性。
- 前次真实数据烟测中：
  - `org_teaching_materials` 可以访问授权资料。
  - `org_operations` 对内部教材资料返回 `403 ACCESS_DENIED`。

### 前端

- H5 build 成功。
- 前端通过 `src/services/httpClient.ts` 和 `src/services/generationApi.ts` 接入后端 V2 API。
- `src/services/dify.ts` 已是兼容层，不再让浏览器直接持有或调用 Dify key。
- 历史 lint/typecheck 债务不属于 P1 阻塞，但建议另开 WP 或 P 阶段集中治理。

### 安全与配置

- 当前文件中的 Dify 明文 key 已清理。
- 由于 key 曾进入 git 历史，单纯当前替换不等于安全；必须轮换 key。
- `.env` 不应入库；`.env.example` 只保留示例值。

## P2 前置建议

P1 完成后，可以进入 P2：选择一个真实科目做小规模真实数据迁移和闭环演示。

建议 P2 继续使用前次 smoke 选择的科目：

- 证书：执业药师
- 科目：药学专业知识（一）
- 数据来源：旧库 `backups/policy_fact_baseline_20260629.sql` 中对应政策、知识点、试题记录

P2 不建议一开始全量迁移。先迁移最小闭环：

1. 证书与别名
2. 考试科目
3. 1 条政策条款
4. 1 条报考规则
5. 1 个知识点
6. 1 道题或 1 组题
7. 1 条资料 fragment
8. 1 次前端 API 完整演示

验收通过后再扩展第二个科目或批量导入模板。

## P1 判定

P1 当前状态：可以验收。

进入 P2 前唯一需要人工确认的外部动作：

- 轮换/废弃曾经写入仓库历史的 Dify API Key。
