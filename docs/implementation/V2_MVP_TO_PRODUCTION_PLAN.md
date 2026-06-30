# V2 MVP 后续实施计划书：从可跑通到可正式使用

> 当前状态：2026-06-30，V2 MVP 已完成并已用真实旧库样例跑通一条业务链路。本文用于接下来“一步一步来”的执行，不是一次性全量上线方案。

## 0. 当前结论

V2 当前可以判定为“技术 MVP 成功”：

- DBeaver 已能连接 `knowledge_platform_v2`，端口 `localhost:5434`；
- 数据库 schema 已包含 `iam / core / knowledge / policy / assessment / content / generation / ingestion`；
- Alembic 已能升到当前最新 revision；
- WP00-WP16 已按 MVP 口径完成；
- 已用旧库真实样例跑通：
  - 证书：执业药师；
  - 科目：药学专业知识（一）；
  - 政策条款：`clause_pharmacist_03`；
  - 知识点：`kp_pharmacist_03` / 药代动力学；
  - 题目：`q_pharmacist_03`；
  - API：证书查询、考试事件、报考判断、知识检索、题目查询；
  - 权限：教材部可读内部资料，运营部读内部资料返回 403。

这说明 V2 架构可以承接真实旧库数据并完成核心业务闭环。

但它还不是生产上线完成。后续目标是把 MVP 从“能跑”推进到“可审计、可批量迁移、可灰度、可回滚、可交给业务使用”。

## 1. 执行原则

后续每一步只做一个可验收目标，不混做。

1. 先审计，再扩数据。
2. 先小批真实数据，再 100 条黄金集。
3. 先后端/API 稳定，再前端体验完善。
4. 先 Dify 后端化联调，再放开生成场景。
5. 先恢复/回滚演练，再灰度。
6. 未通过退出条件，不进入下一阶段。

所有阶段都必须保留这些硬底线：

- 不提交 `.env` 和真实密钥；
- 前端不持有 Dify key；
- 私有/内部资料必须经过 ACL；
- approved/published 数据必须有审核人或审核证据；
- 任何“无法确定”的旧库数据进入 `needs_review` 或等价清单，不自动当事实发布；
- 每阶段结束必须更新报告，不能只口头说通过。

## 2. 后续阶段总览

| 阶段 | 目标 | 是否改代码 | 是否改数据库数据 | 退出条件 |
|---|---|---:|---:|---|
| P0 | 收口当前状态 | 否 | 否 | 文档提交/push，远端和两台设备一致 |
| P1 | 审计 `825648f` | 可能 | 否 | 明显代码/schema/API/权限问题已列清并修完 |
| P2 | 真实数据小批迁移 | 可能 | 是 | 5 个证书、2 本教材/教辅、100 个知识点、200 道题可查 |
| P3 | 黄金集与差异确认 | 可能 | 是 | 100 条真实问题有人工答案、V2 结果、差异分类 |
| P4 | API/前端业务闭环增强 | 是 | 少量 | 前端能稳定使用 V2 证书/考试/知识/生成后端接口 |
| P5 | Dify/模型网关联调 | 是 | 少量 | 后端持 key，生成结果有引用、权限和审计 |
| P6 | 运维生产化补证 | 可能 | 是 | 备份恢复、压测、监控、回滚、灰度计划有证据 |
| P7 | 内部灰度试用 | 可能 | 是 | 小范围真实用户使用，无 P0/P1 数据或权限事故 |

## 3. P0：收口当前状态

### 目标

让 Windows、Mac、后续 Agent、DBeaver 看到的是同一套事实。

### 当前已知

- 远端已有 `825648f feat: complete v2 knowledge platform mvp`；
- 本机还有一笔文档整理提交：`5e7f9e4 docs: summarize v2 mvp full flow`，当前尚未 push；
- 本地 V2 数据库里有 `SMOKE_REAL_*` 验证数据，这是本地冒烟数据，不是正式迁移数据。

### 执行

1. 确认 `git status -sb`。
2. push 当前文档提交。
3. 在 Mac 设备 pull，确认能看到：
   - `docs/implementation/V2_MVP_FULL_FLOW.md`
   - `docs/implementation/V2_MVP_TO_PRODUCTION_PLAN.md`
4. 记录本地 DBeaver 连接：
   - host: `localhost`
   - port: `5434`
   - database: `knowledge_platform_v2`
   - user: `v2_user`

### 验收

```bash
git status -sb
git log --oneline -5
```

DBeaver 能看到：

```text
assessment
content
core
generation
iam
ingestion
knowledge
policy
public
```

### 停止点

P0 完成后再进入 P1。不要在 P0 顺手改业务代码。

## 4. P1：统一审计 `825648f`

### 目标

先确认 MVP 代码和数据库设计有没有明显坑，避免真实数据越迁越多后再返工。

### 审计范围

1. 数据库 schema：
   - FK 是否完整；
   - 唯一约束是否合理；
   - published/approved 状态机是否能阻止脏数据；
   - ACL 是否覆盖所有私有资料读取路径；
   - 索引是否支撑 MVP 查询。
2. Alembic：
   - `upgrade head` 成功；
   - `alembic check` 干净；
   - SQLAlchemy metadata 与 migration 无漂移。
3. API：
   - `/api/v2/certificates`
   - `/api/v2/certificates/{code}/exam-events`
   - `/api/v2/eligibility/evaluate`
   - `/api/v2/knowledge/search`
   - `/api/v2/generations`
4. 权限：
   - 匿名 401；
   - 无权 403；
   - 内部/受限资料不泄漏标题和正文；
   - 生成引用不能越权。
5. 前端：
   - V2 feature flag；
   - httpClient；
   - 证书/考试/生成接口接入；
   - 不再浏览器直连 Dify。

### 执行

建议按三轮审计：

1. 静态审计：读代码和 migration；
2. 自动门禁：跑测试、ruff、pyright、alembic；
3. 真实链路冒烟：复跑执业药师样例，并新增一个“一建”只含主数据的负向样例。

### 验收

至少记录：

```bash
py -m pytest api/tests db/tests -q
py -m ruff check api db
py -m pyright api db --pythonversion 3.12
py -m alembic check
```

如果改了前端：

```bash
npm run build:h5
npm run typecheck
npm run lint
```

### 产物

- `docs/implementation/reports/P1_REVIEW_825648F.md`
- 如有修复，单独提交，不和 P2 数据迁移混在一起。

## 5. P2：真实数据小批迁移

### 目标

不追求全量，先把真实数据按 V2 结构迁一小批，证明映射方案可重复。

### 建议范围

第一批：

- 5 个证书；
- 每个证书至少 1 个科目；
- 至少 20 份政策/政策条款；
- 2 本教材或教辅资料；
- 100 个知识点；
- 200 道题；
- 30 条私有/内部资料片段；
- 10 条生成样例。

优先顺序：

1. 执业药师：因为旧库数据最完整，适合打通全链路；
2. 一级建造师：因为业务关注度高，但旧库目前政策/题库数据不完整，需要标记缺口；
3. 法考：政策条款和题目较完整；
4. 执业医师：题目和政策较完整；
5. 卫生职称或康复治疗师：用于测试多证书、多科目。

### 执行

1. 建 `staging` 或导入脚本，不直接手工改正式表。
2. 旧 ID 映射到 V2 code。
3. 对每条旧数据给出状态：
   - `mapped`
   - `rejected`
   - `needs_review`
4. 迁移顺序：
   - 证书/别名/科目；
   - 组织/集合/ACL；
   - 资产；
   - 资产版本；
   - 片段；
   - 知识点；
   - 片段-知识点映射；
   - 政策文档/条款/规则/证据；
   - 考试事件/分数线；
   - 教材/章节；
   - 试卷/题目；
   - 生成引用。

### 验收

每批结束必须输出：

- 行数统计；
- 映射统计；
- `needs_review` 清单；
- 10 条 API 抽样结果；
- 3 条权限负向测试。

### 产物

- `docs/implementation/data-migration/P2_BATCH_001_MAPPING.md`
- `docs/implementation/data-migration/P2_BATCH_001_NEEDS_REVIEW.csv`
- `docs/implementation/reports/P2_BATCH_001_SELF_TEST.md`

## 6. P3：100 条黄金集与业务确认

### 目标

从“能查到”升级到“查得准、答得准、引用准、权限不漏”。

### 黄金集结构

每条至少包含：

- 问题；
- 证书 code；
- 科目 code；
- 期望答案；
- 期望引用；
- 权限场景；
- 业务负责人；
- 差异分类。

### 差异分类

- `v2_correct_old_wrong`
- `old_correct_v2_wrong`
- `both_correct_format_diff`
- `data_missing`
- `policy_ambiguous`
- `permission_expected_denied`
- `needs_business_decision`

### 验收指标

生产化前建议最低线：

- 结构化查询准确率 ≥ 99%；
- 引用正确率 ≥ 98%；
- restricted/internal 越权泄漏 = 0；
- 无引用事实 = 0；
- P0/P1 缺陷 = 0。

### 产物

- `docs/implementation/evaluation/golden_cases_100.jsonl`
- `docs/implementation/reports/P3_GOLDEN_SET_REPORT.md`

## 7. P4：API 与前端业务闭环增强

### 目标

让真实用户能从前端稳定使用 V2，而不是只靠后端 API 冒烟。

### 范围

1. 证书下拉；
2. 考试时间/分数线；
3. 报考条件判断；
4. 知识检索结果；
5. 题目/教材引用展示；
6. 生成结果引用展示；
7. 错误提示和权限提示。

### 不做

- 不在前端写死证书/考试数据；
- 不在前端保存 Dify key；
- 不直接从浏览器连 DB、MinIO、Dify。

### 验收

- H5 build 通过；
- V2 feature flag 开关可回退；
- 主要页面最少 5 条真实数据可展示；
- 无权限时不泄漏资料标题和正文。

## 8. P5：Dify/模型网关联调

### 目标

把生成从“本地 MVP 后端任务”升级为真实模型网关/Dify 调用，但保持后端持密钥和引用审计。

### 执行

1. 后端读取 Dify/API 网关密钥；
2. 请求前先做知识检索和 ACL；
3. 生成任务写入 `generation.run`；
4. 引用写入 `generation.citation`；
5. 输出写入 `generation.output`；
6. 前端只拿后端任务状态和结果。

### 验收

- 真实生成成功；
- 失败能落库；
- 引用不能为空；
- restricted/internal 权限符合预期；
- 日志不打印密钥。

## 9. P6：运维生产化补证

### 目标

证明系统出问题时能恢复、能回滚、能观察。

### 必做

1. 数据库备份；
2. 对象存储备份；
3. 恢复演练；
4. 查询性能基准；
5. API 5xx 和延迟监控；
6. 权限拒绝监控；
7. 生成失败监控；
8. feature flag 回滚；
9. 旧库只读保留。

### 验收

- 恢复后行数一致；
- 关键表哈希一致；
- 引用关系一致；
- P95 查询延迟在可接受范围；
- 旧库至少保留两个发布周期；
- 有上线报告、恢复报告、旧库退役决策。

## 10. P7：内部灰度试用

### 目标

让小范围真实用户使用 V2，确认业务价值和稳定性。

### 灰度顺序

1. 内部测试账号；
2. 教材部/教辅部小范围；
3. 运营部只读查询；
4. 10% 流量；
5. 50% 流量；
6. 全量。

### 回滚条件

出现以下任一情况立即停止灰度：

- P0/P1 数据错误；
- 权限泄漏；
- 生成无引用事实；
- 关键 API 大面积 5xx；
- 业务负责人判定答案不可用。

## 11. 推荐下一步

下一步建议先执行 P0，然后 P1。

具体顺序：

1. P0：push 当前文档和计划书，让两台设备同步。
2. P1：审计 `825648f`，先把明显问题处理掉。
3. P2：做第一批真实数据迁移，优先执业药师 + 一建。
4. P3：建立 100 条黄金集。

不要直接跳到 P5/P6/P7。MVP 刚跑通，现在最怕“感觉能用了于是直接扩大使用范围”，那样会把数据质量、权限和引用问题放大。

## 12. 当前等待用户确认

请确认下一步从哪一项开始：

- `P0`：先同步代码和计划书；
- `P1`：开始审计 `825648f`；
- `P2`：开始真实数据小批迁移；
- `修改计划`：先调整本文阶段或范围。

在你确认前，不做功能代码改动。
