# API 与前端接入

## 一、接入原则

1. 前端只调用企业 API，不直接调用 PostgreSQL、Dify 或对象存储。
2. API 根据登录用户计算可访问 collection，并把权限条件注入检索。
3. 所有列表使用 cursor pagination；所有写入使用幂等键。
4. API 返回稳定 code，不把内部 bigint 当跨系统 ID。
5. 政策回答必须返回结构化判断、引用和置信状态，不能只返回自然语言。

## 二、核心接口

### 证书与考试

```http
GET /api/v2/certificates?query=一建&cursor=&limit=20
GET /api/v2/certificates/{certificateCode}
GET /api/v2/certificates/{certificateCode}/exam-events?year=2026&region=CN
```

证书响应：

```json
{
  "items": [
    {
      "code": "cls1_constructor",
      "name": "一级建造师",
      "aliases": ["一建"],
      "nextExam": {
        "eventCode": "CLS1_2026_CN",
        "phases": [{"type": "written", "startsOn": "2026-09-19"}]
      }
    }
  ],
  "nextCursor": null
}
```

### 报考条件判断

```http
POST /api/v2/eligibility/evaluate
```

```json
{
  "certificateCode": "nle",
  "degreeLevelCode": "bachelor",
  "majorCategoryCode": "non_law",
  "educationTypeCode": "full_time",
  "relevantWorkMonths": 36,
  "admissionDate": "2020-09-01",
  "regionCode": "CN"
}
```

响应必须可解释：

```json
{
  "decision": "eligible",
  "matchedRuleCode": "NLE_NORMAL_02",
  "requirements": [{"field": "relevantWorkMonths", "required": 36, "actual": 36, "passed": true}],
  "citations": [{
    "assetCode": "POLICY_NLE_2018",
    "versionNo": 1,
    "fragmentCode": "ARTICLE_09",
    "title": "国家统一法律职业资格考试实施办法",
    "section": "第九条",
    "quote": "……从事法律工作满三年……"
  }],
  "reviewedAt": "2026-06-01T10:00:00+08:00"
}
```

无法判断返回 `insufficient_data`，不得猜测。

### 知识检索

```http
POST /api/v2/knowledge/search
```

```json
{
  "query": "非法学本科报考法考需要几年工作经验",
  "collectionCodes": ["public_policy", "internal_textbook"],
  "knowledgePointCodes": ["LAW_QUAL_ELIGIBILITY"],
  "assetTypes": ["policy", "textbook"],
  "topK": 8
}
```

服务端步骤：身份认证 → collection ACL → 状态/有效期过滤 → 结构化查询 → 全文/向量召回 → 重排 → 返回片段。客户端传入无权集合时应返回 403 或忽略，不能泄漏集合是否存在。

### 生成内容

```http
POST /api/v2/generations
GET /api/v2/generations/{runId}
POST /api/v2/generations/{runId}/approve
```

生成请求只传业务需求和允许使用的集合。API 检索授权片段后调用 Dify，并记录 `generation.run/citation/output`。

```json
{
  "applicationCode": "exam_article",
  "outputType": "card_set",
  "certificateCode": "nle",
  "collectionCodes": ["public_policy", "internal_textbook"],
  "knowledgePointCodes": ["LAW_QUAL_ELIGIBILITY"],
  "inputs": {
    "examDate": "2026-09-19",
    "targetAudience": "非法学本科",
    "theme": "报考条件"
  },
  "idempotencyKey": "client-generated-uuid"
}
```

restricted 集合若不允许外部模型，API 应拒绝或路由到批准的本地/私有模型。

### 后台管理

```http
POST /api/v2/admin/assets
POST /api/v2/admin/assets/{assetCode}/versions
POST /api/v2/admin/import-batches
GET  /api/v2/admin/import-batches/{batchId}/errors
POST /api/v2/admin/reviews/{entityType}/{code}/approve
```

## 三、错误模型

统一格式：

```json
{
  "error": {
    "code": "ELIGIBILITY_INSUFFICIENT_DATA",
    "message": "缺少入学时间，无法区分普通路径与老人老办法",
    "fieldErrors": [{"field": "admissionDate", "code": "required_for_route"}],
    "requestId": "req_..."
  }
}
```

数据库不可用返回 503，严禁像现有 `_query()` 一样吞异常并返回空数组。

## 四、当前 Taro 项目改造

### 1. 配置

删除前端硬编码的 Dify API Key。仅保留：

```env
TARO_APP_API_BASE_URL=https://api.example.internal
```

### 2. API Client

增加：

```text
src/services/httpClient.ts
src/services/certificateApi.ts
src/services/knowledgeApi.ts
src/services/generationApi.ts
src/types/api.ts
```

统一 `httpClient` 负责：Authorization、requestId、超时、错误解析和 401 刷新。

```ts
export async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${getAccessToken()}`,
      ...init?.headers,
    },
  })
  if (!response.ok) throw await ApiError.fromResponse(response)
  return response.json() as Promise<T>
}
```

### 3. 证书下拉

现有 `fetchCerts()` 改调 `/api/v2/certificates`；UI 使用 `code` 作为 value。选择证书后请求考试场次，禁止前端常量维护考试日期。

### 4. 内容生成

现有 `generateCards()` 不再直接请求 `/v1/workflows/run`，改为创建 generation：

```text
POST /api/v2/generations
→ 返回 runId
→ SSE /api/v2/generations/{runId}/events
→ completed 后 GET run
```

后端负责 Dify 凭证、资料检索、引用、权限和审计。SSE 事件应包含 queued/retrieving/generating/reviewing/completed/failed。

### 5. 引用展示

生成卡片应携带 `citations[]`。审核界面显示资料标题、版本、章节/页码、保密等级。政策数字缺少引用时禁止通过审核。

### 6. 权限体验

- 前端可展示用户有权使用的知识集合；
- 不允许访问的集合不出现在选择器中；
- restricted 输出禁止普通下载/复制时，需要后端策略和水印配合，不能只靠前端隐藏按钮。

## 五、API 安全和性能

- 读取接口使用只读数据库角色；写入和审批分角色；
- 所有 collection 查询包含 ACL 条件；
- 使用 Pgbouncer，不在 Python 全局 list 手写连接池；
- 对 search/generation 限流；
- 记录 requestId、userId、collectionId、fragmentId，但日志不记录 restricted 正文；
- 大文件上传使用对象存储预签名 URL；
- 列表使用游标分页；
- 对 `(certificate_id, region_code)`、外键、published/approved 部分索引进行 EXPLAIN 验证。
