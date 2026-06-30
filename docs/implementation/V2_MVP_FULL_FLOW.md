# V2 MVP 全流程总览

> 当前版本：2026-06-30，从 Mac 设备完成任务后拉取到 Windows 工作区整理。本文是流程索引，不替代每个 WP 的追踪矩阵和自测报告。

## 1. 当前状态一句话

V2 知识资产平台已经完成 WP00-WP16 的 MVP 闭环。WP06-WP16 由 Mac 设备统一实现并推送为：

```text
825648f feat: complete v2 knowledge platform mvp
```

当前仍不是生产上线完成，而是“可演示、可继续补真实数据、可进入统一审计”的 MVP 版本。

## 2. 读取顺序

新会话、新设备或验收 Agent 按以下顺序读：

1. `docs/implementation/IMPLEMENTATION_STATUS.md`
2. `docs/implementation/NEXT_TASK.md`
3. `docs/implementation/V2_MVP_FULL_FLOW.md`
4. `docs/implementation/MVP_PLAN_WP06_PLUS.md`
5. 对应 `docs/implementation/work-packages/WPxx.md`
6. 对应 `docs/implementation/reports/WPxx_SELF_TEST.md`
7. `docs/implementation/design-package/20260629/`

注意：`design-package/20260629/07-按步骤实施计划.md` 是目标蓝图；WP06 之后的实际执行口径以 `MVP_PLAN_WP06_PLUS.md` 和各工作包文件为准。

## 3. 里程碑总览

| 阶段 | 包 | 结果 | 关键提交 |
|---|---|---|---|
| 基线与工程骨架 | WP00-WP01 | 建立备份、状态文件、FastAPI/Alembic/Docker 骨架 | `7fc8e3d`, `b2a0f39` |
| 权限与主数据 | WP02-WP03 | 组织、集合、ACL、证书、别名、科目 | `d6253d0`, `a4e560d` + registry fix |
| 资产与知识点 | WP04-WP05 | 资产/版本/片段/MinIO、知识点和片段映射 | `125677b`, `63dd920` |
| MVP 业务闭环 | WP06-WP14 | 政策、考试、教材、题库、生成、导入、API、前端最小接入 | `825648f` |
| 验收/发布框架 | WP15-WP16 | 黄金集/安全验收框架、灰度/恢复/旧库只读 runbook 校验框架 | `825648f` |

## 4. 工作包结果

| 包 | MVP 交付 | 主要文件入口 | 自测报告 |
|---|---|---|---|
| WP06 | policy document/version/clause/eligibility/evidence，报考判断最小闭环 | `api/models/policy.py`, `api/services/eligibility.py` | `reports/WP06_SELF_TEST.md` |
| WP07 | exam_event/phase/score_rule，考试场次最小可查 | `api/models/assessment.py`, `api/services/exam_events.py` | `reports/WP07_SELF_TEST.md` |
| WP08 | content product/version/chapter/chapter_kp，教材章节承接 | `api/models/content.py`, `api/services/content_products.py` | `reports/WP08_SELF_TEST.md` |
| WP09 | paper/question/question_kp，题库最小闭环 | `api/models/assessment.py`, `api/services/question_bank.py` | `reports/WP09_SELF_TEST.md` |
| WP10 | generation run/citation/output，生成引用审计 | `api/models/generation.py`, `api/services/generation_audit.py` | `reports/WP10_SELF_TEST.md` |
| WP11 | import_batch/validation_error，导入校验框架 | `api/models/ingestion.py`, `api/services/import_validation.py` | `reports/WP11_SELF_TEST.md` |
| WP12 | `/api/v2/certificates`, `/eligibility/evaluate`, `/knowledge/search` | `api/services/v2_api.py`, `api/main.py` | `reports/WP12_SELF_TEST.md` |
| WP13 | Taro 证书/考试最小接入、feature flag、httpClient | `src/services/httpClient.ts`, `src/services/certificateApi.ts` | `reports/WP13_SELF_TEST.md` |
| WP14 | 前端不直连 Dify，后端生成任务 + 引用展示最小链路 | `api/services/generation_workflow.py`, `src/services/generationApi.ts` | `reports/WP14_SELF_TEST.md` |
| WP15 | 双读/黄金集/安全验收框架 MVP | `api/services/acceptance.py`, `scripts/wp15_acceptance.py` | `reports/WP15_SELF_TEST.md` |
| WP16 | 灰度/恢复/回滚/旧库只读校验框架 MVP | `api/services/release_readiness.py`, `scripts/wp16_release.py` | `reports/WP16_SELF_TEST.md` |

## 5. 后端/API 主流程

```text
collection/ACL
→ asset/version/fragment
→ knowledge_point / fragment_knowledge_point
→ policy clause / eligibility rule / evidence
→ exam event / score rule
→ content chapter / question bank / generation citation
→ /api/v2/certificates
→ /api/v2/eligibility/evaluate
→ /api/v2/knowledge/search
→ Taro frontend httpClient + feature flags
```

权限原则：

- 所有知识检索必须带身份；
- ACL 在返回正文和标题前执行；
- pending/rejected 映射不进入高可信输出；
- restricted/private 内容不得对无权主体泄漏；
- 前端不直接持有 Dify key，不直接连 DB，不直接读对象存储。

## 6. 环境启动流程

完整开发环境建议：

```bash
git checkout feat/v2-knowledge-platform
cp .env.example .env
docker compose --env-file .env -f infra/compose.yaml up -d postgres minio redis
python -m alembic upgrade head
python -m alembic check
```

Windows 后端门禁：

```bat
cmd.exe /c scripts\validate.bat
```

Mac/Linux MVP 后端包可按手动门禁执行：

```bash
python -m pytest api/tests db/tests -q
python -m ruff check api db
python -m pyright api db --pythonversion 3.12
python -m alembic check
```

前端包或生产化阶段再跑：

```bash
npm run build:h5
npm run typecheck
npm run lint
```

## 7. 当前已知文档口径

- `IMPLEMENTATION_STATUS.md` / `NEXT_TASK.md` 已将 WP06-WP16 指向统一提交 `825648f`。
- 各 WP06-WP16 自测报告中部分 `Implementation SHA: local-not-committed` 是历史记录：报告生成时尚未打包提交，随后由 Mac 统一提交为 `825648f`。复核时以状态文件和本文为当前事实。
- `CURRENT_HANDOFF.md` 已同步为最新交接摘要；本文提供更完整的流程索引和复核口径。

## 8. 生产化仍需补的内容

MVP 完成不等于生产上线。进入生产化前至少还需要：

- 对 `825648f` 做统一 code review / schema review / security review；
- 用真实业务数据补 100 条黄金集；
- 业务负责人确认差异分类；
- 真实 Dify/模型网关接入与密钥轮换；
- 生产量级 migration/查询性能测试；
- 真实备份恢复演练；
- 灰度 feature flag 和回滚演练；
- 旧库只读保留和退役决策。

## 9. 推荐下一步

建议先做：

```text
Review 825648f → 修正明显问题 → 再决定是否进入真实数据/生产化补证。
```

不要直接把 MVP 当生产发布版本切流。
