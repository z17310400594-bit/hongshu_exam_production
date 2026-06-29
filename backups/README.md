# 数据库备份

## WP00 基线备份

- **文件**：`policy_fact_baseline_20260629.sql`
- **来源**：`policy-db` 容器（postgres:15-alpine，端口映射 5433→5432）
- **库名**：`policy_fact`，用户 `policy`
- **导出方式**：`pg_dump --no-owner --no-privileges`
- **大小/行数**：102605 字节 / 1115 行
- **内容**：14 张表（CREATE TABLE + COPY 数据）
- **日期**：2026-06-29

## 恢复命令（参考）

```bash
docker exec -i policy-db psql -U policy -d policy_fact < backups/policy_fact_baseline_20260629.sql
```

## 注意

- `.gitignore` 已排除所有 `*.sql` `*.dump`，本目录的 README 可提交，备份数据不可提交。
- 后续 WP01+ 建立新数据库后，本备份仅作历史存档；**不要用此备份覆盖 V2 新表**。
