# 数据库备份

## WP00 基线备份

- **文件**：`policy_fact_baseline_20260629.sql`
- **来源**：`policy-db` 容器（postgres:15-alpine，端口映射 5433→5432）
- **库名**：`policy_fact`，用户 `policy`
- **导出方式**：`pg_dump --no-owner --no-privileges`
- **大小/行数**：102605 字节 / 1115 行
- **内容**：14 张表（CREATE TABLE + COPY 数据）
- **SHA-256**：`4f7b1f6076702f29cd73a9233602ae598e4c297d596e110f68dff3abdf4f7c9a`
- **日期**：2026-06-29

## 恢复验证流程

**不要直接向现有 policy_fact 库恢复**（会产生对象冲突）。应走独立验证流程：

```bash
# 1. 创建临时恢复测试库（通过 psql，兼容 Alpine 的 createdb 限制）
docker exec policy-db psql -U policy -d policy_fact -c "
  DROP DATABASE IF EXISTS policy_fact_restore_test;
  CREATE DATABASE policy_fact_restore_test OWNER policy;
"

# 2. 导入备份（cat | docker exec -i 兼容 PowerShell 和 Bash）
cat backups/policy_fact_baseline_20260629.sql | docker exec -i policy-db psql -U policy -d policy_fact_restore_test -q

# 3. 对比表数和行数（应与 manifest.json 中 data_distribution 一致）
docker exec policy-db psql -U policy -d policy_fact_restore_test -c "
  SELECT t.tablename, s.n_live_tup
  FROM pg_catalog.pg_tables t
  LEFT JOIN pg_stat_user_tables s ON t.tablename = s.relname
  WHERE t.schemaname = 'public'
  ORDER BY t.tablename;
"

# 4. 验证通过后删除测试库
docker exec policy-db psql -U policy -d policy_fact -c "DROP DATABASE IF EXISTS policy_fact_restore_test;"
```

> **已实测验证**：2026-06-29 完整恢复流程通过，14 表结构与行数均与生产库一致。

## 注意

- `.gitignore` 已排除所有 `*.sql` `*.dump`，本目录的 README 可提交，备份数据不可提交。
- 后续 WP01+ 建立新数据库后，本备份仅作历史存档；**不要用此备份覆盖 V2 新表**。
