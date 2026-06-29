# 工作包执行模板

> 每个 WP 开始前复制为 `work-packages/WPxx.md`。需求追踪矩阵完成前禁止编码。

## 身份与范围

- 工作包：
- 状态：pending / in_progress / completed / blocked
- Base SHA：
- 前置工作包：
- 停止点：
- 明确不在范围：

## 权威来源

列出原始实施计划、schema、字段字典、测试模板和决策文件的路径及行号。NEXT_TASK 不能作为唯一来源。

## 需求追踪矩阵

| ID | 原始要求 | 来源文件/行 | 实现位置 | 测试位置 | 验证证据 | 状态 |
|---|---|---|---|---|---|---|
| R01 |  |  | pending | pending | pending | pending |

## 验收矩阵

| ID | 场景 | 输入/前置 | 期望 | 自动化测试 |
|---|---|---|---|---|
| A01 | 正常路径 |  |  | pending |
| A02 | 拒绝/不存在 |  |  | pending |
| A03 | 重复/歧义 |  |  | pending |
| A04 | FK/CHECK/UNIQUE |  |  | pending |
| A05 | migration 回环 | 独立测试库 | upgrade→downgrade→upgrade | pending |

## 数据与清洗

- 有效 fixtures：
- 无效 fixtures：
- 旧 ID/旧编码映射：
- mapped/rejected/needs_review 数量：
- 禁止自行猜测的数据：

## 未实现/不适用

逐项说明。没有时写“无”，不得留空。

## 自测证据

按 `SELF_TEST_GATE.md` 生成 `reports/WPxx_SELF_TEST.md`。矩阵全为 done 且统一门禁退出码为 0 后才能完成。
