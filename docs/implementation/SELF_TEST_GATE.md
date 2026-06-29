# 工作包自测与验收门禁

> 适用于 WP02-WP16。执行 Agent 必须完成“实现自测 + 提交后冷启动复验”并提交可复核证据，才能把工作包标记为 `completed / PASS`。
> 目标：验收 Agent 只需复跑统一门禁和抽查证据，不应再次发现循环导入、假 Alembic 通过、测试环境污染、文档 commit 过期等基础问题。

## 零、一次交付原则

- 不接受“我运行过”“应该没问题”或只给结论；必须给命令、退出码和关键输出。
- 不接受只跑新增测试；专项测试与全量测试必须同时通过。
- 不接受进程内偶然通过；关键模块、迁移和 API 必须在全新进程中验证。
- 不接受工具假绿；返回码为 0 且输出无 traceback、warning、`not recognized`、未 await 协程等异常信息才算通过。
- 不接受测试顺序依赖；每个新增测试文件必须能够单独运行，也能进入全量套件运行。
- 不接受先标记 `PASS` 再补证据。任何失败都必须恢复或保持 `in_progress`。
- 不接受状态真相源不一致；`IMPLEMENTATION_STATUS.md`、`NEXT_TASK.md`、最终实现 commit 和测试数字必须一致。

## 强制执行顺序

1. 读取 `IMPLEMENTATION_STATUS.md`、`NEXT_TASK.md`、`DECISIONS.md`，确认前置包完成。
2. 将当前包改为 `in_progress`，只修改本包范围。
3. 先写失败用例再实现；覆盖正常、拒绝、约束失败和信息泄漏。
4. 完成第一阶段：专项测试、Python 门禁、迁移门禁、真实服务冒烟、前端回归和安全检查。
5. 提交实现 commit，记录 `IMPLEMENTATION_SHA`；再更新状态文档，禁止预填不存在的 commit。
6. 完成第二阶段：从新终端/新 Python 进程复跑统一门禁、模块导入、真实 API 与 diff 检查。
7. 保存自测报告；全部通过后才允许标记 `completed / PASS` 并路由到下一包。

任一必测项失败：保持 `in_progress`，修复后从第一阶段重新执行完整门禁；不得只重跑刚失败的一条。

## 通用门禁

在 Windows 仓库根目录执行：

```bat
scripts\validate.bat
python -m pytest api/tests db/tests -q
python -m ruff check api db
python -m pyright api db --pythonversion 3.12
python -m alembic current
python -m alembic check
python -m api.run
```

必须通过 `cmd.exe /c scripts\validate.bat` 调用并记录 `%ERRORLEVEL%`。脚本必须 fail-fast；任何子命令失败时整体非 0，且不得在报错后仍打印 `ALL CHECKS PASSED`。

另开终端请求 `/health/live`、`/health/ready`：都必须 HTTP 200，ready 必须为 `database=connected`。必须通过真实 Uvicorn 入口，不能只用 ASGITransport；验证后关闭服务。

迁移测试必须使用独立测试库，执行 upgrade → downgrade → upgrade，最终位于 head；不得对开发库或基线库执行 `downgrade base`，并要证明开发库未被迁移或回滚。

## 数据库与 Alembic 硬门禁

只要工作包新增或修改 ORM、表、约束、schema 或 migration，以下全部为必测项：

1. 所有模型模块必须在 `target_metadata` 赋值和 `context.configure()` 之前导入。
2. 使用非默认 PostgreSQL schema 时，online/offline 两个 `context.configure()` 都必须设置 `include_schemas=True`。
3. 新进程中断言 `Base.metadata.tables` 精确包含本包应有表，且不包含后续工作包表。
4. `python -m alembic check` 必须返回 0；不能仅凭它判断无漂移。
5. 再使用 `MigrationContext + compare_metadata(... include_schemas=True)` 做独立比较，必须输出 `diff_count=0`。
6. migration upgrade → downgrade → upgrade 必须在独立测试库完成；最终 head、测试库清理、开发库不变均需断言。
7. ORM 类型必须与数据库完全一致，包括 timezone、数组、默认值、nullable、on-delete、复合主键和 schema。
8. 每个 FK、CHECK、UNIQUE/PK 至少一个失败用例；新增约束数量必须与失败用例清单逐项对应。

禁止将模型导入放在 `run_migrations_online()` 调用之后；禁止用空 metadata 或未扫描 schema 的 `alembic check` 作为通过证据。

## 冷启动与导入独立性

对每个新增或修改的 Python 模块执行独立进程导入，例如：

```bat
python -c "import api.database; import api.deps; import api.main; print('imports_ok')"
```

- 禁止依赖 pytest 的导入顺序、其他测试预先导入模型或模块级副作用。
- 出现 `partially initialized module` 即为循环导入失败。
- 数据库 engine、配置、模型注册应有单一来源；禁止 `main.py` 与依赖模块互相导入。
- 新增测试文件要分别执行 `python -m pytest <file> -q`，结束后不得遗留测试库、服务进程或临时数据。

前端即使未修改也要运行：

```bat
npm.cmd run build:h5
npm.cmd run typecheck
npm.cmd run lint
```

- 构建必须成功。
- typecheck 基线 1046 个错误，lint 基线 7 errors、3 warnings，均不得增加。
- 若修改前端，涉及文件不得新增错误，不能只看总数。

最后检查 `git diff --check`、`git status --short`、`git diff --stat`、`git diff --name-only`，并扫描 api/db/infra 的 password、secret、API key、Bearer。不得包含真实凭据、缓存/构建产物、越界文件或用户原有改动；真实 `.env` 不得入库。

## 真实 API 与安全门禁

- 必须使用正式启动入口启动 Uvicorn，再从另一个进程请求；ASGITransport 只算单元测试。
- 至少验证 live、ready、一个允许请求、一个拒绝请求、缺少身份请求和未知资源请求。
- 同时捕获响应体、应用日志和访问日志；敏感标题、正文、内部 ID、密级详情不得出现。
- 拒绝路径必须证明正文查询、向量检索、对象存储读取等下游函数没有被调用。
- 冒烟结束必须主动停止服务，并检查端口上没有遗留本次进程。

## 提交与状态一致性门禁

最终提交后重新执行：

```bat
git diff --check <BASE_SHA>...HEAD
git log --oneline <BASE_SHA>..HEAD
git status --short
cmd.exe /c scripts\validate.bat
```

- `IMPLEMENTATION_STATUS.md` 记录最终实现 commit，不得指向已被后续修复淘汰的 commit。
- `NEXT_TASK.md` 的 commit、测试数量和结论必须与状态文件及实际输出一致。
- 状态文档引用的文件必须已被 `git ls-files` 跟踪。
- 工作包提交不得夹带开始前已有的用户修改、缓存或其他工作包内容。
- 状态更新之后发生任何代码修改，原 PASS 自动失效，必须重新跑第二阶段并更新报告。

## WP02 专项自测

| 场景 | 数据 | 期望 |
|---|---|---|
| internal 允许 | 教材部用户读教材部内部集合 | allow |
| restricted 拒绝 | 运营部用户读教辅部 restricted 集合 | HTTP 403 |
| public 允许 | 有效用户读 public 集合 | allow |
| 默认拒绝 | 无身份、未知部门或无 ACL | HTTP 403 |
| 检索前授权 | 无权请求进入检索入口 | 不调用正文/向量检索 |
| 防泄漏 | 请求存在但无权访问的集合 | 响应及日志不含标题、正文、内部 ID、密级详情 |
| FK/CHECK | 不存在引用、非法密级/主体类型/层级 | 数据库拒绝 |
| 唯一性 | 重复组织、集合标识或 ACL | 数据库拒绝 |
| 迁移回环 | 测试库 upgrade → downgrade → upgrade | 成功且位于 head |

测试必须包括：

- `db/tests/`：schema、FK、CHECK、UNIQUE、隔离迁移回环。
- `api/tests/`：身份适配、授权矩阵、403、防泄漏、检索前拦截。
- fixtures：教材部、教辅部、运营部，四级密级，以及允许/拒绝样本。

WP02 不得创建证书、资产、知识点、试卷等后续业务表，不得接入真实检索正文。正向测试必须连接真实测试库；负向 mock 必须符合真实同步/异步协议；pytest 不得有 warning；403 防泄漏必须同时检查响应和日志。

## 完成报告

报告必须保存为 `docs/implementation/reports/WPxx_SELF_TEST.md`，不能只存在于聊天消息中。至少包含：

```text
WPxx SELF-TEST REPORT
Base SHA: <开始固定点>
Implementation SHA: <最终实现提交>
Scope: <允许修改范围 + 实际文件列表>
Migration: PASS/FAIL（测试库、upgrade/downgrade/upgrade）
Metadata: PASS/FAIL（表清单、include_schemas、diff_count）
Cold imports: PASS/FAIL（逐个模块）
Special tests: PASS/FAIL（通过数/总数）
Pytest: PASS/FAIL（通过数、warning 数）
Ruff: PASS/FAIL（错误数）
Pyright: PASS/FAIL（错误数）
API smoke: live=<结果>, ready=<结果>, allow=<结果>, deny=<结果>, anonymous=<结果>
Leak/downstream: PASS/FAIL（响应、应用日志、访问日志、下游未调用）
Frontend: build=<结果>, typecheck=<当前/基线>, lint=<当前/基线>
Security/diff: PASS/FAIL（secret scan、diff check、越界文件）
Test cleanup: PASS/FAIL（测试库、端口、进程、临时文件）
Status consistency: PASS/FAIL（状态、NEXT_TASK、commit、测试数字）
Validation command exit code: 0/<非零>
Overall: PASS/FAIL
```

报告中每个 PASS 必须附命令与关键输出；失败输出不得删除。只有 `Overall: PASS`、统一脚本退出码为 0、没有 warning、没有未解释回归时，才允许更新状态文档。

## 验收 Agent 的快速复核入口

执行 Agent 完成上述报告后，验收 Agent原则上只需：

1. 对照报告与 Git diff 抽查范围和测试矩阵。
2. 运行 `cmd.exe /c scripts\validate.bat`。
3. 运行独立 metadata/schema 比较与模块冷导入。
4. 运行一次真实 API allow/deny 冒烟。
5. 核对状态文档与 commit。

若快速复核发现报告未披露的基础问题，该工作包自动退回 `in_progress`，执行 Agent必须补充对应自动化测试或门禁，不能只修当前实例。
