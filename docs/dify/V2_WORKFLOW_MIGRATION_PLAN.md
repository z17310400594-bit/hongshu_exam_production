# Dify 小红书生产工作流 V2 改造计划书

## 1. 背景与结论

当前导出的 Dify 工作流 `小红书生产.yml` 仍是旧模式：

- Dify 内部通过“查询数据库”代码节点调用 `http://policy-api:8400/query/*`。
- 工作流自己组装 `db_data_json`、`facts_brief`、`knowledge_points`、`exam_questions`、`policy_clauses` 等上下文。
- Dify 直接承担“查库 + 数据裁剪 + prompt 构造 + 逐卡生成 + 输出清洗”。

V2 已经完成了后端化生成链路：

- 前端只调用 `/api/v2/generations`。
- 后端负责 ACL、知识片段检索、引用、保密等级、模型路由和生成审计。
- 后端通过 `api/services/model_gateway.py` 调 Dify 或本地生成器。
- 生成结果写入 `generation.run / generation.citation / generation.output`。

因此，Dify 不应再直接查旧库。Dify 在 V2 中的定位应改为：

> 只做“卡片文案生成器”，接收 V2 后端传入的授权上下文和引用，输出结构化 cards JSON。

## 2. 改造目标

### 2.1 必须达成

1. 删除或旁路 Dify 工作流中的“查询数据库”节点。
2. Dify 不再调用 `policy-api:8400/query/*`。
3. Dify 输入改为匹配 V2 后端网关：

```json
{
  "applicationCode": "exam_article",
  "outputType": "card_set",
  "certificateCode": "c_xxx",
  "generationInputs": {
    "examName": "一级建造师",
    "examDate": "2026-09-20",
    "targetAudience": "在职备考",
    "theme": "30天冲刺",
    "role": "小红书-建工号"
  },
  "cardSequence": ["cover", "plan", "subjects", "notice", "cta"],
  "citations": [
    {
      "assetCode": "asset_xxx",
      "assetTitle": "政策文件",
      "assetType": "policy",
      "versionNo": 1,
      "fragmentCode": "frag_xxx",
      "heading": "报名条件",
      "pageFrom": 1,
      "pageTo": 1,
      "confidentiality": "internal",
      "quote": "授权后的短引用"
    }
  ]
}
```

4. Dify 输出固定为：

```json
{
  "cards": [
    {
      "type": "cover",
      "title": "",
      "subtitle": "",
      "days": [],
      "items": [],
      "qrcode_url": "",
      "study_material": [],
      "citations": []
    }
  ]
}
```

5. Dify 输出的每张卡必须保留或继承 citations，便于前端审核和后端审计。

### 2.2 明确不做

- 不让 Dify 直接连 PostgreSQL。
- 不让 Dify 直接调用 MinIO。
- 不把数据库密码、Dify Key、模型 Key 放到前端。
- 不在 Dify 里做权限过滤。
- 不在 Dify 里做完整数据清洗和来源判断。
- 不把全量长文档、全量题库、全量政策 JSON 塞进 prompt。

## 3. 新架构路线

### 3.1 调用链路

```text
Taro 前端
  -> POST /api/v2/generations
       输入：证书、考试日期、卡片序列、角色、人群、主题

V2 后端
  -> 校验身份和 collection ACL
  -> 检索 approved + ACL-readable fragments
  -> 生成 citations
  -> 判断 confidentiality / modelRoute
  -> 写 generation.run
  -> 调 Dify workflow
  -> 写 generation.citation / generation.output
  -> 返回 cards + citations

Dify workflow
  -> 接收 generationInputs / cardSequence / citations
  -> 主编节点生成叙事策略
  -> 逐卡生成 JSON
  -> 清洗合并输出 cards
```

### 3.2 责任边界

| 层 | 职责 |
|---|---|
| 前端 | 收集用户输入、展示生成结果、展示引用、审核前检查 citations |
| V2 后端 | 权限、检索、引用、保密级别、模型路由、审计、Dify Key |
| Dify | 文案生成、卡片结构化输出 |
| PostgreSQL | 结构化事实、片段、知识点、政策、题库、生成审计 |
| MinIO | PDF/Word/图片原文件 |

## 4. Dify 工作流设计

### 4.1 推荐节点

保留 6 类节点即可：

```text
Start
  -> 输入适配 Code
  -> 主编 LLM
  -> 卡片列表准备 Code
  -> Iteration
       -> 单卡 Prompt Code
       -> 单卡 LLM
       -> 单卡 JSON 清洗 Code
  -> 聚合清洗 Code
  -> End
```

### 4.2 删除或旁路的旧节点

必须删除或断开：

- `查询数据库`
- 调用 `http://policy-api:8400/query/cert_lookup`
- 调用 `http://policy-api:8400/query/policy`
- 调用 `http://policy-api:8400/query/knowledge`
- 调用 `http://policy-api:8400/query/viral`

可以保留但需瘦身：

- `LLM 主编`
- `遍历cardsType`
- `构造cardPrompt` / `代码执行 5`
- `清洗llm输出`

### 4.3 Start 输入

Dify Start 节点建议改成以下变量：

| 变量 | 类型 | 说明 |
|---|---|---|
| `applicationCode` | text | 例如 `exam_article` |
| `outputType` | text | 例如 `card_set` |
| `certificateCode` | text | V2 证书 code |
| `generationInputs` | paragraph/text | JSON 字符串 |
| `cardSequence` | paragraph/text | JSON 数组字符串 |
| `citations` | paragraph/text | JSON 数组字符串 |

如果 Dify 支持 object/array 类型，也可以用原生 JSON 类型；否则统一用字符串，在第一个 Code 节点解析。

### 4.4 输入适配 Code

职责：

- 解析 `generationInputs`。
- 解析 `cardSequence`。
- 解析 `citations`。
- 生成 `facts_brief`，但只从 citations 和必要输入生成，不查数据库。
- 生成每张卡的 `current_card` 基础结构。

输出：

```json
{
  "exam_name": "一级建造师",
  "exam_date": "2026-09-20",
  "role": "小红书-建工号",
  "target_audience": "在职备考",
  "theme": "30天冲刺",
  "cards": [
    {
      "type": "cover",
      "index": 1,
      "total_cards": 5,
      "citations": []
    }
  ],
  "facts_brief": "基于 V2 引用片段压缩后的事实摘要"
}
```

### 4.5 主编 LLM

主编节点仍保留，但输入改为：

- `exam_name`
- `exam_date`
- `role`
- `target_audience`
- `theme`
- `cardSequence`
- `facts_brief`

主编节点只输出叙事策略，不输出事实判断。

要求：

- 不新增政策数字。
- 不猜考试时间。
- 不编造报考条件。
- 只根据 `facts_brief` 和用户输入组织表达。

### 4.6 单卡 Prompt Code

沿用旧工作流的卡片类型能力，但数据源改成：

- `current_card`
- `facts_brief`
- `citations`
- `generationInputs`
- `narrative_plan`

不同卡片的数据策略：

| 卡片类型 | 数据来源 |
|---|---|
| `cover` | examName、examDate、targetAudience、theme、facts_brief |
| `plan` | examDate、countdownDays、phase 信息；真题只允许来自 citations 摘要 |
| `subjects` | 优先用 V2 后端后续提供的 subject 摘要；暂无时避免编具体分值 |
| `notice` | 只使用 citations 里的政策/考试安排/合格标准 |
| `resources` | 可生成通用资料清单，但不要声称公司已有资料，除非 citations 有来源 |
| `priority` | 无真实分值 citation 时，避免写“约 XX 分” |
| `mnemonics` | 只基于 citations 或 knowledge point 主题生成 |
| `study_material` | 只基于授权片段生成 2-3 个模块 |
| `cta` | 基于人群和主题生成行动引导 |

### 4.7 单卡 LLM

模型可继续用当前 DeepSeek 插件。

输出必须是单张卡 JSON，不能包含 Markdown 包裹。

建议 system prompt 加硬约束：

```text
你只能使用输入中的 facts_brief 和 citations 作为事实来源。
不得编造考试日期、报名时间、分数线、报考条件、政策条款。
如果缺少事实，使用“以官方通知为准”“待官方发布”为表达，不生成具体数字。
输出必须是纯 JSON。
每张卡必须包含 citations 字段；如果没有可用引用，citations 为空数组。
```

### 4.8 聚合清洗 Code

职责：

- 收集所有单卡输出。
- 解析 JSON。
- 兜底补齐字段：
  - `type`
  - `title`
  - `subtitle`
  - `days`
  - `items`
  - `qrcode_url`
  - `study_material`
  - `citations`
- 删除 Markdown 包裹。
- 严格输出：

```json
{
  "cards": []
}
```

## 5. V2 后端配套修改

### 5.1 当前已具备

已完成：

- `/api/v2/generations`
- `/api/v2/generations/{run_id}`
- `api/services/model_gateway.py`
- `GENERATION_PROVIDER=local|dify`
- `DIFY_API_URL`
- `DIFY_API_KEY`
- citations 审计
- restricted 资料不外发到未批准外部模型

### 5.2 建议增强

建议后端在调用 Dify 前，把输入整理得更贴近小红书工作流：

```json
{
  "generationInputs": {
    "examName": "...",
    "examDate": "...",
    "role": "...",
    "targetAudience": "...",
    "theme": "...",
    "countdownDays": 30,
    "phase1End": "...",
    "phase2End": "..."
  },
  "cardSequence": ["cover", "plan", "notice", "cta"],
  "citations": []
}
```

后端还可追加一个 `factsBrief` 字段，避免 Dify 每次自己摘要：

```json
{
  "factsBrief": "考试日期：...；政策依据：...；知识点：..."
}
```

### 5.3 推荐新增 helper

在 `api/services/model_gateway.py` 中新增：

- `_build_dify_inputs(...)`
- `_build_facts_brief(citations, inputs)`
- `_normalize_card_sequence(card_sequence)`

这样 Dify workflow 可以更薄，联调也更稳定。

## 6. 环境配置

`.env` 中开启 Dify：

```env
GENERATION_PROVIDER=dify
DIFY_API_URL=http://localhost:<dify-api-port>
DIFY_API_KEY=<后端专用 workflow api key>
```

注意：

- `DIFY_API_KEY` 只允许后端持有。
- 前端 `.env.*` 不得再出现 `TARO_APP_DIFY_*`。
- 如果 Dify 和 API 都在 Docker 网络中，`DIFY_API_URL` 可用容器服务名。
- 如果 V2 API 从宿主机调用 Dify，用 `http://localhost:端口`。

## 7. 联调步骤

### 7.1 Dify 单独调试

在 Dify 后台用以下最小输入跑一次：

```json
{
  "applicationCode": "exam_article",
  "outputType": "card_set",
  "certificateCode": "c_demo",
  "generationInputs": "{\"examName\":\"一级建造师\",\"examDate\":\"2026-09-20\",\"role\":\"小红书-建工号\",\"targetAudience\":\"在职备考\",\"theme\":\"30天冲刺\"}",
  "cardSequence": "[\"cover\",\"plan\",\"notice\",\"cta\"]",
  "citations": "[{\"assetCode\":\"asset_demo\",\"assetTitle\":\"示例政策\",\"assetType\":\"policy\",\"versionNo\":1,\"fragmentCode\":\"frag_demo\",\"heading\":\"考试安排\",\"pageFrom\":1,\"pageTo\":1,\"confidentiality\":\"internal\",\"quote\":\"考试安排以官方通知为准。\"}]"
}
```

期望输出：

```json
{
  "cards": [
    {
      "type": "cover",
      "title": "...",
      "subtitle": "...",
      "days": [],
      "items": [],
      "qrcode_url": "",
      "citations": []
    }
  ]
}
```

### 7.2 后端联调

启动 V2 API 后，请求：

```http
POST /api/v2/generations
```

请求体由前端当前 `src/services/generationApi.ts` 产生。

观察：

- HTTP 200
- `status=succeeded`
- `modelRoute=approved_external` 或 `internal`
- `cards` 非空
- `citations` 非空
- 数据库写入 `generation.run`
- 数据库写入 `generation.citation`
- 数据库写入 `generation.output`

### 7.3 前端联调

在图文生成页执行一次完整生成：

1. 选择证书。
2. 选择考试日期。
3. 选择卡片序列。
4. 点击生成。
5. 检查卡片正常渲染。
6. 检查引用列表正常展示。
7. 检查无 citations 时不能审核通过。

## 8. 验收标准

### 8.1 功能验收

- Dify workflow 不再调用旧 `/query/*`。
- 前端仍只调用 `/api/v2/generations`。
- Dify 返回 `cards`。
- 每张卡结构符合 `src/types/exam-article.ts`。
- 生成结果包含 citations。
- 后端可通过 `/api/v2/generations/{run_id}` 查询生成结果。

### 8.2 安全验收

- 前端无 Dify Key。
- Dify 不直接连 DB。
- Dify 不接收 restricted 原文，除非后端路由允许。
- 无权 collection 不会进入 citations。
- 生成输出不包含内部 DB id。
- 错误响应不包含密钥、连接串、内部路径。

### 8.3 质量验收

- 不编造考试日期、分数、报考条件。
- 政策/考试安排类数字能从 citations 找到来源。
- 没有来源时不写具体数字。
- 小红书语气保留，但事实边界更稳。

## 9. 分阶段实施

### 阶段 1：Dify 瘦身

目标：让 Dify 接收 V2 输入并输出 cards。

动作：

1. 复制当前 `小红书生产.yml` 为新 workflow。
2. 删除或断开“查询数据库”节点。
3. 新增输入适配 Code。
4. 改 Start 变量。
5. 保留主编和逐卡生成逻辑。
6. 改最终输出为 `{ "cards": [...] }`。

### 阶段 2：后端联调

目标：让 `model_gateway.py` 调通新 workflow。

动作：

1. 配置 `GENERATION_PROVIDER=dify`。
2. 配置 `DIFY_API_URL` 和 `DIFY_API_KEY`。
3. 用 `/api/v2/generations` 跑通。
4. 查看 `generation.output.content.gateway` 里的 workflow metadata。

### 阶段 3：质量收敛

目标：减少幻觉和格式错误。

动作：

1. 加强 prompt 的“事实只来自 citations”约束。
2. 聚合清洗节点补字段。
3. 对每类卡片准备 1 个样例。
4. 固定失败兜底：解析失败时返回 `type=text` 或明确错误。

### 阶段 4：生产前增强

目标：上线前可观测、可回滚。

动作：

1. 给 Dify workflow 版本号，例如 `xhs_card_workflow_v2_20260630`。
2. 后端记录 workflow run id。
3. 建 10 条小红书生成回归样例。
4. 记录生成耗时、token、失败原因。
5. 保留 `GENERATION_PROVIDER=local` 作为回滚开关。

## 10. 回滚方案

如果 Dify 新 workflow 不稳定：

1. `.env` 改回：

```env
GENERATION_PROVIDER=local
```

2. 重启 V2 API。
3. 前端仍可生成本地草稿。
4. 数据库审计链路不受影响。

如果只想回滚 Dify workflow：

1. 保留旧 workflow。
2. 后端 `DIFY_API_KEY` 换回旧 workflow key。
3. 但不建议长期回到旧“Dify 查库”模式。

## 11. 建议最终形态

长期建议把当前 Dify 工作流拆为两层：

```text
V2 API
  数据、权限、引用、审计、模型路由

Dify XHS Writer
  小红书语气、卡片文案、JSON 输出
```

这样后续增加公众号、短视频脚本、课程资料、模拟卷时，不需要每个 Dify workflow 都重新实现一遍查库、权限和引用逻辑。

