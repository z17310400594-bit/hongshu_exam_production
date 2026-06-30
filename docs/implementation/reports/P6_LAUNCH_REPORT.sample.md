# P6 上线报告模板

Date:
Operator:
Release branch:
Commit:

## 范围

- V2 API:
- 前端 feature flag:
- 数据库:
- 对象存储:

## 门禁结果

| Gate | Result | Evidence |
| --- | --- | --- |
| 数据库恢复对比 | pending | `p6_restore_comparison.json` |
| 对象存储恢复 | pending | 对象 manifest / 抽样下载记录 |
| P95 查询延迟 | pending | `p6_api_summary.json` |
| API 5xx | pending | `p6_api_summary.json` |
| 权限拒绝监控 | pending | `p6_api_summary.json` |
| 生成失败监控 | pending | `p6_api_summary.json` |
| 缺引用监控 | pending | `p6_api_summary.json` |
| 旧库只读 | pending | 只读账号/权限截图或 SQL 记录 |

## 回滚开关

| Flag | Rollback value | Owner |
| --- | --- | --- |
| TARO_APP_USE_V2_CERTIFICATE_API | false |  |
| TARO_APP_SHOW_V2_FLOW | false |  |
| GENERATION_PROVIDER | local |  |

## 结论

- Continue / pause / rollback:
- Reason:

