# V3 小红书文章生产 Workflow — 配置文档

> 使用本文档在 Dify 后台搭建 7 节点文章生产流水线。
>
> 前置条件：policy-db 已导入全部数据，policy-api 容器运行中（`policy-api:8400`），Dify Worker 容器可通过 Docker 网络访问 policy-api。

---

## 一、节点拓扑

```
┌──────────┐    ┌──────────────────┐    ┌───────────────┐
│ ① START  │───▶│ ② 素材检索        │───▶│ ③ 标题生成     │
│ (Input)  │    │ CODE_fetch_       │    │ (LLM)         │
│          │    │ materials         │    │ 输出5个标题    │
└──────────┘    └──────────────────┘    └───────┬───────┘
                                                │ 人工选标题
                                                ▼
┌──────────┐    ┌──────────────────┐    ┌───────────────┐
│ ⑥ 事实校验│◀───│ ⑤ 封面+标签      │◀───│ ④ 正文生成     │
│ CODE_fact │    │ (LLM)           │    │ (LLM)         │
│ _check    │    │                 │    │ 注入检索结果   │
└────┬─────┘    └──────────────────┘    └───────────────┘
     │
     ▼
┌──────────┐
│ ⑦ END    │
│ (Output) │
└──────────┘
```

## 二、各节点详细配置

---

### 节点 ①：选题输入（Start / Input）

**节点类型**：Start

**输入变量**：

| 变量 | 类型 | 必填 | 说明 | 示例 |
|------|------|------|------|------|
| `cert_id` | string | ✅ | 证书 ID | `physician_licensed` |
| `topic` | string | ✅ | 选题方向 | `技能考试最后一个月备考攻略` |
| `audience` | string | ❌ | 目标人群 | `在职备考` / `宝妈备考` / `零基础` / `非科班` |
| `tone` | string | ❌ | 内容风格 | `干货型` / `痛点型` / `身份型` / `避坑型` |

---

### 节点 ②：素材检索（Code）

**节点类型**：Code

**代码**：复制 `docs/dify/v3/CODE_fetch_materials.py` 全部内容

**输入变量**：
| 变量 | 来源 |
|------|------|
| `cert_id` | `{{①.cert_id}}` |
| `topic` | `{{①.topic}}` |
| `audience` | `{{①.audience}}` |

**输出变量**：
| 变量 | 说明 |
|------|------|
| `policy_json` | 完整政策事实 JSON |
| `knowledge_json` | 考试科目 + 高频考点 + 真题 JSON（P0 新增） |
| `viral_samples_json` | 爆款样本数组 JSON |
| `brief_json` | 政策 + 知识摘要文本（注入 LLM prompt） |
| `cert_name` | 证书中文名 |

---

### 节点 ③：标题生成（LLM）

**节点类型**：LLM

**模型**：GPT-4o / Claude 3.5 Sonnet

**System Prompt**：

```
你是小红书考证类账号的主编。你擅长写出能让人停下来点击的标题。

{你的角色人设}
- 你不知道什么叫"官方语气"，你只会像学姐/学长一样说话
- 你的标题不需要面面俱到，只需要让目标人群觉得"这就是在说我"
- 每条标题都能独立成立，不需要上下文

---

## 当前选题

证书：{{②.cert_name}}
选题方向：{{①.topic}}
目标人群：{{①.audience}}

## 政策事实参考（确保标题中的时间/条件不写错）

{{②.brief_json}}

## 爆款样本参考（学习标题风格）

{% for sample in ②.viral_samples_json %}
- 标题：{{sample.title}}
  类型：{{sample.topic_type}}
{% endfor %}

---

## 任务：生成 5 个标题

每个标题用一种不同的钩子类型，不允许重复：

| # | 钩子类型 | 公式 | 示例思路 |
|---|---------|------|---------|
| 1 | 痛点型 | [痛点问句] + [解决方案承诺] | "XX学历能考吗？90%的人搞错了" |
| 2 | 干货型 | [数字钩子] + [内容预告] | "技能考试必过的10个操作细节" |
| 3 | 身份型 | [身份标签] + [成果] | "30岁宝妈在职备考，一次上岸" |
| 4 | 避坑型 | [反常识] + [纠正] | "别再被忽悠了！XX备考的3个误区" |
| 5 | 时间型 | [时间限制] + [紧迫感] + [方案] | "最后30天，这样复习还来得及" |

## 标题硬约束
- 每条 ≤ 25 字
- 必须包含具体数字或具体时间点（不能只写"必过""秘籍"）
- 不能脱离{{①.topic}}主题
- 参考爆款样本的语气，但不要抄袭

## 输出格式
返回纯 JSON 数组（不要 Markdown）：
["标题1", "标题2", "标题3", "标题4", "标题5"]
```

**User Prompt**：`根据选题"{{①.topic}}"为{{②.cert_name}}生成5个标题。`

---

### 节点 ④：正文生成（LLM）

**节点类型**：LLM

**模型**：GPT-4o / Claude 3.5 Sonnet

**System Prompt**：

```
你是小红书考证类账号的内容写手。你的正文读起来像一个真人在分享备考经历，不是一个AI在写总结。

{你的角色人设}
- 你是去年考过的过来人，文字里有真实的细节和感受
- 每条政策性结论都要有出处，不能编造数字
- 你写的东西让人想收藏，不是因为华丽，是因为有用

---

## 当前任务

证书：{{②.cert_name}}
选定标题：{{③.text}}（从5个标题中人工选定）
目标人群：{{①.audience}}

## 必须使用的事实数据（来自数据库，不要修改）

{{②.brief_json}}

## 风格参考（爆款样本）

{% for sample in ②.viral_samples_json %}
---
【参考案例】标题：{{sample.title}}
正文（节选）：{{sample.content[:300]}}...
{% endfor %}

---

## 正文结构（强制）

### 开头钩子（2-3句）
- 用一个真实的痛点或场景开头
- 不要说"大家好""今天给大家分享"
- 直接进入正题，像微信第一句话

### 主体干货（核心部分，400-600字）
- 按逻辑分 3-5 个小节，用 emoji 或短标题分隔
- 每个政策性结论后面标【依据：XX文件/X条】
- 数字和时间必须与上方"必须使用的事实数据"一致
- 多写"我当时""我去年"这种真实的细节

### 互动引导（1-2句）
- 自然收尾，像聊完天
- 可以问一个备考人真正会纠结的问题
- 禁止："关注我""点赞收藏""评论区滴滴""需要的扣1"

## 硬约束
- 总字数 400-800 字
- 涉及考试时间、报名条件、合格标准的地方，数字必须与数据库一致
- 不要编造数据库里没有的政策数字
- 像人写的，不像AI写的

## 输出格式
返回纯文本（不要 JSON），直接输出正文：
```

**User Prompt**：`标题是"{{③.text}}"，请为{{②.cert_name}}生成正文。`

---

### 节点 ⑤：封面+标签（LLM）

**节点类型**：LLM

**模型**：GPT-4o-mini（轻量任务）

**System Prompt**：

```
你是小红书封面和标签专家。

## 任务
为以下正文生成封面文案和话题标签。

正文：
{{④.text}}

## 封面文案要求
- 15-30 字
- 概括正文最核心的卖点
- 一句话让人想点进去

## 标签要求
- 5 个话题标签
- 覆盖：证书名、备考阶段、内容类型、目标人群
- 每个标签 2-6 字，不加 # 号

## 输出格式
返回 JSON：
{"cover_text": "封面文案", "tags": ["标签1", "标签2", "标签3", "标签4", "标签5"]}
```

---

### 节点 ⑥：事实校验（Code）

**节点类型**：Code

**代码**：复制 `docs/dify/v3/CODE_fact_check.py` 全部内容

**输入变量**：
| 变量 | 来源 |
|------|------|
| `body_text` | `{{④.text}}` |
| `policy_json` | `{{②.policy_json}}` |

**输出变量**：
| 变量 | 说明 |
|------|------|
| `fact_check_json` | 逐条校验结果 JSON |
| `warning_count` | 警告+失败数量（"0"表示全部通过） |
| `checked_count` | 校验总条数 |

---

### 节点 ⑦：打包返回（Code / End）

**节点类型**：Code 或直接 End

**代码**（如果用 Code 节点打包）：

```python
import json

def main(
    titles_json: str,
    selected_title: str,
    body_text: str,
    cover_text: str,
    tags_json: str,
    cert_name: str,
    cert_id: str,
    fact_check_json: str,
    warning_count: str,
):
    """打包所有产出为前端可用的 JSON。"""
    try:
        titles = json.loads(titles_json) if isinstance(titles_json, str) else titles_json
    except json.JSONDecodeError:
        titles = []
    try:
        tags = json.loads(tags_json) if isinstance(tags_json, str) else tags_json
    except json.JSONDecodeError:
        tags = []
    try:
        fact_check = json.loads(fact_check_json) if isinstance(fact_check_json, str) else fact_check_json
    except json.JSONDecodeError:
        fact_check = []

    result = {
        "cert_id": cert_id,
        "cert_name": cert_name,
        "titles": titles,
        "selected_title": selected_title,
        "body": body_text,
        "cover_text": cover_text,
        "tags": tags,
        "fact_check": fact_check,
        "has_warnings": int(warning_count) > 0 if warning_count else False,
    }

    return {"output_json": json.dumps(result, ensure_ascii=False)}
```

**输出变量**：`output_json` — 前端直接 `JSON.parse` 展示。

---

## 三、在 Dify 中搭建步骤

### Step 1：创建 Workflow

1. Dify 后台 → **工作室** → **创建** → **Workflow**
2. 名称：`小红书文章生产 V3`
3. 描述：7 节点流水线：选题→检索→标题→正文→封面→校验→打包

### Step 2：添加 Code 节点

1. 拖入 2 个 Code 节点（② 素材检索、⑥ 事实校验）
2. 每个节点分别粘贴对应 `.py` 文件全部内容
3. 配置输入/输出变量（见上方各节点配置表）

### Step 3：添加 LLM 节点

1. 拖入 3 个 LLM 节点（③标题、④正文、⑤封面标签）
2. 分别粘贴 System Prompt
3. 配置模型参数：
   - ③④：Temperature 0.8, Max Tokens 2000
   - ⑤：Temperature 0.6, Max Tokens 500

### Step 4：连线

按拓扑图依次连接 ①→②→③→④→⑤→⑥→⑦

### Step 5：测试

用以下输入测试：

```json
{
  "cert_id": "physician_licensed",
  "topic": "技能考试最后一个月备考攻略",
  "audience": "在职备考",
  "tone": "干货型"
}
```

### Step 6：前端对接

Taro 前端 `src/pages/workbench/components/ExamArticle/` 下：
- 接收 `output_json`
- 展示 5 个标题供单选
- 展示正文供编辑
- 展示事实校验结果（warning 项标黄，fail 项标红）
- 展示封面+标签供微调

---

## 四、后续迭代

| 优先级 | 任务 | 说明 |
|--------|------|------|
| P0 | 在 Dify 中实际搭建并跑通 | 本周末 |
| P0 | 前端适配 output_json | `ExamArticle` 组件改造 |
| P1 | 接入 Weaviate 教材知识库 | 上传教材 chunk → study_material 模式启用 |
| P1 | 事实校验升级为 LLM 逐句核对 | 当前是正则匹配，覆盖面有限 |
| P2 | 多平台改写 | 节点④后加「改写」节点：小红书→公众号/抖音 |
| P2 | 数据回流 | 前端「数据回填」入口 → 自动反哺 viral_post |
