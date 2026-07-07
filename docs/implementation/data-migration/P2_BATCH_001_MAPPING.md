# P2 Batch 001 Mapping — 真实数据小批迁移

日期：2026-06-30  
脚本：`scripts/p2_batch_001_seed.py`  
旧库来源：`backups/policy_fact_baseline_20260629.sql`  
官方来源：`http://www.cpta.com.cn/testPlan/2127.html`

## 目标

本批验证“旧库真实数据 → V2 结构 → API/权限闭环”可重复执行，不做全量迁移。

两层范围：

1. 用旧库 `cert_basic.cert_name` 建立公司当前业务支持证书目录底座。
2. 只对少量证书做深链路：
   - 执业药师：政策、报考条件、考试时间、知识点、题目、内部资料权限。
   - 一级建造师：目录、科目、2026 官方考试时间。

## 执行命令

```bash
py scripts/p2_batch_001_seed.py --dry-run
py scripts/p2_batch_001_seed.py --apply
```

统计：

| 项 | 数量 |
|---|---:|
| 证书目录 | 17 |
| aliases | 34 |
| 科目 | 8 |
| 2026 考试事件 | 2 |
| 知识点 | 8 |
| 报考条件规则 | 7 |
| 题目 | 6 |

## 旧库到 V2 映射

| 旧库表 | V2 表 | 策略 |
|---|---|---|
| `cert_basic` | `core.certificate` | `cert_id` 作为 V2 `code`，`cert_name` 作为名称 |
| `cert_basic.cert_name` | `core.certificate_alias` | alias_type=`common`，normalized_alias=`cert_id` |
| `cert_basic.short_name` | `core.certificate_alias` | alias_type=`short`，normalized_alias=`{cert_id}:short`，避免简称重复冲突 |
| `exam_subject` | `core.exam_subject` | 只迁本批深链路证书：执业药师、一级建造师 |
| CPTA 2026 考试计划 | `assessment.exam_event` / `assessment.exam_phase` | 只落官网确认的 written 考试日期 |
| `policy_doc` | `knowledge.asset/version` + `policy.document/version` | 政策原文作为 public asset，可溯源 |
| `policy_clause` | `knowledge.fragment` + `policy.clause` | 条款作为可引用 fragment |
| `exam_condition` | `policy.eligibility_rule` | 中文学历/专业枚举映射到 V2 code |
| `knowledge_point` | `knowledge.knowledge_point/scope` | 执业药师 7 个知识点 + 1 个报考条件知识点 |
| `exam_question` | `assessment.paper/question` | 执业药师 6 道题，挂内部 paper asset |
| `exam_question_kp` | `assessment.question_knowledge_point` | 题目与知识点关系 |

## 证书目录底座

| code | cert_name | short_name | category |
|---|---|---|---|
| cls1_constructor | 一级建造师 | 一建 | 准入类 |
| cls2_constructor | 二级建造师 | 二建 | 准入类 |
| cls1_firePorEngineer | 一级消防工程师 | 一消 | 准入类 |
| cls2_firePorEngineer | 二级消防工程师 | 二消 | 准入类 |
| cls1_costEngineer | 一级造价师 | 一造 | 准入类 |
| cls2_costEngineer | 二级造价师 | 二造 | 准入类 |
| yj_jzs5 | 消防操作员 | 一建 | 准入类 |
| yj_jzs4 | 安全工程师 | 一建 | 准入类 |
| yj_jzs3 | 中级经济师 | 一建 | 准入类 |
| yj_jzs2 | 注册会计师 | CPA | 准入类 |
| yj_jzs1 | 执业兽医师 | 一建 | 准入类 |
| physician_title | 卫生专业技术资格考试 | 职称医师 | 水平类 |
| pharmacist_licensed | 执业药师 | 执业药师 | 准入类 |
| physician_licensed | 执业医师 | 执业医师 | 准入类 |
| pharmacist | 药剂师 | 药剂师 | 准入类 |
| rehabilitation | 康复治疗师 | 康复治疗师 | 准入类 |
| nle | 法律执业资格考试 | 法考 | 准入类 |

旧库里多条证书的 `short_name=一建`，P2 已保留但用 `{cert_id}:short` 避免唯一约束冲突；简称质量问题进入 needs_review。

## 本批深链路

### 执业药师

V2 code：`pharmacist_licensed`

迁移内容：

- 科目：`pharmacist_licensed_yao1`、`pharmacist_licensed_yao2`、`pharmacist_licensed_fagui`、`pharmacist_licensed_zhonghe`
- 2026 官方考试日期：`2026-10-31` 至 `2026-11-01`
- 报考条件规则：`cond_pharmacist_01` 至 `cond_pharmacist_07`
- 7 个旧库知识点 + 1 个报考条件知识点
- 6 道旧库题目
- 内部资料集合：`coll_internal`
  - 教材部 `org_teaching_materials` 可读
  - 运营部 `org_operations` 不可读

### 一级建造师

V2 code：`cls1_constructor`

迁移内容：

- 科目：`yj_jzs_fagui`、`yj_jzs_jingji`、`yj_jzs_guanli`、`yj_jzs_shiwu`
- 2026 官方考试日期：`2026-09-12` 至 `2026-09-13`

未迁内容：

- 一级建造师报考条件、政策条款、题库、知识点，本批只标记缺口，不伪造。

## 官方来源处理

CPTA 年度计划详情页为图片形式：

- 入口页：`http://www.cpta.com.cn/testPlan.html`
- 详情页：`http://www.cpta.com.cn/testPlan/2127.html`
- 页面标题：`2026年度专业技术人员职业资格考试工作计划`
- 发布时间：`2026-02-03 15:20:00`

已读取官方图片：

- 建造师（一级）：`9月12日、13日`
- 执业药师（药学、中药学）：`10月31日、11月1日`

未落库内容：

- 各省报名时间；
- 具体考点/考区/考场城市；
- 准考证打印时间。

这些信息通常在各省人事考试网的报名通知中发布，进入 `P2_BATCH_001_NEEDS_REVIEW.csv`。

## 本地注意事项

当前本机 V2 数据库曾跑过 WP fixture / smoke，存在 `c_*` 测试证书。P2 脚本本身是幂等的，但演示时应按真实 code 查询：

- `pharmacist_licensed`
- `cls1_constructor`

不要用模糊查询结果第一条来判断 P2 是否成功。
