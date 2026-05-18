# Phase 55: JSON 输出增强 - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-17
**Phase:** 55-JSON 输出增强
**Areas discussed:** 输出结构定位, 函数粒度拆分, 数据流集成方式, 输出版本与兼容

---

## 输出结构定位

| Option | Description | Selected |
|--------|-------------|----------|
| 顶层数组 | 与 graphs_summary 保持一致的位置，方便下游 C++ 翻译器直接读取 | ✓ |
| 嵌套在 blueprint 内 | 与当前 graphs 数据嵌套位置一致，所有图相关数据归到 blueprint 下 | |
| 两者都有 | 顶层保留摘要，详细数据仍在 blueprint.graphs 内 | |

**User's choice:** 顶层数组（推荐）
**Notes:** 保持与 graphs_summary 一致的顶层位置

## 函数粒度拆分

| Option | Description | Selected |
|--------|-------------|----------|
| FunctionEntry 级别 | 每个 FunctionEntry 节点对应一个 function_graph 条目，与 C++ 函数一对一映射 | ✓ |
| 整图级别 | 每个 UEdGraph 对应一个 function_graph，内部包含多个函数 | |

**User's choice:** FunctionEntry 级别（推荐）
**Notes:** 与 Phase 53 的 build_execution_flows() 行为一致

## 数据流集成方式

| Option | Description | Selected |
|--------|-------------|----------|
| 节点内嵌标注 | 每个执行流节点对象内增加 data_providers 和 data_sources 字段 | ✓ |
| 平行数组 | function_graph 内平行挂载 execution_flows 和 data_flows 两个数组 | |
| 数据流作为 children | 数据流作为执行流节点的 children 字段嵌套 | |

**User's choice:** 节点内嵌标注（推荐）
**Notes:** 执行流和数据流在同一层级，C++ 翻译时可以直接看到节点的数据上下文

## 输出版本与兼容

| Option | Description | Selected |
|--------|-------------|----------|
| 4.x 内递增 | 新增字段，旧消费者不受影响（忽略未知字段） | |
| 升级到 5.0 + 开关 | output_version 升级到大版本，提供配置开关控制 | ✓ |

**User's choice:** 升级到 5.0 + 开关
**Notes:** 视为 breaking change，需要配置开关向后兼容

---

## Claude's Discretion

- function_graphs 条目的具体字段结构由 planner 确定
- 配置开关的实现方式（CLI flag / config file）由 planner 确定
- Phase 54 数据与 Phase 53 执行流节点的关联方式由 researcher 确定

## Deferred Ideas

None — discussion stayed within phase scope.
