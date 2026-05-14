# Phase 14: 输出格式优化并冻结 - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-03
**Phase:** 14-output-format-optimization
**Areas discussed:** status字段设计, graphs_summary结构, 摘要精简策略, Markdown格式设计

---

## status字段设计

| Option | Description | Selected |
|--------|-------------|----------|
| 三元分类 | success/fail/error，警告不算 fail | ✓ |
| 二元简化 | success/fail，警告合并到 success | |
| 严格判定 | 三元分类，但警告也算 fail | |

**Question 2:** status 字段附带哪些附加字段？

| Option | Description | Selected |
|--------|-------------|----------|
| JSend完整结构 | status + message + code 字段 | ✓ |
| 最小结构 | 仅 status 字段，错误信息在 errors 数组 | |
| 扩展结构 | status + 各状态不同附加字段 | |

**Question 3:** status 结构放在 JSON 输出的什么位置？

| Option | Description | Selected |
|--------|-------------|----------|
| 顶层 status 对象 | JSON 顶层 status 对象包含 status/message/code | ✓ |
| 扁平顶层字段 | 顶层 status 字段字符串，message/code 同级 | |
| 嵌套 summary | 嵌套在 summary 对象中 | |

**Notes:** 用户选择遵循 JSend 规范的三元分类和完整结构，顶层位置便于 AI 快速判断解析结果。

---

## graphs_summary结构

| Option | Description | Selected |
|--------|-------------|----------|
| 函数调用链 | 仅函数调用序列 [{event, calls: [...]}] | ✓ |
| 详细节点信息 | 完整节点列表含 inputs/outputs | |
| 统计概览 | graph_count/node_count/event_count | |

**Question 2:** 多个蓝图图如何处理？

| Option | Description | Selected |
|--------|-------------|----------|
| 按图分组 | 每个图一个 execution_flows 条目 | ✓ |
| 合并所有图 | 所有图执行流合并为一个数组 | |
| 仅主图 | 仅 EventGraph，忽略其他图 | |

**Question 3:** execution_flows 中函数调用的详细程度？

| Option | Description | Selected |
|--------|-------------|----------|
| 函数名+参数类型 | 如 "PrintString(InStr:String)" | ✓ |
| 仅函数名 | 如 "PrintString" | |
| 完整参数信息 | 函数名+参数名+类型 | |

**Notes:** 用户选择简洁的函数调用链格式，按图分组便于理解不同图的逻辑流程。

---

## 摘要精简策略

| Option | Description | Selected |
|--------|-------------|----------|
| 移除依赖字段 | 移除 imports/soft_references/circular_deps/errors | ✓ |
| 保留错误信息 | 仅移除 imports/soft_references | |
| 极简模式 | 仅保留 summary 和 graphs_summary | |

**Question 2:** exports 数组如何精简？

| Option | Description | Selected |
|--------|-------------|----------|
| 精简 exports | 仅保留 name/class/parent_class | ✓ |
| 完整 exports | 保留所有字段 | |
| 极简 exports | 仅保留 name 和 class | |

**Question 3:** properties 数组如何处理？

| Option | Description | Selected |
|--------|-------------|----------|
| 移除 properties | 摘要模式不含属性详情 | ✓ |
| 关键属性 | 仅保留关键属性如 RelativeLocation | |
| 完整 properties | 保留完整 properties 数组 | |

**Notes:** 用户选择激进精简策略以达到 70%+ token 减少目标，移除依赖字段和 properties 数组。

---

## Markdown格式设计

| Option | Description | Selected |
|--------|-------------|----------|
| 三节结构 | Asset Overview / Blueprint Details / Graph Summary / Exports | ✓ |
| 通用结构 | Summary / Details / Raw Data | |
| 按 export 分节 | 每个 export 为一个 ## 章节 | |

**Question 2:** 数据展示形式？

| Option | Description | Selected |
|--------|-------------|----------|
| 表格优先 | exports 和属性用 Markdown 表格 | ✓ |
| 列表优先 | 使用列表展示数据 | |
| 混合格式 | 表格概览 + 列表详细 | |

**Question 3:** execution_flows 如何展示？

| Option | Description | Selected |
|--------|-------------|----------|
| Mermaid 流程图 | 使用 ```mermaid 流程图语法 | ✓ |
| JSON 代码块 | 使用 ```json 展示原始 JSON | |
| 列表格式 | 使用列表展示调用链 | |

**Notes:** 用户选择三节结构配合表格优先展示，Mermaid 流程图可视化执行流程便于人类和 AI 理解。

---

## Claude's Discretion

- status.code 错误码枚举值命名
- Mermaid 图布局方向（LR vs TD）
- _schema 字段的具体内容结构
- 单元测试组织和测试资产选择

## Deferred Ideas

无 — 讨论保持在 Phase 14 范围内。

---

*Discussion log generated: 2026-05-03*