# 数据问题清单

> 记录迁移过程中发现的数据问题、不确定项、需业务确认项。
> 每条标明来源、严重度、阻断阶段、处理状态。
> 严重度：P0 阻断发布 / P1 阻断迁移 / P2 需确认 / P3 记录备查。

## 一、数据分布画像（WP00 采集）

当前 `policy_fact` 库各表行数：

| 表 | 行数 | 备注 |
|---|---|---|
| cert_basic | 17 | 证书主表 |
| exam_subject | 31 | 考试科目 |
| knowledge_point | 41 | 知识点 |
| exam_condition | 32 | 报考条件（仅 6 个证书有） |
| exam_question | 26 | 真题 |
| exam_question_kp | 26 | 真题-知识点映射 |
| policy_clause | 28 | 政策条款 |
| viral_post | 12 | 爆款 |
| policy_doc | 7 | 政策文档 |
| exam_schedule | 4 | 考试日程（极少） |
| exemption | 6 | 免考 |
| registration_policy | 6 | 注册政策 |
| score_management | 6 | 合格标准 |
| years_calc_rule | 5 | 年限计算规则 |

## 二、发现的问题

### D001 · 建工类证书（一建/一造/一消）子表数据缺失 — P1

- **现象**：`cert_basic` 有 17 个证书，但仅 6 个 cert_id 在子表（exam_condition 等）有数据：`pharmacist_licensed`、`rehabilitation`、`pharmacist`、`nle`、`physician_title`、`physician_licensed`。
- **影响**：建工类证书（`cls1_constructor` 一建、`cls1_costEngineer` 一造、`cls1_firePorEngineer` 一消及二级对应证书）**只有主信息，无报考条件/考试日程/合格标准**。
- **API 表现**：`POST /query/policy {"cert_id":"cls1_constructor"}` 返回 cert 主信息但 conditions/schedules/score_rules 全为 `[]`。**这不是 API bug，是数据未导入**。
- **处理**：WP11 迁移时建工类证书数据若仍缺失，进入 `draft`，不发布。
- **来源**：WP00 数据库画像。
- **状态**：open，待业务确认建工数据是否另存别处或尚未录入。

### D002 · cert_id 命名混乱 / 一建简称误用 — P1

- **现象**：cert_id `yj_jzs2` 的 `cert_name` = "注册会计师"，`yj_jzs3` = "中级经济师"，`yj_jzs4` = "安全工程师"，`yj_jzs5` = "消防操作员"。前缀 `yj_jzs`（疑似"一建建造师"拼音首字母）与实际证书完全无关。
- **关联**：印证 HANDOFF 第 4 条"多个不相关证书错误共用一建简称和主管机关"。
- **处理**：WP03 清洗时进入 `needs_review`，**不擅自修正主管机构**，待业务确认。
- **来源**：WP00 cert_basic 画像。
- **状态**：open。

### D003 · `source_clause_id` 普遍为空 — P1

- **现象**：HANDOFF 第 1 条已记录——所有主要政策事实 CSV 的 `source_clause_id` 为空，事实溯源链未建立。
- **影响**：方案 §10/§11 要求"published 政策事实必须 approved 且有真实条款证据"，当前数据无法满足。
- **处理**：WP11 迁移时这些事实只能进 `draft`，直至人工补全证据。
- **来源**：HANDOFF §"已发现的重要问题"第 1 条。
- **状态**：open。

### D004 · `relates_to_type/id` 错误目标 — P1

- **现象**：HANDOFF 第 2 条——无 FK 的 `policy_clause.relates_to_type/id` 已存在 11 条错误目标。
- **处理**：V2 设计改用显式 `policy.eligibility_rule_evidence` 关联表（见 02-schema-v2.sql），WP06 迁移时丢弃多态 `relates_to`，重建证据关联；错误目标不自动迁移，进 `needs_review`。
- **来源**：HANDOFF 第 2 条。
- **状态**：open。

### D005 · `exam_schedule` 重复主键 — P1

- **现象**：HANDOFF 第 3 条——`sched_pharmacist_2026` 重复主键且关联两个不同证书。
- **处理**：WP07 拆分 exam_event/phase，V2 用 `UNIQUE(certificate_id, exam_year, region_code)` 约束；重复记录进 `needs_review`。
- **来源**：HANDOFF 第 3 条。
- **状态**：open。

### D006 · 报考条件模型维度不足 — P2

- **现象**：HANDOFF 第 5 条——现有 `exam_condition` 缺少资格级别、报考路径、地区、入学截止日期等维度。
- **处理**：V2 `policy.eligibility_rule` 已扩展这些字段（route_code、admission_before、region_code 等）；旧数据无法自动填充的维度进 `draft`。
- **来源**：HANDOFF 第 5 条。
- **状态**：open。

## 三、需业务确认项（迁移前不必定，发布前必须定）

- D001：建工类证书数据是否尚未录入，还是存于别处？
- D002：`yj_jzs*` 系列证书的真实主管机构与简称？
- 部门、角色、审批链组织结构（IAM 建模用，WP02）。
- 四级保密分类是否符合公司制度（WP02）。
- 哪些私有资料可发往哪些模型供应商（WP10/WP14）。
- 教材/教辅/题库的最终审核责任人。
