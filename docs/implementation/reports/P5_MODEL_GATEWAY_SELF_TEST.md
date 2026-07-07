# P5 模型网关联调自测报告

Date: 2026-06-30  
Scope: P5 MVP — 后端模型网关边界、Dify 配置入口、生成失败落库、引用非空门禁、密钥不进前端。

## 变更范围

- 新增 `api/services/model_gateway.py`
  - 后端统一模型网关。
  - 默认 `GENERATION_PROVIDER=local`，保持本地开发可运行。
  - 配置 `GENERATION_PROVIDER=dify` 且后端存在 `DIFY_API_URL` / `DIFY_API_KEY` 时，非 restricted 的 approved external 路由会调用 Dify `/v1/workflows/run`。
  - Dify 错误只返回脱敏错误码/消息，不返回响应体和密钥。
- 更新 `api/services/generation_workflow.py`
  - 生成链路调整为：ACL/检索 → 引用非空检查 → `generation.run=running` → `generation.citation` → 模型网关 → 成功写 `generation.output` + `run=succeeded`，失败写 `run=failed`。
  - 无可读引用时不生成 output，直接落 `run=failed`。
  - restricted 资料保持 `modelRoute=internal`，不会发往 Dify。
- 更新 `api/config.py`
  - 新增 `generation_provider`、`model_gateway_timeout_seconds`。
- 更新 `.env.example`
  - 新增后端专用模型网关配置示例；前端仍不持有 Dify key。
- 更新 `api/tests/test_generation_workflow.py`
  - 覆盖网关成功、网关失败落库、无引用失败、restricted 内部路由。

## 自测命令

```powershell
py -m pytest api\tests\test_generation_workflow.py -q
py -m ruff check api\services\model_gateway.py api\services\generation_workflow.py api\tests\test_generation_workflow.py api\config.py
py -m pytest api\tests db\tests -q
py -m ruff check api db scripts
py -m pyright api db --pythonversion 3.12
py scripts\p3_golden_eval.py docs\implementation\evaluation\p3_golden_cases.batch001.jsonl
npm.cmd run build:h5
rg -n "(sk-[A-Za-z0-9_-]{20,}|app-[A-Za-z0-9_-]{20,}|Bearer\s+[A-Za-z0-9._-]{20,}|DIFY_API_KEY\s*=\s*[^\s#<]+|TARO_APP_DIFY|password\s*=\s*[^\s#]+|secret\s*=\s*[^\s#]+)" api db src config docs\implementation infra .env.example .env.development .env.production .env.test -S
```

## 当前结果

| Gate | Result | Evidence |
| --- | --- | --- |
| 定向生成测试 | PASS | `6 passed in 1.38s` |
| 定向 ruff | PASS | `All checks passed!` |
| 全量后端测试 | PASS | `156 passed in 10.47s` |
| 全量 ruff | PASS | `All checks passed!` |
| pyright | PASS | `0 errors, 0 warnings, 0 informations` |
| P3 黄金集 | PASS | `status=pass`, structuredAccuracy 1.0, citationAccuracy 1.0, restrictedLeakRate 0.0 |
| H5 build | PASS | `webpack compiled with 2 warnings`，仅既有 asset/entrypoint size warning |
| Secret scan | PASS | 仅命中历史文档/测试里的占位说明：WP13/WP14 文档、`test_acceptance.py` 的 fake key 测试和扫描命令文本；未发现真实 Dify key |
| 网关成功路径 | PASS | monkeypatch 模拟 Dify 返回，`generation.run.model_provider=dify`，output 写入 gateway metadata，cards 自动补 citations |
| 网关失败落库 | PASS | monkeypatch 抛 `MODEL_GATEWAY_TIMEOUT`，`generation.run.status=failed`，citation 保留，output 为 0 |
| 引用不能为空 | PASS | 无可读引用时返回 `status=failed` + `GENERATION_REQUIRES_CITATION`，不写 output |
| restricted/internal 权限 | PASS | restricted 生成保持 `modelRoute=internal`，引用 confidentiality 保持 restricted |

## 真实 Dify 联调说明

本次未在本机真实调用 Dify，因为工作区没有可安全输出/验证的生产密钥，且自测不能依赖外网和真实账户状态。代码已留下真实联调入口：

```env
GENERATION_PROVIDER=dify
DIFY_API_URL=https://api.dify.ai
DIFY_API_KEY=<backend-only-secret>
MODEL_GATEWAY_TIMEOUT_SECONDS=30
```

真实联调时必须执行：

1. 只在后端 `.env` 填入 `DIFY_API_KEY`，不要写入 `.env.development` / `.env.production` 的 `TARO_APP_*` 前端变量。
2. 使用拥有 `coll_internal` 读取权限的身份调用 `/api/v2/generations`。
3. 确认响应：
   - `status=succeeded`
   - `modelRoute=approved_external`
   - `citations` 非空
   - `cards[*].citations` 非空
4. 在数据库确认：
   - `generation.run.model_provider='dify'`
   - `generation.run.status='succeeded'`
   - `generation.citation` 至少 1 条
   - `generation.output.content.gateway.provider='dify'`
5. 临时改错 `DIFY_API_URL` 或网关超时，确认失败请求：
   - API 返回 `status=failed`
   - `generation.run.status='failed'`
   - 不写 `generation.output`
   - 错误信息不包含 key、Authorization header 或 Dify 原始响应体。

## 风险与停止点

- P5 还不是异步队列/SSE；仍沿用同步 API 返回任务结果。
- Dify workflow 的 outputs 字段必须返回 `cards`、`result.cards`、JSON 字符串，或纯文本；否则会进入 `MODEL_GATEWAY_EMPTY_OUTPUT`。
- 真实 Dify 成功需由有密钥环境补一次 smoke，本报告只证明代码路径和审计边界已就绪。
