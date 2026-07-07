# P3 黄金集使用说明

P3 的目标是从“能查到”升级到“查得准、答得准、引用准、权限不漏”。

当前 `batch001` 不强行凑 100 条；它是基于 P2 已迁数据的第一批真实用例。后续补 P2 数据时，只需要继续追加 JSONL 记录。

## 运行

```bash
py scripts/p3_golden_eval.py docs/implementation/evaluation/p3_golden_cases.batch001.jsonl
```

可选输出 JSON 报告：

```bash
py scripts/p3_golden_eval.py docs/implementation/evaluation/p3_golden_cases.batch001.jsonl --output docs/implementation/reports/P3_GOLDEN_SET_REPORT.generated.json
```

## JSONL 字段

每行一条 case：

```json
{
  "id": "P3-ELIG-001",
  "category": "eligibility",
  "question": "药学类本科、药学岗位满 24 个月，是否可报执业药师？",
  "action": "eligibility",
  "params": {
    "certificateCode": "pharmacist_licensed",
    "degreeLevelCode": "bachelor"
  },
  "expected": {
    "decision": "eligible",
    "matchedRuleCode": "cond_pharmacist_03",
    "citationAssetCodes": ["doc_pharmacist_rule"],
    "requiresCitation": true
  }
}
```

## 当前支持 action

- `certificate_detail`
- `exam_event`
- `eligibility`
- `knowledge_search`
- `question_bank`

权限拒绝场景也使用真实 action，例如无权访问内部集合时 `knowledge_search` 会被规范化为：

```json
{"statusCode": 403, "error": {"code": "ACCESS_DENIED"}}
```

## 继续补 100 条时的原则

1. 每条必须有业务问题和 expected。
2. 能要求引用的必须写 `requiresCitation=true`。
3. 权限负向用例必须写 `forbiddenTerms`，用于检查越权泄漏。
4. 数据没补齐的用例可以先进入 `dataStatus=missing`，不要伪造答案。
5. 后续如果要做旧库双读，可以在 JSONL 中补 `oldResult`；当前 batch001 是 V2-vs-golden。
