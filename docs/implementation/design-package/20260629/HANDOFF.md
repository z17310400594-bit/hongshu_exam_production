# 下一模型执行交接

## 任务目标

在 `D:\taro_project\workbench\taro_workbench` 中实施“企业知识资产平台 V2”，并将桌面两个资料目录中的政策、考试、题库和运营数据迁入新模型。当前交付包是设计基线，不代表已经完成代码实施。

## 已审查来源

- 项目：`D:\taro_project\workbench\taro_workbench`
- 原数据库设计：`C:\Users\Administrator\Desktop\企业项目升级相关数据库`
- CSV 和说明：`C:\Users\Administrator\Desktop\数据说明`

## 已发现的重要问题

1. 所有主要政策事实 CSV 的 `source_clause_id` 为空，事实溯源链未建立。
2. 无 FK 的 `relates_to_type/id` 已存在 11 条错误目标。
3. `exam_schedule.csv` 的 `sched_pharmacist_2026` 重复主键且关联两个不同证书。
4. 多个不相关证书错误共用“一建”简称和主管机关。
5. 报考条件模型缺少资格级别、报考路径、地区、入学截止日期等维度。
6. API 没有有效政策过滤；`_query()` 吞异常并返回空数组。
7. 数据库默认凭证、开放 CORS 和前端 Dify API Key 存在高风险。不得在交付或日志中复述实际密钥，需立即轮换。
8. 仓库没有正式数据库 migration/compose，DDL 主要存在桌面资料中。

## 建议 skills

- `postgres-patterns`：DDL、索引、约束与查询设计。
- `database-migrations`：双库迁移、回填、灰度和回滚。
- `fastapi-patterns`：若保留 Python/FastAPI API。
- `api-design`：稳定 API 契约、错误模型和分页。
- `tdd`：先写 schema/API/ACL 失败用例再实现。
- `production-audit`：上线前安全、恢复和观测审计。

## 执行顺序

1. 阅读本目录全部文件，形成实施计划，不先改代码。
2. 对现有数据库做备份，轮换已暴露密钥。
3. 将 `02-schema-v2.sql` 拆成有序 migrations，并为每项约束写测试。
4. 建 staging/import validation，不允许直接 COPY 正式表。
5. 清洗现有 CSV，建立旧 ID 到新 code 映射；不确定来源数据保持 draft。
6. 实施 API/BFF、身份认证、collection ACL、政策有效期过滤。
7. 改造 Taro 前端，移除直连 Dify 和前端密钥。
8. 建 valid/invalid fixtures、100 条真实查询评测集和越权测试。
9. 双读比较，达到验收指标后灰度切换；旧库只读保留两个发布周期。

## 必须向用户确认的业务决策

- 部门、角色和审批链的真实组织结构；
- 四级保密分类是否符合公司制度；
- 哪些私有资料可发送至哪些模型供应商；
- 教材、教辅、题库的最终审核责任人；
- 知识点编码由谁维护以及合并/废弃流程；
- 原文件对象存储和备份位置；
- 版权、引用长度和训练使用政策；
- 首期 MVP 的证书、教材和部门范围。

## 完成定义

- 空库可通过 migrations 一键重建；
- valid fixtures 全部成功，invalid fixtures 命中指定错误码；
- published 政策事实全部 approved 且有真实条款证据；
- restricted 越权测试泄漏率为 0；
- 前端和仓库不含 Dify/数据库秘密；
- API 返回结构化判断和版本化引用；
- 备份恢复、回滚、双读对比均完成演练并留存报告。
