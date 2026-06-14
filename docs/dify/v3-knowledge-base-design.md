# V3 — 知识库集成设计方案

> 撰于 2026-06-13 · 修订 2026-06-14 · 基于 V2 架构，新增知识库检索环节
>
> 目标：LLM 生成 study_material / subjects / priority / mnemonics 等内容时，从知识库检索权威资料作为参考，确保内容准确可控、有据可查，杜绝 LLM 编造考点。
>
> **2026-06-14 修订摘要**：切分策略从手动 chunk 改为脚本自动（按 `##` 标题）；检索策略从关键词向量检索改为章节名随机分配；新增「表达风格」融合到 CODE_0；新增引用原文不修改规则；新增 AI 味去除约束。详见各节 `⚠️ 2026-06-14 修订` 标记。

---

## 一、目标与范围

### 1.1 核心目标

| 目标 | 现状 | 期望 |
|------|------|------|
| 内容准确性 | LLM 凭训练记忆生成考点，可能编造不存在的"高频考点" | 基于权威资料库检索结果生成，每条考点可追溯到 source chunk |
| 内容可控性 | study_material 两张卡片可能覆盖同一器官系统（如 Demo 中两张都写妇产+儿科+消化） | 检索时就限定话题域，不同卡片检索不同知识域 |
| 可追溯性 | source 字段写死 `knowledge_base` / `llm_search`，无实际溯源 | source 引用具体 chunk_id + 文档名，可回溯验证 |
| 可扩展性 | 新增考试类型需重新写死 STUDY_TOPIC_DOMAINS | 知识库上传新考试文档即可，检索自动匹配 |

### 1.2 受益卡片类型

| 卡片类型 | KB 需求强度 | 说明 |
|----------|-----------|------|
| **study_material** | ★★★ 必须 | 核心考点、记忆方法需要从权威资料提取 |
| **subjects** | ★★☆ 建议 | 科目分值分布、备考策略需要考试大纲支撑 |
| **priority** | ★★☆ 建议 | 分值权重需要真题统计数据 |
| **mnemonics** | ★☆☆ 可选 | 口诀本身靠 LLM 创意，但口诀映射的知识点需验证 |
| **plan** | ★☆☆ 可选 | 复习顺序建议可参考知识库 |
| cover / notice / cta / resources | — 不需要 | 这些卡片不涉及专业知识 |

### 1.3 非目标（V3 不做）

- 不做实时联网搜索（用静态知识库，内容由运营上传审核）
- 不做用户个性化知识库（一个考试类型一个知识库）
- 不替代 LLM 的文案能力（KB 提供事实，LLM 负责表达）

---

## 二、Workflow 拓扑变更

### 2.1 V2（当前）

```
START
  → CODE_0 (LLM: 叙事规划)
  → CODE_1 (参数计算)
  → Iterator(
      CODE_A (构造 prompt)
      → LLM (生成卡片)
    )
  → CODE_2 (后处理)
  → END
```

### 2.2 V3（知识库集成）

```
START
  → CODE_0 (LLM: 叙事规划)
  → CODE_1 (参数计算 + 知识库章节分配)
  → Iterator(
      CODE_A (构造 prompt + 输出 kb_query)
      → Knowledge_Retrieval (Dify 原生节点: 向量检索)
      → LLM (生成卡片，prompt 中注入 kb_context)
    )
  → CODE_2 (后处理 + source 补全)
  → END
```

### 2.3 关键变更

| 变更点 | 说明 |
|--------|------|
| CODE_1 新增输出 | `kb_query` + `assigned_chapter` — 随机分配章节给 study_material |
| CODE_A 新增输出 | `kb_query` — 当前卡片的知识库查询语句（透传自 CODE_1） |
| **新增节点** | **Knowledge_Retrieval** — Dify 原生知识库检索节点 |
| LLM prompt 变更 | user_prompt 尾部追加 kb_context（检索到的知识块, LLM 模板中遍历数组） |
| CODE_2 新增逻辑 | source 字段补全, 默认 `knowledge_base` |

---

## 三、知识库设计

### 3.1 文档组织结构

以执业医师资格证为例：

```
知识库: 执业医师资格证-考点库/
├── 01-考试大纲/
│   ├── 临床执业医师考试大纲-2026.md
│   └── 各科目分值分布统计.md
├── 02-分科考点/
│   ├── 呼吸系统-核心考点.md
│   ├── 循环系统-核心考点.md
│   ├── 消化系统-核心考点.md
│   ├── 泌尿系统-核心考点.md
│   ├── 妇产科-核心考点.md
│   ├── 儿科-核心考点.md
│   ├── 神经精神系统-核心考点.md
│   ├── 运动系统-核心考点.md
│   ├── 内分泌系统-核心考点.md
│   ├── 血液系统-核心考点.md
│   ├── 传染病-核心考点.md
│   ├── 药理学-核心考点.md
│   ├── 病理学-核心考点.md
│   └── 生理学-核心考点.md
├── 03-历年真题分析/
│   ├── 2024-2025-真题考点频次统计.md
│   └── 高频考点TOP100.md
└── 04-记忆方法/
    └── 各科记忆口诀汇总.md
```

### 3.2 Chunk 策略（核心） ⚠️ 2026-06-14 修订

> **变更说明**：V3 原设计为手动 `chunk:start/end` 标记 + 人工 metadata 标注，但因知识库文档超过 3400 个知识点，人工切分不可行。改为**脚本自动按 `##` 标题切分 + 独立文件上传**，文件名承载章节层级作为隐式 metadata。

#### 3.2.1 分块原则

| 决策 | 选型 | 理由 |
|------|------|------|
| **切分边界** | `## ` 二级标题（即一个知识点/一节） | 每个 `##` 对应一个独立的知识点单元，语义完整不跨话题 |
| **每片大小** | 不设硬上限，以 `##` 为自然边界 | 原文一个知识点多长就是多长，不人为截断 |
| **上传格式** | 每个知识点一个独立 `.txt` 文件 | 文件名带章节路径，Dify 上传后文件名可作为 metadata 检索 |
| **分段模式** | Dify 通用分段（非父子分段） | 每个文件已是一个知识点，无需 Dify 再做语义切分 |
| **Top-K** | 5 | 检索 5 个最相关 chunk |
| **相似度阈值** | 先不设阈值（开放测试后根据效果调整） | 保证召回率优先 |

#### 3.2.2 脚本切分流程

输入：按章节组织的 Markdown 文档（如 `呼吸系统-核心考点.md`）
输出：独立 `.txt` 文件，一个知识点一个文件

```
输入: 呼吸系统-核心考点.md
  ├── ## COPD（慢性阻塞性肺疾病）
  │   ├── ### 病因
  │   ├── ### 诊断标准
  │   └── ### 治疗
  ├── ## 支气管哮喘
  │   └── ...
  
        ↓ 脚本按 ## 切分 ↓

输出: upload/
  ├── 呼吸系统__COPD.txt              # 包含 COPD 下所有 ### 子节
  ├── 呼吸系统__支气管哮喘.txt
  ├── 呼吸系统__肺炎.txt
  └── ...
```

**切分规则**：
1. 遇到 `## {知识点名}` → 开始一个新文件
2. 该 `##` 下所有内容（含 `###` 子标题）归入同一文件
3. 文件名格式：`{章名}__{知识点名}.txt`（双下划线分隔层级）
4. 文件名同时生成章节清单 JSON（供 CODE_1 做随机章节分配）

#### 3.2.3 文件名即 Metadata

不手写 JSON metadata。用文件名承载章节层级，Dify 上传后文件名参与检索匹配：

```
文件名: 呼吸系统__COPD.txt
         ↑       ↑
      章节名   知识点名

文件名: 循环系统__心力衰竭__慢性心衰.txt
         ↑       ↑           ↑
      章节名   知识点名    子知识点（可选）
```

脚本同时生成一个 `chapter_index.json`，记录完整的章节名列表：

```json
{
  "exam": "执业医师资格证",
  "chapters": [
    {
      "name": "呼吸系统",
      "file": "呼吸系统",
      "topics": ["COPD", "支气管哮喘", "肺炎", "肺结核", "呼吸衰竭"]
    },
    {
      "name": "循环系统",
      "file": "循环系统",
      "topics": ["心力衰竭", "心律失常", "冠心病", "高血压", "心脏瓣膜病"]
    }
  ]
}
```

`chapter_index.json` 供 CODE_1 使用——随机不重复抽取章节分配给各 `study_material` 卡片（详见 4.1）。

#### 3.2.4 脚本存放规范

```
docs/dify/scripts/
├── README.md                    # 脚本使用说明
├── chunk_by_heading.py          # 按 ## 切分 Markdown → txt
├── chunk_by_heading_extract_index.py  # 同上 + 生成 chapter_index.json
├── merge_index.py               # 合并多个考试的 chapter_index.json
└── validate_chunks.py           # 校验：文件名规范、空文件、编码
```

### 3.3 索引与 Embedding

| 配置项 | 推荐值 | 说明 |
|--------|--------|------|
| Embedding 模型 | `text-embedding-3-small`（OpenAI）/ `bge-large-zh-v1.5`（本地） | 中文医学文本检索效果好 |
| 向量数据库 | Dify 内置（Weaviate / Qdrant） | 本地部署用小规模即可 |
| Top-K | 5 | 检索 5 个最相关 chunk |
| 相似度阈值 | 0.65 | 低于此分数的 chunk 丢弃 |
| Rerank | 可选（Cohere Rerank / bge-reranker） | 提升精度，但不必须 |

---

## 四、检索策略设计 ⚠️ 2026-06-14 修订

> **变更说明**：V3 原设计为关键词构造 kb_query → 向量检索匹配。但因 V1 版不含知识点关键词，改为**CODE_1 随机分配章节 → Knowledge Retrieval 用章节名检索对应文件**。本质是把「语义检索」降级为「文件名匹配 + 指定章节注入」。

### 4.1 核心策略：章节随机不重复分配（CODE_1 预计算）

CODE_1 从 `chapter_index.json` 中读取章节列表，为每张 `study_material` 卡片随机分配一个不重复的章节。`kb_query` 直接用章节名，精确匹配该章节下的所有知识点文件。

```python
# CODE_1 中：章节随机不重复分配

import random

def assign_chapters_to_cards(enriched_cards, chapter_index, exam_name):
    """
    为所有 study_material 卡片随机分配不重复的章节。
    chapter_index: {"chapters": [{"name": "呼吸系统", "file": "呼吸系统", "topics": [...]}, ...]}
    返回: 更新后的 enriched_cards（每张 study_material 多了 kb_query 和 assigned_chapter）
    """
    chapters = chapter_index["chapters"]
    random.shuffle(chapters)  # 随机打乱
    chapter_pool = list(chapters)
    
    for i, card in enumerate(enriched_cards):
        if card.get("type") != "study_material":
            card["kb_query"] = ""  # 非 study_material 不检索
            continue
        
        if chapter_pool:
            chapter = chapter_pool.pop(0)  # 取一个不重复的章节
        else:
            chapter = random.choice(chapters)  # 章节不够时允许重复
        
        card["assigned_chapter"] = chapter["name"]
        # kb_query = 章节文件名前缀，检索时精确命中该章节所有知识点
        card["kb_query"] = f"{exam_name}__{chapter['file']}"
    
    return enriched_cards
```

**分配示例**（2 张 study_material 卡片）：

```
chapter_index 共 14 个章节
  → 随机打乱：[循环系统, 妇产科, 呼吸系统, 消化系统, ...]
  → 卡片1: 分配「循环系统」→ kb_query = "执业医师资格证__循环系统"
  → 卡片2: 分配「妇产科」  → kb_query = "执业医师资格证__妇产科"
  
结果：两张 study_material 覆盖不同系统，内容不重叠。
```

### 4.2 各卡片类型的检索策略

| 卡片类型 | kb_query 来源 | 检索机制 |
|----------|-------------|----------|
| **study_material** | CODE_1 随机分配章节名 → `"{考试名}__{章节名}"` | 文件名精确匹配该章节的所有 chunk |
| **subjects** | 固定查询 `"{考试名} 考试大纲 科目分值"` | 向量检索匹配大纲/分值文件 |
| **priority** | 固定查询 `"{考试名} 分值占比 高频考点"` | 向量检索匹配统计文件 |
| **mnemonics** | 固定查询 `"{考试名} 记忆口诀"` | 向量检索匹配口诀文件 |
| **plan** | 固定查询 `"{考试名} 复习顺序 阶段规划"` | 向量检索匹配复习建议 |
| cover / notice / cta / resources | 空字符串 | 跳过检索，纯 LLM 生成 |

### 4.3 检索流程（简化版）

```
CODE_1 分配章节 → CODE_A 透传 kb_query
                          ↓
Knowledge_Retrieval 节点:
  1. 用 kb_query（章节名）在知识库中检索
  2. 返回 Top-K=5 个匹配文件的内容
  3. 拼接为 kb_context（保留文件名作为来源标记）
                          ↓
输出 kb_context → LLM 节点生成卡片
```

### 4.4 kb_context 输出格式

检索结果注入 prompt 时的格式（示例——「循环系统」章节检索到的 5 个知识点文件）：

```
📚 [来源: 循环系统__心力衰竭.txt]
{原文全部内容}
---
📚 [来源: 循环系统__心律失常.txt]
{原文全部内容}
---
📚 [来源: 循环系统__冠心病.txt]
{原文全部内容}
---
📚 [来源: 循环系统__高血压.txt]
{原文全部内容}
---
📚 [来源: 循环系统__心脏瓣膜病.txt]
{原文全部内容}
```

**关键约束**：LLM 引用教材原文（key_points 中的数值、定义、诊断标准）时**不得修改原文表述**，防止歧义。发散性内容（memory_tips、模块衔接语、标题润色）可以自由发挥，但必须围绕原文知识点展开。

---

## 五、节点级改动设计

### 5.1 CODE_1 改动 ⚠️ 2026-06-14 修订

#### 新增函数入参

```python
def main(
    # ... 现有参数 ...
    chapter_index: str = "",  # ★ 新增：chapter_index.json 内容（JSON 字符串）
):
```

#### 新增章节随机分配逻辑

```python
import json
import random

def load_chapter_index(chapter_index_str: str) -> dict:
    """解析 chapter_index.json 字符串"""
    if not chapter_index_str:
        return {"chapters": []}
    return json.loads(chapter_index_str)

def assign_chapters_to_cards(enriched_cards, chapter_index_str, exam_name):
    """
    为 study_material 卡片随机分配不重复章节。
    返回更新后的 enriched_cards。
    """
    index = load_chapter_index(chapter_index_str)
    chapters = index.get("chapters", [])
    random.shuffle(chapters)
    pool = list(chapters)
    
    for card in enriched_cards:
        if card.get("type") != "study_material":
            card["kb_query"] = ""
            continue
        
        if pool:
            ch = pool.pop(0)
        else:
            ch = random.choice(chapters) if chapters else {"name": "", "file": ""}
        
        card["assigned_chapter"] = ch["name"]
        card["kb_query"] = f"{exam_name}__{ch.get('file', ch['name'])}"
    
    return enriched_cards
```

### 5.2 CODE_A 改动 ⚠️ 2026-06-14 修订

#### 新增输出变量

```python
return {
    "system_prompt": system_prompt,
    "user_prompt": user_prompt,
    "kb_query": current_card.get("kb_query", ""),  # ★ 透传给知识库检索节点
    "card_index": str(current_card.get("index", 0)),
    "card_type": card_type,
}
```

#### LLM 节点 User Prompt 模板（含引用规则 + 主编基调）

```
{{CODE_A.user_prompt}}

{% if Knowledge_Retrieval.result and Knowledge_Retrieval.result != "" %}
---
📚 **以下内容来自权威备考教材，请严格遵循以下规则生成卡片：**

{{Knowledge_Retrieval.result}}

⚠️ **引用规则（必须遵守）：**
1. key_points 中涉及的具体数值（诊断阈值、正常值范围、分级标准）、定义、诊断标准——**必须原文照搬，不得改写、不得调整语序、不得替换同义词**。教材怎么说就怎么引用，修改可能引入歧义。长段落无法照搬时，提取关键数值和定义原样保留，解释性文字由你压缩拼装。
2. 每个 key_point 必须能在上述资料中找到原始出处。
3. 如果资料中的某个知识点你在卡片中没有用到，跳过即可，不要强行塞入。
4. memory_tips 可以自由创作（谐音、联想、场景记忆），但所记忆的「知识点」必须来自资料原文。

📐 **优先级（冲突时遵守）：**
5. key_points：**原文准确性 > 口语化**。宁可句式学术，也不能改变数值/定义/诊断标准。
6. memory_tips / module_title / 模块衔接语：**口语化 > 学术精确**。这里就是用来把原文「翻译成人话」的。
7. 简而言之：考点内核严守原文，包装外壳自由发挥。

✍️ **写作风格（由主编 CODE_0 设定基调）：**
6. 整体语气遵循 CODE_0 制定的「整体基调」和「表达风格」。
7. 减少 AI 味——像真人发微信而不是写总结：
   - 句子长短交错，避免每句工整排比（像 PPT 大纲是 AI 味的典型症状）
   - 用「你」直接对话，不用「考生」「备考者」等第三人称
   - 用口语词：「别指望」「刷到吐」「看到题干就秒」「卡住就跳过」，不要「建议」「应当」「值得注意的是」
   - 像学姐/教练在给你发消息，不是在写教材
8. 发散内容（模块衔接语、标题润色、补充说明）必须围绕原文知识点展开，不得离题。
{% else %}
---
⚠️ 本次生成未检索到相关知识库资料，请基于你的训练知识生成内容，并在 source 字段标记为 "llm_search"。对于不确定的考点数据（如分值、统计数字），优先使用模糊表述而非编造具体数字。
{% endif %}
```

### 5.3 Knowledge Retrieval 节点配置（Dify 后台操作） ⚠️ 2026-06-14 修订

| 配置项 | 值 | 说明 |
|--------|---|------|
| 节点类型 | **知识检索** (Knowledge Retrieval) | Dify 原生节点 |
| 知识库 | `{考试名}-考点库` | 每个考试类型一个独立知识库 |
| 输入变量 | `{{CODE_A.kb_query}}` | 来自 CODE_A（study_material 为章节名，其他卡片为固定短语） |
| 检索模式 | **向量检索** | 本版不含关键词，纯语义匹配 |
| Top-K | 5 | 检索 5 个最相关 chunk |
| Score 阈值 | 不设（开放） | 初期保证召回率，后续根据效果收紧 |
| 输出变量 | `result` (text) | 拼接后的检索结果文本 |
| 分段模式 | 通用分段 | 每个文件已是独立知识点，Dify 做通用分段即可 |

**重要：Iterator 内使用注意事项**

- Dify 的 Knowledge Retrieval 节点放在 Iterator 的子流程中时，每次迭代独立执行检索
- 如果 kb_query 为空字符串，检索节点返回空结果（不报错）
- 检索结果只在当前迭代内可用，不会跨迭代累积
- study_material 的 kb_query 已绑定具体章节名，两张 study_material 卡片会检索到不同章节的内容

### 5.4 CODE_2 改动

#### 新增：source 字段溯源

```python
def extract_source_from_kb_context(kb_context: str) -> list[dict]:
    """
    从 kb_context 文本中提取 source 信息。
    输入格式: "📚 [来源: 文档名#章节]\n内容..."
    输出: [{"doc": "呼吸系统-核心考点.md", "section": "COPD-诊断", "chunk_index": 0}, ...]
    """
    sources = []
    pattern = r'📚\s*\[来源:\s*([^\]]+)\]'
    for match in re.finditer(pattern, kb_context):
        source_str = match.group(1)
        if "#" in source_str:
            doc, section = source_str.split("#", 1)
        else:
            doc, section = source_str, ""
        sources.append({"doc": doc.strip(), "section": section.strip()})
    return sources
```

在 study_material 的每个 module 中注入 source：

```python
# CODE_2 后处理中
if card.get("type") == "study_material":
    kb_sources = extract_source_from_kb_context(
        original_card.get("kb_context", "")
    )
    for i, module in enumerate(card.get("study_material", [])):
        if i < len(kb_sources):
            module["source"] = {
                "type": "knowledge_base",
                "doc": kb_sources[i]["doc"],
                "section": kb_sources[i]["section"],
            }
        else:
            module["source"] = {"type": "llm_search"}
```

---

## 六、知识库准备与运维 ⚠️ 2026-06-14 修订

### 6.1 文档编写规范

源文档使用 Markdown 格式，结构遵循教材自然层级：

```markdown
# {系统/学科名}（一级标题 = 章，一个文件一个章）

## {知识点名}（二级标题 = 切分边界，脚本自动在此处切分）

### {子主题}（三级标题 = 归入所属 ## 的同一文件，不单独切）

{正文内容，自然段落，不要求特殊标注}
```

**无需手写 metadata、chunk 标记或 exam_freq**。脚本自动提取标题层级作为文件名。

### 6.2 上传与索引流程

```
1. 将教材内容按 # 章 / ## 知识点 结构编写为 Markdown
2. 运行 chunk_by_heading_extract_index.py：
   - 输入：knowledge_base/{考试名}/ 下的 .md 文件
   - 输出：upload/*.txt（独立知识点文件）+ chapter_index.json
3. 在 Dify 后台创建知识库 → 批量上传 upload/ 目录下的 .txt 文件
4. 等待 Dify 向量化索引完成（通常几分钟）
5. 将 chapter_index.json 内容配置到 CODE_1 的入参
6. 测试检索：
   - 测试查询："执业医师资格证__呼吸系统"
   - 验证返回的 5 个 chunk 均为呼吸系统相关知识点
7. 将知识库绑定到 Workflow 的 Knowledge Retrieval 节点
```

| 场景 | 操作 | 影响 |
|------|------|------|
| 新增考试类型 | 按模板编写新考试的文档 → 上传到同一知识库（用 exam_name metadata 区分） | 无影响 |
| 修正某个考点 | 在 Dify 后台找到对应文档 → 编辑 → 重新索引 | 仅该文档的 chunk 重新向量化 |
| 大纲变更（如 2027 新大纲） | 新建 `v2027/` 目录 → 上传新版文档 → 旧版文档下线（取消索引） | 需确保查询中包含考试年份限定词 |
| 批量导入 | 用 Dify API 批量上传文档 | 首次导入可能需要 10-30 分钟索引 |

---

## 七、边界情况与降级策略

### 7.1 检索结果为空

| 原因 | 降级策略 |
|------|----------|
| kb_query 为空（非 KB 类型卡片） | 正常，LLM 走原有生成逻辑 |
| 知识库未包含该查询的考点 | LLM prompt 中的 fallback 分支：标记 `source: llm_search`，提醒 LLM 不确定时用模糊表述 |
| 相似度低于阈值（所有 chunk < 0.65） | 同上，归为 LLM 自主生成 |

### 7.2 检索结果不相关

| 原因 | 降级策略 |
|------|----------|
| 查询语句与 chunk 语义不匹配 | LLM prompt 中指示："如果以下资料与当前卡片不相关，忽略资料，按你的知识生成" |
| 向量模型对中文医学术语不敏感 | 启用混合检索（关键词 BM25 + 向量），关键词匹配保底 |

### 7.3 知识库不可用

| 原因 | 降级策略 |
|------|----------|
| 向量数据库挂了 | Dify Knowledge Retrieval 节点抛出异常 → Workflow 配置错误处理分支，跳过检索直接走 LLM |
| Embedding API 超时 | Dify 内置重试机制（3 次），仍失败则跳过检索 |

### 7.4 多张 study_material 卡片内容重叠

| 场景 | 策略 |
|------|------|
| 两张 study_material | CODE_1 随机分配不重复章节 → kb_query 不同 → 检索到不同教材内容 |
| 三张及以上 study_material | 优先不重复分配；章节数不够时（如 3 张卡片但只有 2 个章）才允许重复，此时重复的章节会检索到相同文件 |
| 极端情况（章节数 < 卡片数） | CODE_1 轮询复用章节，不报错

---

## 八、与 V2 的兼容性

### 8.1 渐进式部署

```
Phase 1（本周）: 仅对 study_material 卡片启用知识库检索
                → 其他卡片 kb_query 留空，走原有逻辑
                → 观察效果 + 调试检索质量

Phase 2（下周）: 扩展到 subjects + priority + mnemonics
                → 验证多类型卡片的检索效果

Phase 3（稳定后）: 可选扩展到 plan 卡片
```

### 8.2 回滚

- Dify 后台断开 Knowledge Retrieval 节点的连线 → 退回纯 V2 模式
- CODE_1/CODE_A/CODE_2 的 V3 代码向下兼容：如果 kb_query 为空，行为与 V2 完全一致
- 不需要修改前端代码

---

## 九、评估指标 ⚠️ 2026-06-14 修订

### 9.1 检索有效性（章节分配模型）

| 指标 | 目标值 | 测量方法 |
|------|--------|----------|
| 章节匹配率 | > 90% | kb_query 用章节名检索时，Top-5 中属于该章节的比例 |
| 跨章污染率 | < 10% | Top-5 结果中不属于所分配章节的比例（纯向量检索的副作用） |
| 检索为空率 | < 5% | 给定有效章节名，知识库检索返回 0 结果的概率 |

### 9.2 内容质量

| 指标 | 目标值 | 测量方法 |
|------|--------|----------|
| 原文引用准确率 | > 95% | key_points 中的具体数值、定义与教材原文一致的比例 |
| 编造率 | < 5% | 生成了教材中不存在且无法验证的"考点"的比例 |
| 章节内容覆盖率 | > 60% | 检索注入的教材章节中，实际被考点覆盖的知识点数占比 |
| 卡片去重率 | 100% | 两张 study_material 卡片覆盖不同章节的比例 |

### 9.3 性能

| 指标 | 目标值 | 说明 |
|------|--------|------|
| 检索延迟 | < 500ms | 单次向量检索 + 拼接时间 |
| 端到端延迟增加 | < 2s | 相比 V2，多了 Knowledge Retrieval 节点 |
| kb_context 大小 | < 8000 字符 | Top-5 个知识点的原文总量上限 |
| 知识库存储 | < 50MB 每考试 | 每个考试类型约 50-200 个 Markdown 文件 |

---

## 十、本地部署注意事项

### 10.1 先决条件

当前 Dify 为本地 Docker 部署。知识库功能需要：

1. **Embedding 模型**：Dify 默认使用 OpenAI embedding，需要配置 API key。或者在 Dify 后台配置本地 embedding 模型（如 `bge-large-zh-v1.5` 通过 Ollama / Xinference）。
2. **向量数据库**：Dify 内置 Weaviate（Docker compose 自带），无需额外部署。

### 10.2 本地测试脚本

```python
# tools/test_kb_retrieval.py
# 用于在部署前验证知识库检索质量

import requests

DIFY_API_URL = "http://localhost/v1"
DIFY_API_KEY = "app-SLc5nNMlGTuR8XJrEY48ssY1"

TEST_QUERIES = [
    ("执业医师资格证 呼吸系统 COPD 诊断标准", "期望检索到 COPD 诊断标准 chunk"),
    ("执业医师资格证 妇产科 前置胎盘 诊断", "期望检索到前置胎盘 chunk"),
    ("执业医师资格证 消化系统 肝硬化 并发症", "期望检索到肝硬化失代偿 chunk"),
    ("执业医师资格证 儿科 小儿腹泻 补液", "期望检索到补液方案 chunk"),
    ("执业医师资格证 药理学 抗生素 分类", "期望检索到抗生素分类 chunk"),
]

def test_kb_retrieval(kb_name: str):
    for query, expected in TEST_QUERIES:
        # 调用 Dify 知识库检索 API
        resp = requests.post(
            f"{DIFY_API_URL}/datasets/{kb_name}/retrieve",
            headers={"Authorization": f"Bearer {DIFY_API_KEY}"},
            json={"query": query, "top_k": 5},
        )
        results = resp.json()
        print(f"Query: {query}")
        print(f"Top-1: {results[0]['content'][:100]}...")
        print(f"Expected: {expected}")
        print("---")
```

### 10.3 文档预处理脚本（chunk_by_heading.py）

```python
# docs/dify/scripts/chunk_by_heading_extract_index.py
# 按 ## 标题切分 Markdown → 独立 .txt 文件 + 生成 chapter_index.json

import re
import os
import json
from pathlib import Path

def chunk_by_heading(md_path: str, output_dir: str) -> list[dict]:
    """
    按 ## 二级标题切分 Markdown 文档。
    # 一级标题 = 章/系统名
    ## 二级标题 = 知识点（切分边界）
    ### 三级标题 = 子节（归入所属 ## 的同一文件）
    """
    with open(md_path, "r", encoding="utf-8") as f:
        content = f.read()
    
    # 提取一级标题（章名）
    chapter_match = re.search(r'^#\s+(.+)$', content, re.MULTILINE)
    chapter_name = chapter_match.group(1).strip() if chapter_match else Path(md_path).stem
    
    # 按 ## 切分
    sections = re.split(r'\n(?=##\s+)', content)
    
    chunks = []
    topics = []
    
    for section in sections:
        # 提取 ## 标题
        heading_match = re.search(r'^##\s+(.+)$', section, re.MULTILINE)
        if not heading_match:
            continue
        
        topic_name = heading_match.group(1).strip()
        # 清理文件名非法字符
        safe_topic = re.sub(r'[\\/:*?"<>|]', '-', topic_name)
        safe_chapter = re.sub(r'[\\/:*?"<>|]', '-', chapter_name)
        
        filename = f"{safe_chapter}__{safe_topic}.txt"
        filepath = os.path.join(output_dir, filename)
        
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(section.strip())
        
        topics.append(safe_topic)
        chunks.append({
            "file": filename,
            "chapter": chapter_name,
            "topic": topic_name
        })
    
    return {"chapter": chapter_name, "file": chapter_name, "topics": topics, "chunks": chunks}

def process_all(source_dir: str, output_dir: str, index_path: str):
    """
    批量处理知识库源文件目录。
    生成：upload/*.txt（上传文件）+ chapter_index.json（章节索引）
    """
    os.makedirs(output_dir, exist_ok=True)
    
    index = {"exam": os.path.basename(source_dir), "chapters": []}
    
    for md_file in Path(source_dir).glob("*.md"):
        result = chunk_by_heading(str(md_file), output_dir)
        index["chapters"].append({
            "name": result["chapter"],
            "file": result["file"],
            "topics": result["topics"]
        })
        print(f"  {md_file.name} → {len(result['chunks'])} 个知识点文件")
    
    with open(index_path, "w", encoding="utf-8") as f:
        json.dump(index, f, ensure_ascii=False, indent=2)
    
    print(f"\n总计 {sum(len(c['topics']) for c in index['chapters'])} 个知识点")
    print(f"章节索引 → {index_path}")

if __name__ == "__main__":
    process_all(
        source_dir="./knowledge_base/执业医师",
        output_dir="./knowledge_base/upload",
        index_path="./knowledge_base/chapter_index.json"
    )
```

---

## 十一、实施路线图

| 阶段 | 任务 | 负责人 | 预计耗时 |
|------|------|--------|----------|
| **Day 1** | 编写知识库文档（至少覆盖呼吸+循环+消化 3 个系统） | 内容运营 | 4h |
| **Day 1** | 本地 Dify 配置 Embedding 模型 + 创建知识库 | 开发 | 1h |
| **Day 2** | 上传文档 + 检查索引质量 + 调优 chunk 参数 | 开发 | 2h |
| **Day 2** | 修改 CODE_1：新增 kb_queries 构造逻辑 | 开发 | 1h |
| **Day 2** | 修改 CODE_A：新增 kb_query 输出 | 开发 | 0.5h |
| **Day 2** | 配置 Knowledge Retrieval 节点 + LLM prompt 模板 | 开发 | 1h |
| **Day 3** | 修改 CODE_2：source 溯源逻辑 | 开发 | 1h |
| **Day 3** | 端到端测试（用 v1.1-dify-test-cases.json 中的 TC-01~TC-06） | 开发 | 2h |
| **Day 3** | 人工审核生成结果：考点准确性、数字正确性、source 可追溯 | 开发 + 运营 | 2h |
| **Day 4** | 修复集成测试发现的问题 | 开发 | 2h |
| **Day 5** | Phase 1 上线（仅 study_material 启用 KB） | 开发 | 1h |

---

## 十二、风险与待讨论项

| 风险 | 概率 | 影响 | 缓解措施 |
|------|------|------|----------|
| Dify 本地版 Knowledge Retrieval 功能受限（不支持混合检索/Rerank） | 中 | 中 | 降级为纯向量检索；或等 Dify 版本更新 |
| 知识库文档编写质量低，chunk 内容不完整 | 高 | 高 | 提供文档模板 + 示例 + 审核流程 |
| Embedding 模型对中文医学术语理解差 | 中 | 高 | 优先选 `bge-large-zh-v1.5`（中文优化）；测试阶段用人工评估 |
| 检索延迟导致端到端体验变差 | 低 | 中 | 设置超时 + fallback；混合检索时关键词匹配保底 |
| Iterator 内检索的 Token 消耗增加 | 中 | 低 | 仅对 4 种卡片类型开启检索（plan/mnemonics 可选关闭） |

### 待讨论

1. **知识库内容谁写？** 内容运营 vs 开发？建议运营写初稿，开发验证格式。
2. **是否需要多知识库？** 一个考试一个知识库 vs 所有考试共用一个知识库？建议一个考试一个知识库（元数据隔离清晰）。
3. **是否需要人工审核生成结果？** 建议 Phase 1 阶段人工审核 100% 的 study_material 卡片，稳定后抽检 20%。
4. **本地 Embedding 模型选型？** 需要确认 Dify 本地部署环境是否支持 Ollama/Xinference，或直接用 OpenAI API。

---

## 附录 A：Dify Knowledge Retrieval 节点配置截图指南

1. 打开 Workflow 编辑页
2. 在 Iterator 内部，CODE_A 节点后面，点击 `+` 添加节点
3. 选择「知识检索」节点类型
4. 配置面板：
   - 知识库：选择已创建的知识库
   - 查询变量：选择 `{{CODE_A.kb_query}}`
   - 检索模式：混合检索
   - Top-K：5
   - Score 阈值：0.65
   - 输出变量名：`result`
5. 连接：CODE_A → Knowledge_Retrieval → LLM
6. 在 LLM 节点的 User Prompt 中引用 `{{Knowledge_Retrieval.result}}`

## 附录 B：典型 chunk 示例（完整）

```
[Chunk 示例 — 呼吸系统·COPD·诊断标准]

📚 [来源: 呼吸系统-核心考点.md#COPD-诊断标准]

COPD 诊断金标准：吸入支气管舒张剂后 FEV1/FVC < 0.70。

严重程度分级（基于 FEV1%pred）：
- GOLD 1（轻度）：FEV1 ≥ 80% 预计值
- GOLD 2（中度）：50% ≤ FEV1 < 80% 预计值
- GOLD 3（重度）：30% ≤ FEV1 < 50% 预计值
- GOLD 4（极重度）：FEV1 < 30% 预计值

出题方向：
1. 病例题给吸烟史（>20 包年）+ 慢性咳嗽咳痰气短 + 肺功能 FEV1/FVC < 0.7 → 诊断 COPD
2. 选择题给 FEV1%pred 数值让你判断严重程度分级（最爱考 GOLD 2 vs 3 的临界值）
3. 每年 2-3 分，单选 + 病例串题都有可能

记忆方法：「0.7 是及格线，低于就扣 COPD 帽子；50 是中度线，30 是重度线」
```
