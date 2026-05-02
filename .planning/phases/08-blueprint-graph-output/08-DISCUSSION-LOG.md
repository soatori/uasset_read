# Phase 8: 蓝图图输出增强 - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-02
**Phase:** 08-blueprint-graph-output
**Areas discussed:** 连接映射构建, 执行流路径, CLI --graph 标志

---

## 连接映射构建

### 连接匹配策略

| Option | Description | Selected |
|--------|-------------|----------|
| PinName 全图匹配 | 在图中搜索所有节点的引脚，找到 PinName 匹配的引脚，返回其 PinId。简单但可能有同名引脚冲突。 | ✓ |
| 解析原始 PinId | LinkedTo 原始数据可能包含 PinId 格式，直接解析为 GUID hex。需要验证实际数据格式。 | |
| NodeGuid + PinName 组合 | LinkedTo 数据可能包含 NodeGuid + PinName 组合，先定位节点再定位引脚。更精确但解析复杂。 | |

**User's choice:** PinName 全图匹配（推荐）
**Notes:** 简单实现优先

### 连接表示格式

| Option | Description | Selected |
|--------|-------------|----------|
| PinId 对（PinId → TargetPinId） | 每个连接显示为 PinId GUID hex 对。简洁但需要额外查找才能理解。 | |
| NodeGuid + PinName 组合 | 每个连接显示为 NodeGuid + PinName 组合。可读性好，可直接定位。 | ✓ |
| 同时输出两种格式 | 每种格式各有利弊，完整输出包含两者。 | |

**User's choice:** NodeGuid + PinName 组合
**Notes:** 可读性优于紧凑性

### 连接映射位置

| Option | Description | Selected |
|--------|-------------|----------|
| 引脚层级（Pin.linked_to） | 每个引脚的 linked_to 字段包含连接列表。查询引脚时直接看到连接，但遍历图时需要检查每个引脚。 | |
| 图层级（Graph.connections） | 每个图对象包含 connections 数组，元素为 {from_pin, to_pin}。便于统计连接数，但需要交叉引用。 | ✓ |
| 两者都包含 | 两者都有：Pin.linked_to 包含连接，Graph.connections 包含汇总。冗余但方便两种查询方式。 | |

**User's choice:** 图层级（Graph.connections）
**Notes:** 便于统计连接数和遍历图

### 连接匹配失败处理

| Option | Description | Selected |
|--------|-------------|----------|
| 输出警告 + 原始数据（推荐） | 未匹配的引脚输出 warning 字段，包含原始 LinkedTo 数据。保留信息供调试。 | ✓ |
| 静默跳过 | 未匹配的连接静默跳过，不输出。避免输出混乱，但丢失信息。 | |
| 记录到 graphs.errors | 匹配失败时记录到 graphs.errors 数组。与顶层 errors 字段一致。 | |

**User's choice:** 输出警告 + 原始数据（推荐）
**Notes:** 保留信息供调试

### 双向连接表示

| Option | Description | Selected |
|--------|-------------|----------|
| 单向表示（Output → Input）（推荐） | 每个连接在 Graph.connections 中仅出现一次（Output Pin → Input Pin 方向）。避免重复，符合执行流语义。 | ✓ |
| 双向表示 | 每个连接出现两次（A→B 和 B→A）。便于从任何引脚查找连接，但输出冗余。 | |

**User's choice:** 单向表示（Output → Input）（推荐）
**Notes:** 避免重复，符合执行流语义

### 连接元素格式

| Option | Description | Selected |
|--------|-------------|----------|
| {from, to} 对象结构（推荐） | 每个连接为 {from: {node_guid, pin_name}, to: {node_guid, pin_name}}。结构清晰，便于 JSON 处理。 | ✓ |
| [node, pin, node, pin] 数组 | 每个连接为 [from_node, from_pin, to_node, to_pin] 数组。紧凑但需要按位置解析。 | |
| 字符串格式 | 每个连接为字符串 "node_guid.pin_name → node_guid.pin_name"。可读性好但不便于程序处理。 | |

**User's choice:** {from, to} 对象结构（推荐）
**Notes:** 结构清晰，便于 JSON 处理

---

## 执行流路径

### 执行流定义范围

| Option | Description | Selected |
|--------|-------------|----------|
| Event → CallFunction 链路（推荐） | 从 Event 节点（K2Node_Event）开始，沿连接追踪到 CallFunction 节点，记录路径上的节点序列。用于理解蓝图逻辑。 | ✓ |
| 完整控制流图 | 考虑所有控制流节点（If、Switch、Loop）分支，构建完整的控制流图。复杂但更完整。 | |
| 不构建执行流 | 不构建执行流，仅输出节点和连接数据。下游 AI agent 自己分析。 | |

**User's choice:** Event → CallFunction 链路（推荐）
**Notes:** 满足 GRAPH-12 需求

### 执行流路径表示

| Option | Description | Selected |
|--------|-------------|----------|
| 节点 GUID 序列 | 每条执行流为节点 GUID 序列 [node_guid_1, node_guid_2, ...]。紧凑，便于追踪。 | |
| 节点详细信息序列（推荐） | 每条执行流为节点对象序列 [{node_guid, node_type, function_name}, ...]。信息丰富但输出较大。 | ✓ |
| 仅首尾节点 | 仅输出起始 Event 和终止 CallFunction，不记录中间节点。最简单，用于概览。 | |

**User's choice:** 节点详细信息序列（推荐）
**Notes:** 信息丰富，便于理解执行流

### 多 Event 节点处理

| Option | Description | Selected |
|--------|-------------|----------|
| execution_flows 数组（推荐） | 每个 Event 节点生成一条执行流路径，放在 execution_flows 数组。便于查看每个事件的处理逻辑。 | ✓ |
| 合并为连通图 | 所有执行流合并成一个连通图，使用 edges 表示执行流边。更接近图结构。 | |
| 节点级后续列表 | 不按 Event 分组，每个节点单独列出其执行后续节点。需要更多后续处理。 | |

**User's choice:** execution_flows 数组（推荐）
**Notes:** 每个 Event 一条执行流

### 控制流节点处理

| Option | Description | Selected |
|--------|-------------|----------|
| 在分支处停止（推荐） | 在分支节点处停止追踪，execution_flow 记录到分支节点为止。AI agent 可自行分析分支逻辑。 | ✓ |
| 追踪所有分支 | 追踪所有分支，execution_flow 包含分支信息 {branch_type, branches: [...]}.。完整但输出复杂。 | |
| 仅追踪主分支 | 选择一个主要分支（如 If 的 True 分支）继续追踪。简化但可能丢失逻辑。 | |

**User's choice:** 在分支处停止（推荐）
**Notes:** 简化实现，AI agent 可自行分析分支逻辑

### 循环检测

| Option | Description | Selected |
|--------|-------------|----------|
| 检测并停止（推荐） | 追踪时检测已访问节点，遇到循环时停止并标记。避免无限循环。 | ✓ |
| 限制深度 | 允许循环路径输出，但限制最大深度（如 5 层）。 | |
| 不检测 | 不检测循环，假设蓝图无循环问题。简单但有风险。 | |

**User's choice:** 检测并停止（推荐）
**Notes:** 避免无限循环

---

## CLI --graph 标志

### --graph 与现有标志关系

| Option | Description | Selected |
|--------|-------------|----------|
| 独立标志（可组合） | --graph 独立输出蓝图图数据（graphs 字段），不与 --json/--text 互斥。用户可组合使用：--json --graph 输出完整 JSON + 图数据。 | ✓ |
| 互斥标志（仅输出图） | --graph 与 --json/--text/--summary 互斥，仅输出 graphs 字段。简化使用，但输出受限。 | |
| --json 的修饰符 | --graph 是 --json 的修饰符，仅在使用 --json 时生效，输出 graphs 字段代替完整 JSON。 | |

**User's choice:** 独立标志（可组合）
**Notes:** 用户可组合使用

### --graph 输出范围

| Option | Description | Selected |
|--------|-------------|----------|
| 仅 graphs 字段 | 仅输出 graphs 字段（图数据），省略其他字段（summary、exports 等）。便于专注查看蓝图逻辑。 | |
| 完整结构 + graphs | 输出完整结构 + graphs 字段。保留所有数据，但输出较大。 | |
| 取决于 --verbose | 默认仅 graphs，但与 --verbose 组合时输出完整结构 + graphs。 | ✓ |

**User's choice:** 取决于 --verbose
**Notes:** 默认专注图数据，--verbose 提供完整上下文

---

## Claude's Discretion

- Graph 对象的具体字段列表（graph_name, graph_class, nodes, connections, execution_flows 的完整结构）
- 文本输出图结构摘要的具体格式（节点数、连接数、执行流概览的 YAML 风格）
- 连接映射的验证机制（同名引脚冲突处理）
- 执行流节点详细信息的具体字段（node_guid, node_type, function_name之外是否包含更多）
- 单元测试组织

## Deferred Ideas

推迟到后续阶段：
- OUT2-02 高级属性解析结果输出（需先实现 Phase 9 的属性解析）
- 完整控制流图（考虑所有控制流节点分支）
- 连接验证机制（同名引脚冲突处理）
- 更多节点类型的执行流追踪
- 图可视化输出（SVG/DOT 格式）

---

*Discussion completed: 2026-05-02*