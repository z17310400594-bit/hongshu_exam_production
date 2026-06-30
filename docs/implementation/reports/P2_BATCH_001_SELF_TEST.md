# P2 Batch 001 Self Test — 真实数据小批迁移

日期：2026-06-30  
脚本：`scripts/p2_batch_001_seed.py`  
状态：通过，可进入 P3 前准备。

## 范围

本批完成：

- 从旧库 `cert_basic` 建立 17 个证书目录底座。
- 深迁移执业药师：科目、2026 官方考试日期、报考条件、政策证据、知识点、内部资料片段、题库样例、权限验证。
- 为一级建造师迁移：证书目录、科目、2026 官方考试日期。

## 官方核验

中国人事考试网可通过 HTTP 打开考试计划列表：

```text
http://www.cpta.com.cn/testPlan.html
```

列表中存在：

```text
2026年度专业技术人员职业资格考试工作计划
发布时间：2026-02-03
详情页：http://www.cpta.com.cn/testPlan/2127.html
```

详情页内容为图片。已读取图片第 3 页：

- 建造师（一级）：9月12日、13日；
- 执业药师（药学、中药学）：10月31日、11月1日。

说明：

- `https://www.cpta.com.cn/testPlan.html` 在本机 curl/Python 下 TLS 握手失败，但 `http://www.cpta.com.cn/testPlan.html` 可访问。
- 国家药监局 NMPA 页面在本机 curl 下返回反爬挑战页；旧库中已保留官方 URL 和政策原文，后续建议人工浏览器核验。

## 执行命令与结果

### dry-run

```bash
py scripts\p2_batch_001_seed.py --dry-run
```

结果：

```json
{"aliases": 34, "certificates": 17, "eligibility_rules": 7, "exam_events": 2, "knowledge_points": 8, "questions": 6, "subjects": 8}
```

### apply

```bash
py -m alembic upgrade head
py scripts\p2_batch_001_seed.py --apply
```

结果：

```json
{"aliases": 34, "certificates": 17, "eligibility_rules": 7, "exam_events": 2, "knowledge_points": 8, "questions": 6, "subjects": 8}
```

## 自动化检查

| 检查 | 命令 | 结果 |
|---|---|---|
| P2 parser/official date tests | `py -m pytest api/tests/test_p2_batch_001_seed.py -q` | `3 passed` |
| P2 script lint | `py -m ruff check scripts\p2_batch_001_seed.py api\tests\test_p2_batch_001_seed.py` | `All checks passed` |

## 本地数据库统计

```text
cert_total=22
p2_events=2
p2_kp=8
p2_questions=6
needs_old_fixture=11
```

说明：

- `cert_total=22` 是因为本机 V2 库已有 WP fixture/smoke 数据。
- P2 真实目录脚本导入 17 个旧库业务证书。
- 演示时应按真实 code 查询，不用模糊查询第一条判断。

## API / Service 抽样

结果：

```text
detail_pharmacist_code= pharmacist_licensed
detail_constructor_code= cls1_constructor
pharm_event_code= P2_CPTA_2026_PHARMACIST
pharm_written= 2026-10-31
constructor_written= 2026-09-12
eligibility_decision= eligible
eligibility_rule= cond_pharmacist_03
knowledge_allowed= 1
knowledge_denied=YES
questions= 6
```

验收含义：

- 执业药师和一级建造师真实 code 可查。
- 两个 2026 官方考试事件可查。
- 执业药师本科/本专业/24 个月样例命中旧库规则 `cond_pharmacist_03`。
- 教材部可检索内部教辅资料。
- 运营部读取内部集合被拒绝。
- 执业药师药一题库样例返回 6 道题。

## 已知未完成

见：

```text
docs/implementation/data-migration/P2_BATCH_001_NEEDS_REVIEW.csv
```

关键缺口：

1. 各省报名时间和具体考点/考区未迁移。
2. 一建只迁目录、科目、2026 考试日期，未迁政策规则和题库。
3. 本机库有历史 fixture/smoke 数据，正式演示建议用干净库。
4. 执业药师报考年限需用 2026 报名通知做最终口径核验。

## P2 判定

P2 Batch 001 当前状态：通过。

可以进入下一步，但建议 P3 前先决定：

- 是否清理本地演示库历史 fixture/smoke 数据；
- 是否先补省级报名通知/考区数据；
- 是否把一建从“骨架”扩为完整闭环。
