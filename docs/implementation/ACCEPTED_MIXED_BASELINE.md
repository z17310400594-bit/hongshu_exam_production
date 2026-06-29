# 已接受混合基线提交

> 用途：避免后续 WP05+ 反复把历史混合提交当成当前工作包夹带问题，同时明确从此之后恢复严格边界。

## 基线提交

- Commit：`b91488c`
- 标题：`chore: sync skills, dify v4 pipeline, wp04 assets, data docs`
- 日期：2026-06-29
- 状态：用户确认其中非 WP04 内容为此前修改，保留；不改写历史。

## `b91488c` 包含的主要范围

- WP04 后端：
  - `api/main.py`
  - `api/models/knowledge.py`
  - `api/services/assets.py`
  - `api/tests/test_assets.py`
  - `api/tests/test_model_registry.py`
  - `db/migrations/versions/8fb1d4ac20f4_wp04_assets_versions_fragments.py`
  - `db/tests/test_wp04_constraints.py`
- 工作包/门禁文档：
  - `docs/implementation/SELF_TEST_GATE.md`
  - `docs/implementation/WORK_PACKAGE_TEMPLATE.md`
  - `docs/implementation/work-packages/WP04.md`
- 用户此前修改：
  - `.agents/skills/**`
  - `.claude/skills/**`
  - `docs/dify/v3/**`
  - `docs/数据说明/**`
  - `src/pages/workbench/components/ExamArticle/index.tsx`
  - `src/store/examArticleStore.ts`
  - `src/utils/md-parser.ts`

## 后续工作规则

1. WP05+ 的 scope review 固定从最新已完成状态提交开始，不再重新追责 `b91488c` 的混合范围。
2. 后续每个 WP 只能修改本包要求的 api/db/docs/implementation 文件；不得继续夹带 skills、Dify、前端、数据说明，除非该 WP 明确需要。
3. 若确实要继续修改 `b91488c` 中的非 WP04 内容，必须单独提交，提交标题应体现真实范围，例如：
   - `chore: sync agent skills`
   - `feat: update dify v4 pipeline`
   - `docs: update legacy data templates`
4. 缓存和临时文件不得进入 Git，包括：
   - `__pycache__/`
   - `*.pyc`
   - `.stylelintcache`
   - `.tmp/`
   - `docs/dify/v3/*backup_before*.py`

## 当前安全结论

- WP04 功能验证已完成，详见 `docs/implementation/reports/WP04_SELF_TEST.md`。
- `b91488c` 的混合性质是项目管理风险，不是 WP04 功能失败。
- 本文件之后的新增提交若再出现无关夹带，应视为新的工作包边界问题。
