---
name: taro-core-constraints
description: Taro 项目核心禁止事项和红线约束
metadata:
  type: project
---

## 核心约束（不可违反）

### 平台兼容
- ❌ 禁止 DOM API（`document`、`window`、`getElementById`）
- ❌ 禁止 `innerHTML` / `dangerouslySetInnerHTML`
- 标签映射：`<div>` → `<View>`，`<span>` → `<Text>`，`<a>` → `<Navigator>`，`<img>` → `<Image>`
- 跨端差异用 `process.env.TARO_ENV === 'weapp'/'h5'` 条件编译，或拆成 `.h5.ts` / `.weapp.ts` 文件

### 包体积
- 主包 ≤ 2MB，总包 ≤ 20MB
- 禁止全量引入 UI 库、lodash 等。lodash 按函数引入：`import debounce from 'lodash-es/debounce'`
- 图片放 CDN，不分包

### 代码规范
- ❌ 禁止 `any`（除非有充分理由并加注释）
- ❌ 禁止 `@ts-ignore`（用 `@ts-expect-error` 替代并注释）
- ❌ 禁止 `console.log` 提交
- ❌ 禁止硬编码用户可见文案
- ❌ 禁止 `eval`、`new Function`
- 组件 Props 必须定义 TS 接口
- 禁止 render 中创建匿名函数/对象

### API 规范
- 所有请求走 `services/`，禁止页面内直接调 `Taro.request`
- 每个 API 函数返回类型必须明确

### 提交前检查
- `npm run typecheck` 零错误
- `npm run lint` 零 warning
- `npm run build:weapp` 成功且主包不超限

**Why:** 这些是项目硬约束，违反会导致编译失败、小程序审核不通过、或跨端表现不一致。上下文压缩后最容易遗忘的是具体禁止项。

**How to apply:** 每次写代码前自查：有没有用 DOM API？标签对不对？有没有引入全量库？提交前跑 typecheck + lint + build:weapp。
