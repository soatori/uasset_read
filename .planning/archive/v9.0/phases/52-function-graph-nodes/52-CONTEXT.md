# Phase 52: 函数图节点解析 - Context

**Gathered:** 2026-05-17
**Status:** Ready for planning

<domain>
## Phase Boundary

从蓝图函数图中识别和解析 FunctionEntry 节点，区分 EventGraph 和 Function Graph，
使解析器能提取函数级别的图结构，为后续执行流追踪提供基础。

不修改 EventGraph 输出格式（向后兼容）。
</domain>

<decisions>
## Implementation Decisions

### 函数图区分策略
- **D-01:** 使用组合判断区分 EventGraph 和 Function Graph：graph_class 为主（UberEdGraph 通常是函数图容器），辅以 graph_name 模式和图中是否存在 K2Node_FunctionEntry 节点。三者组合判断，避免单一条件误判。

### Knot 节点处理
- **D-02:** Knot 节点在函数调用链中采用透明穿透策略 — 不产生独立节点记录，数据流和执流直接穿透到下一个有意义的节点。目标是将 JSON 输出翻译为等价的 C++ 函数实现，Knot 作为 UE 编辑器内部的中继概念不需要映射到 C++。

### 执行流整合
- **D-03:** 复用现有 build_execution_flows() 函数处理函数图执行流追踪，将 K2Node_FunctionEntry 加入 START_EVENT_TYPES。最小改动方案，利用已有的 exec pin 追踪逻辑。

### Claude's Discretion
- FunctionEntry 节点的具体字段读取深度由 researcher 根据 UE 源码确定（至少包含 FunctionReference）
- graph_name 的命名模式判断逻辑由 planner 根据实际情况设计

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### 核心序列化
- `src/uasset_read/serializers/graph.py` — 图二进制序列化器，包含所有节点读取器和 create_node_from_archive 工厂
- `src/uasset_read/serializers/graph.py:read_ue_graph()` — UEdGraph 读取，当前图入口
- `src/uasset_read/serializers/graph.py:read_ue_graph_node()` — UEdGraphNode 读取，PropertyTag 解析
- `src/uasset_read/serializers/graph.py:create_node_from_archive()` — 节点工厂分派函数

### 数据模型
- `src/uasset_read/models/node_types.py` — K2Node 数据类定义
- `src/uasset_read/models/core.py` — UEdGraph/UEdGraphNode/UEdGraphPin 基类

### 流构建
- `src/uasset_read/graph/flow_builder.py` — 执行流/数据流构建
- `src/uasset_read/graph/flow_builder.py:build_execution_flows()` — 当前执行流入口
- `src/uasset_read/graph/flow_builder.py:build_graphs_summary()` — 图汇总输出

### 常量配置
- `src/uasset_read/constants.py` — START_EVENT_TYPES, GRAPH_TYPE_MAP, CONTROL_FLOW_NODES

### 需求追溯
- `.planning/REQUIREMENTS.md` — v9.0 需求（FUNC-01/02 映射到此 Phase）
- `.planning/ROADMAP.md` — v9.0 Phase 52-55 路线图

### 参考
- `reference/蓝图节点文本参考.md` — BP_FirstPersonCharacter 蓝图节点文本参考
- No external specs — requirements fully captured in decisions above

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `create_node_from_archive()` — 节点工厂分派模式，添加 K2Node_FunctionEntry 只需增加一个 elif 分支
- `read_ue_graph_node()` — 已有 FunctionReference/EventReference PropertyTag 解析，FunctionEntry 可复用
- `K2NodeKnot` dataclass — 已有 Knot 节点数据类，无需新增

### Established Patterns
- 节点解析模式: 每个 K2Node 类型有对应的 read_k2node_*() 函数 + dataclass + create_node_from_archive 分派
- 执行流追踪: START_EVENT_TYPES 定义了执行流起点集合，build_execution_flows() 遍历这些起点
- GRAPH_TYPE_MAP: EdGraph→"event", UberEdGraph→"uber"，需要扩展以区分 Function Graph

### Integration Points
- `extract_blueprint_graphs()` (parser.py) — 图提取入口，需要区分函数图/事件图
- `build_execution_flows()` (flow_builder.py) — 需要支持 FunctionEntry 作为起点
- `format_graphs_json()` (flow_builder.py) — JSON 输出入口，需要保持向后兼容

</code_context>

<specifics>
## Specific Ideas

- K2Node_FunctionEntry 的 FunctionReference 指向被定义的函数（如 "Move"），可从 node_data 中提取
- UberEdGraph 是 UE 中函数图的容器类型，通常包含多个 Function Graph
- Knot 节点在数据流中起中继作用，在 C++ 翻译中相当于变量赋值/传递，不需要显式表示

</specifics>

<deferred>
## Deferred Ideas

- Pure 函数的数据流追踪（DATA-01/02/03） — Phase 54
- JSON function_graphs 数组输出 — Phase 55
- 局部变量追踪 — v2 scope，不在 v9.0 范围内
- 控制流节点（Branch/DoOnce） — v2 scope，不在 v9.0 范围内

</deferred>

---

*Phase: 52-函数图节点解析*
*Context gathered: 2026-05-17*
