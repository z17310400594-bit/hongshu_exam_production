# P3 Golden Set Report — Batch 001

日期：2026-06-30  
用例文件：`docs/implementation/evaluation/p3_golden_cases.batch001.jsonl`  
运行脚本：`scripts/p3_golden_eval.py`

## 结论

P3 Batch 001 通过。

本批不是最终生产级 100 条黄金集，而是基于 P2 Batch 001 当前已迁数据建立的第一批真实可跑用例。后续 P2 数据继续补充时，直接向 JSONL 追加用例即可。

当前结果：

```text
status=pass
totalCases=10
structuredAccuracy=1.0
citationAccuracy=1.0
restrictedLeakRate=0.0
noEvidenceFacts=0
```

## 本批覆盖范围

| 类别 | 用例数 | 覆盖 |
|---|---:|---|
| certificate | 2 | 执业药师、一级建造师真实 code 可查 |
| exam_event | 2 | 2026 年执业药师/一级建造师官方考试日期 |
| eligibility | 2 | 执业药师本科本专业、相关专业本科报考判断 |
| knowledge_search | 1 | 教材部检索内部教辅片段 |
| permission | 1 | 运营部读取内部教辅集合被拒绝 |
| question_bank | 1 | 执业药师药一题库样例 |
| data_gap | 1 | 一级建造师报考条件未迁移，预期 `data_missing` |

## 运行命令

```bash
py scripts\p3_golden_eval.py docs\implementation\evaluation\p3_golden_cases.batch001.jsonl
```

定向测试：

```bash
py -m pytest api/tests/test_p3_golden.py -q
py -m ruff check api\services\acceptance.py api\services\p3_golden.py api\tests\test_p3_golden.py scripts\p3_golden_eval.py
```

结果：

```text
3 passed
All checks passed
```

## 关键用例

### P3-ELIG-001

问题：药学类本科、药学岗位满 24 个月，是否可报执业药师？

期望：

```text
decision=eligible
certificateCode=pharmacist_licensed
matchedRuleCode=cond_pharmacist_03
requiresCitation=true
citationAssetCodes=["doc_pharmacist_rule"]
```

结果：通过。

### P3-KNOW-001

问题：教材部检索 AUC 是否能命中执业药师药代动力学内部教辅片段？

期望：

```text
decision=found
itemCount=1
citationAssetCodes=["P2_PHARMACIST_INTERNAL_KP_NOTES"]
```

结果：通过。

### P3-SEC-001

问题：运营部是否不能读取教材部内部教辅资料？

期望：

```text
statusCode=403
forbiddenTerms=["AUC/半衰期","P2_PHARMACIST_INTERNAL_KP_NOTES"]
```

结果：通过，未泄漏 forbiddenTerms。

### P3-GAP-001

问题：一级建造师报考条件是否已经可判定？

期望：

```text
decision=insufficient_data
dataStatus=missing
```

结果：通过，分类为 `data_missing`。

这说明系统没有在缺少一建规则时硬猜答案；这正是当前阶段想要的行为。

## 与完整 P3 的差距

完整生产化 P3 仍需：

1. 补足 100 条真实业务问题；
2. 每条补人工确认答案和业务负责人；
3. 加入真实旧库/旧 API 输出，形成真正双读差异；
4. 扩展证书覆盖：
   - 一级建造师完整报考条件；
   - 执业医师；
   - 法考；
   - 卫生职称或康复治疗师；
5. 补省级报名时间、考区/考点类用例；
6. 把 `data_missing` 用例逐步转为可判定用例。

## 判定

P3 Batch 001 当前可以验收。

下一步建议二选一：

1. `P2-expand`：继续补数据，优先一建报考条件/政策/题库或省级报名时间；
2. `P4`：用当前执业药师 + 一建骨架数据做前端业务闭环增强。
