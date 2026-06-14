# Dify Workflow 代码节点

## 目录结构

```
docs/dify/
├── README.md                    # 本文件
├── v1/                          # V1 基线版（当前生产运行中）
│   ├── CODE_1.py                # 参数计算：倒计时/阶段分配/days_grid
│   ├── CODE_A.py                # 参数构造：每张卡片的 system/user prompt
│   └── CODE_2.py                # 后处理：LLM 输出合并校验
├── v2/                          # V2 优化版（待部署）
│   ├── CODE_0_prompt.md         # 新增 LLM 节点：叙事规划（sys+user prompt）
│   ├── CODE_1.py                # 参数计算 V2：+叙事上下文 +密度约束 +话题分派
│   ├── CODE_A.py                # 参数构造 V2：TONE_BLOCK重组 +人群CTA +subjects/priority互斥
│   └── CODE_2.py                # 后处理 V2：修复duration覆盖bug +清洗<think>标签
├── v3-knowledge-base-design.md  # V3 设计稿：知识库集成 + chunk策略 + 检索方案
├── v1.1-dify-changes.md         # V1.1 Dify 改动清单（入参/出参/卡片类型）
├── v1.1-dify-test-cases.json    # V1.1 测试用例（6 个 TC）
├── v1.1-prompt-optimization.md  # V2 质量优化方案（诊断+策略+实施步骤）
├── v1.1-work-plan.md            # V1.1 工作文档
└── dify_1.1_demo.md             # V1.1 实际生成样本日志
```

## 版本概览

| 版本 | 拓扑 | 卡片类型 | 关键特征 |
|------|------|----------|----------|
| V1 | START→CODE_1→Iterator(CODE_A→LLM)→CODE_2→END | 8种 | 3角色画像，逐卡生成 |
| V1.1 | 同上 | 9种(+study_material) | +target_audience/theme入参，4人群画像 |
| V2 | START→CODE_0→CODE_1→Iterator(CODE_A→LLM)→CODE_2→END | 9种 | +叙事规划 +人群共鸣 +话题分派 +duration修复 |
| V3 | START→CODE_0→CODE_1→Iterator(CODE_A→**KB检索**→LLM)→CODE_2→END | 9种 | +知识库检索 +chunk溯源 +考点可验证 |

## 使用方式

1. 打开 Dify 后台 → 备考卡片生成 Workflow
2. 找到对应 CODE 节点 → 全选删除 → 粘贴 `v1/` 或 `v2/` 下对应文件全部内容
3. 检查输入变量映射是否与函数签名一致
4. V2 部署需先新增 CODE_0 LLM 节点（prompt 见 `v2/CODE_0_prompt.md`）

## Dify 连接信息

- API: `http://localhost/v1/workflows/run`
- API Key: `app-SLc5nNMlGTuR8XJrEY48ssY1`
- 前端服务文件: `src/services/dify.ts`

## 文件规范

- **唯一存放位置**：`docs/dify/v<N>/`，禁止在项目根目录散落 `CODE_*.py`
- **当前生产**：`v1/` 部署在 Dify
- **V2 待部署**：`v2/` 含 CODE_0 叙事规划节点 + 优化版 CODE_1/CODE_A/CODE_2
- **当前 v1 和 v2 内容相同**（均为 V1 + ASCII 标点清洗），V2 优化逻辑待后续应用
