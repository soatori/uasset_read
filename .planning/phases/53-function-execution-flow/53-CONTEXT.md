# Phase 53: 函数内执行流追踪 - Context

**Gathered:** 2026-05-17
**Status:** Ready for planning

<domain>
## Phase Boundary

在 Phase 52 识别 FunctionEntry 节点的基础上，追踪函数图内部的执行流 ——
从 FunctionEntry 开始，沿 exec pin 连接到 CallFunction 链路，构建完整的函数内执行路径。

目标：使 JSON 输出可翻译为等价的 C++ 函数实现。每个函数对应一条独立的执行流，
包含函数内完整的控制流链路（不含数据流，数据流留给 Phase 54）。
</domain>

<decisions>
## Implementation Decisions

### 输出结构
- **D-01:** 复用现有 `build_execution_flows()` 输出结构。FunctionEntry 自动作为 START_EVENT_TYPES 起点被纳入，每个函数生成独立的 execution_flow 条目，以 `start_event` 字段区分（如 `"FunctionEntry.Move"` vs `"Event.ReceiveBeginPlay"`）。不引入新的顶层数组。

### CallFunction 处理
- **D-02:** CallFunction 在执行流中仅记录引用 —— `{function_name, params}`。不递归展开被调用函数的内部执行流。理由：(1) 被调用函数可能在不同蓝图或 C++ 中，无法展开 (2) 避免无限递归 (3) C++ 翻译天然就是函数调用语句而非内联展开。

### Pure 函数处理
- **D-03:** Pure 函数（无 exec pin）在执行流追踪中跳过，不纳入 execution_flow 序列。它们是数据驱动的，留给 Phase 54 数据流追踪处理。执行流只追踪有 exec pin 的节点。

### Knot 节点处理
- **D-04:** 沿用 Phase 52 CONTEXT.md D-02 决定：Knot 节点透明穿透，不产生独立节点记录。执行流直接穿透到下一个有意义的节点。

### Claude's Discretion
- `_trace_execution_from_event` 中对 FunctionEntry 的 `_get_start_event_name` 实现细节由 planner 根据 Phase 52 的数据模型确定
- CallFunction 类型标记的具体字段结构（如 `is_blueprint_callable`, `target_graph` 等）由 researcher 根据 UE 源码确定

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### 核心流构建
- `src/uasset_read/graph/flow_builder.py` — 执行流/数据流构建主模块
- `src/uasset_read/graph/flow_builder.py:build_execution_flows()` — 执行流入口（L448），已支持 FunctionEntry 作为起点
- `src/uasset_read/graph/flow_builder.py:_trace_execution_from_event()` — 单条执行流追踪（L290），L356-361 已有 FunctionEntry 处理
- `src/uasset_read/graph/flow_builder.py:_find_next_exec_node()` — 查找下一个 exec 连接节点（L264-287）

### 常量配置
- `src/uasset_read/constants.py` — START_EVENT_TYPES（L147-153），已包含 K2Node_FunctionEntry

### 数据模型
- `src/uasset_read/models/node_types.py` — K2Node 数据类定义（含 K2NodeCallFunction、K2NodeFunctionEntry）
- `src/uasset_read/models/core.py` — UEdGraph/UEdGraphNode/UEdGraphPin 基类

### 上游决策
- `.planning/phases/52-struct-offset-alignment/52-CONTEXT.md` — Phase 52 决策：FunctionEntry 识别策略、Knot 穿透（D-02）
- `.planning/ROADMAP.md` — v9.0 Phase 52-55 路线图

### 参考
- `reference/蓝图节点文本参考.md` — BP_FirstPersonCharacter 蓝图节点文本参考
- No external specs — requirements fully captured in decisions above

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `build_execution_flows()` — 已支持 FunctionEntry 作为起点（L468 的 START_EVENT_TYPES 过滤），无需修改入口逻辑
- `_trace_execution_from_event()` — 已有 FunctionEntry 节点处理（L356-361），提取 function_name
- `_find_next_exec_node()` — 通用 exec pin 后继查找，函数图和事件图共用
- `START_EVENT_TYPES` — 已包含 K2Node_FunctionEntry（Phase 52 已添加）

### Established Patterns
- 节点解析模式: 每个 K2Node 类型有对应的 dataclass + node_data 解析
- 执行流追踪: 沿 exec output pin → linked_to_raw → 目标节点循环
- CONTROL_FLOW_NODES: Branch/Sequence 等控制流节点会终止执行流追踪

### Integration Points
- `extract_blueprint_graphs()` (parsers/parser.py) — 图提取入口
- `build_execution_flows()` (flow_builder.py) — 函数图执行流复用此函数
- `format_graphs_json()` (flow_builder.py) — JSON 输出格式，需确保 start_event 字段能区分 Event vs FunctionEntry

</code_context>

<specifics>
## Specific Ideas

- start_event 命名建议：`"FunctionEntry.{function_name}"` 格式，便于 C++ 翻译器按前缀区分事件 vs 函数
- CallFunction 的 params 列表应区分输入/输出参数方向（direction 0=input, 1=output）
- 如果被调函数在同一 UberEdGraph 中，可通过 function_reference.member_name 查找对应 FunctionEntry，但 Phase 53 不展开

</specifics>

<deferred>
## Deferred Ideas

- Pure 函数的数据流追踪（返回值 → 参数输入） — Phase 54
- 跨图函数调用展开（递归展开被调用函数的 execution_flow） — 不在 v9.0 范围内
- JSON function_graphs 独立数组输出 — Phase 55
- 局部变量追踪 — v2 scope，不在 v9.0 范围内
- 控制流节点（Branch/DoOnce）详细展开 — v2 scope，不在 v9.0 范围内

</deferred>

---

*Phase: 53-函数内执行流追踪*
*Context gathered: 2026-05-17*
