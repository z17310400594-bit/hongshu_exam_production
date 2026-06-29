# WP15 验收工具使用说明

WP15 当前交付的是“验收框架 MVP”，不是最终生产验收结论。它的作用是让后续的人或模型把真实旧 API 输出、V2 输出和人工答案填进 JSONL，然后一键得到双读差异分类、黄金集指标和安全门禁结果。

## 1. 黄金集 JSONL 格式

每行一个 case，参考：

```json
{"id":"ELIG-001","category":"eligibility","request":{"path":"/api/v2/eligibility/evaluate","body":{"certificateCode":"c_constructor_1"}},"oldResult":{"decision":"insufficient_data"},"v2Result":{"decision":"eligible","certificateCode":"c_constructor_1","citations":[{"assetCode":"POLICY_001"}]},"expected":{"decision":"eligible","certificateCode":"c_constructor_1","citationAssetCodes":["POLICY_001"],"requiresCitation":true,"forbiddenTerms":["restricted body"]}}
```

字段含义：

- `id`：稳定用例编号，建议按 `ELIG-001`、`SEARCH-001`、`GEN-001`、`SEC-001` 分类。
- `category`：`certificate` / `eligibility` / `exam_event` / `knowledge_search` / `generation` / `security`。
- `request`：原始请求，便于复跑和人工核对。
- `oldResult`：旧 API 结果或旧库查询结果。
- `v2Result`：V2 API 结果。
- `expected`：人工标注答案。
  - `decision`、`certificateCode`、`matchedRuleCode`、`eventCode` 等会进入结构化准确率。
  - `citationAssetCodes` / `requiresCitation` 会进入引用正确率和无证据事实检查。
  - `forbiddenTerms` 会检查 V2 输出中是否泄漏 restricted 明文、标题或内部摘要。
  - `ambiguous: true` 表示业务口径未决。
  - `dataStatus: "missing"` 表示数据缺失，不应被当成模型/代码错误。

样例文件：

```bash
docs/implementation/evaluation/wp15_golden_cases.sample.jsonl
```

## 2. 运行黄金集评测

```bash
python scripts/wp15_acceptance.py evaluate docs/implementation/evaluation/wp15_golden_cases.sample.jsonl
```

默认门槛：

| 指标 | 门槛 |
|---|---:|
| structuredAccuracy | ≥ 0.99 |
| citationAccuracy | ≥ 0.98 |
| restrictedLeakRate | = 0 |
| noEvidenceFacts | = 0 |

输出中的 `comparisons[].classification` 可能是：

- `match`：旧/V2 都符合人工答案；
- `old_wrong`：V2 符合人工答案，旧结果不符合；
- `new_wrong`：旧结果符合人工答案，V2 不符合；
- `business_ambiguous`：人工标注为业务歧义；
- `data_missing`：数据缺失或 V2 明确返回 insufficient_data；
- `security_leak`：命中 forbiddenTerms；
- `needs_review`：无法自动归类，需要人工复核。

## 3. 运行安全扫描

```bash
python scripts/wp15_acceptance.py secret-scan api db src scripts .env.example .env.development .env.production .env.test
```

扫描目标：

- OpenAI/Dify 形态的 API key；
- 长 Bearer token；
- `password=` / `secret=` / `api_key=` 这类明显赋值。

注意：历史设计文档里可能有“变量名/风险说明”文字，本命令默认扫描代码、脚本和 env 模板，不扫描所有历史文档，避免把旧风险登记误判成真实泄漏。

## 4. 后续补齐真实 100 条的方法

1. 从真实运营/销售/教辅场景里抽样 100 条问题；
2. 每条保存旧 API 输出、V2 输出和人工答案；
3. restricted 安全用例必须填写 `forbiddenTerms`，至少覆盖标题、正文片段、内部集合名；
4. 每次调整数据或服务后复跑 `evaluate`；
5. 所有 `new_wrong`、`security_leak` 必须修复；`business_ambiguous` 必须由业务负责人定口径；`data_missing` 必须进入数据补录清单。

## 5. 生产量级 migration/query 性能测试入口

本包没有执行真实生产量级压测。进入正式生产验收时，建议另建报告并记录：

- 空库 `alembic upgrade head` 耗时；
- 从备份/CSV 导入耗时和失败行；
- `/api/v2/certificates`、`/api/v2/eligibility/evaluate`、`/api/v2/knowledge/search`、`/api/v2/generations` 的 P50/P95/P99；
- restricted deny 路径确认不会触发正文读取、对象存储下载或外部模型调用；
- Postgres `EXPLAIN` 结果和慢查询清单。
