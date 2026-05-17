# Phase 54: 数据流追踪 - Context

**Gathered:** 2026-05-17
**Status:** Ready for planning

<domain>
## Phase Boundary

在 Phase 53 识别执行流和 Pure 函数的基础上，构建双向数据流追踪能力：
- 正向追踪（data_providers）：从 Pure 函数输出 pin 追踪到所有使用点
- 反向追踪（data_sources）：从 CallFunction 输入 pin 向回追踪数据来源链

满足 DATA-01（Pure 函数返回值 → 参数输入）、DATA-02（Knot 中继处理）、DATA-03（SubPin 字段级数据流）需求。

不跨图追踪，不递归展开嵌套结构体（仅第一级 SubPin）。
</domain>

<decisions>
## Implementation Decisions

### 追踪方向策略
- **D-01:** 双向追踪分开输出。正向追踪（data_providers）用于分析 Pure 函数输出去向；反向追踪（data_sources）用于分析调用参数来源。两种视角独立但互补。
- **D-02:** Knot 节点透明穿透，不作为独立节点出现在数据链中。遵循 Phase 52 D-02 决策，数据流直接穿透到下一个有意义的节点。
- **D-03:** 追踪在图边界停止。不跨图追踪数据流（无法找到跨图引用，且可能产生无限递归）。

### 输出结构设计
- **D-04:** 新增两个顶层数组 `data_sources` 和 `data_providers`，与现有 `data_flows` 并存。`data_flows` 记录直接连接关系，新数组记录来源链路。
- **D-05:** 数据链路用数组格式表示 `[{node, pin, type}, ...]`，便于序列化和程序处理。
- **D-06:** 链路节点包含扩展信息：`node_name`、`pin_name`、`node_type`、`pin_type`（可选）。便于区分 Pure vs Impure 函数和不同数据类型。

### SubPin 处理策略
- **D-07:** SubPin 展开为字段级追踪，满足 DATA-03 需求。记录「结构体.X 字段 → 目标.Y 字段」的细粒度数据流。
- **D-08:** SubPin 在链路中用嵌套结构表示 `{parent_pin, subfield}`，而非点分隔字符串。结构更清晰，便于程序解析。
- **D-09:** 仅展开第一级 SubPin，不递归展开嵌套结构体。避免过度复杂化输出，满足大多数 C++ 翻译场景。

### 追踪范围界定
- **D-10:** 仅追踪非 exec 类型 pin（包括 bool、int、float、string、struct、object、delegate 等）。符合 Phase 53 D-03 定义。
- **D-11:** 正向追踪（data_providers）仅从标记为 Pure 的 CallFunction 输出 pin 开始。Phase 53 D-03 已识别 pure 函数（`pure: true` 标记）。
- **D-12:** 反向追踪（data_sources）仅从 CallFunction 输入 pin 开始，不包括 Event/VariableSet 等其他节点。聚焦于函数调用参数来源分析。

### Claude's Discretion
- 算法实现细节（正向/反向遍历逻辑）由 researcher 根据 UE 源码和现有模式确定
- 具体函数命名和模块划分由 planner 决定
- SubPin 检测逻辑（如何识别 parent_pin → subfield 关系）由 researcher 确定

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### 上游决策
- `.planning/phases/52-struct-offset-alignment/52-CONTEXT.md` — Phase 52 决策：Knot 穿透策略（D-02）
- `.planning/phases/53-function-execution-flow/53-CONTEXT.md` — Phase 53 决策：Pure 函数识别（D-03），执行流追踪模式
- `.planning/REQUIREMENTS.md` — v9.0 需求（DATA-01/02/03 映射到此 Phase）
- `.planning/ROADMAP.md` — v9.0 Phase 52-55 路线图

### 核心流构建模块
- `src/uasset_read/graph/flow_builder.py` — 执行流/数据流构建主模块
- `src/uasset_read/graph/flow_builder.py:build_data_flows()` — 现有数据流构建（L498-533），仅记录直接连接
- `src/uasset_read/graph/flow_builder.py:build_execution_flows()` — 执行流入口，已识别 pure 函数
- `src/uasset_read/graph/flow_builder.py:_trace_execution_from_event()` — 执行流追踪模式（可参考追踪逻辑）
- `src/uasset_read/graph/flow_builder.py:format_graphs_json()` — JSON 输出入口，需添加新数组

### 数据模型
- `src/uasset_read/models/node_types.py` — K2NodeCallFunction、K2NodeKnot 数据类定义
- `src/uasset_read/models/core.py` — UEdGraph/UEdGraphNode/UEdGraphPin 基类，FEdGraphPinType

### 常量配置
- `src/uasset_read/constants.py` — PIN_CATEGORY 类型定义

### 参考
- `reference/蓝图节点文本参考.md` — BP_FirstPersonCharacter 蓝图节点文本参考
- No external specs — requirements fully captured in decisions above

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `build_data_flows()` — 已有 pin_lookup/node_name_lookup 构建，可直接复用
- `_trace_execution_from_event()` — 追踪遍历模式（visited set、while loop），可参考设计数据流追踪
- `format_pin_ref()` — Pin 引用格式化函数，已有 `{node, pin}` 输出模式
- `_find_next_exec_node()` — 查找连接节点的逻辑（linked_to_raw → target_pin_guid → node）

### Established Patterns
- 追踪遍历模式: visited set 防止循环 + while/for loop 追踪连接
- Pin 引用格式: `{node, pin}` 或 `{node_guid, pin_name}` 模式
- Knot 穿透: Phase 52 D-02 决定不产生独立节点，执行流/数据流直接穿透

### Integration Points
- `format_graphs_json()` (flow_builder.py) — JSON 输出入口，需添加 `data_sources` + `data_providers` 数组
- `build_execution_flows()` (flow_builder.py) — Phase 53 已标记 pure 函数，可复用识别逻辑
- `K2NodeCallFunction.parameters` (Phase 49) — CallFunction 节点已有 parameters 字段，反向追踪可关联

</code_context>

<specifics>
## Specific Ideas

- data_sources 数组示例：从 Move 函数的 Direction 参数向回追踪 → `GetActorForwardVector().ReturnValue`
- data_providers 数组示例：从 `GetActorForwardVector().ReturnValue` 正向追踪 → 使用于 Move.Direction、Add.VectorA 等
- SubPin 示例：`BreakVector` 节点将 Vector 拆分为 X/Y/Z，SubPin 展开记录字段级传递
- 正向追踪可用于分析「一个 Pure 函数的输出被哪些节点使用」，便于 C++ 翻译器理解数据依赖
- 反向追踪更直接对应 C++ 翻译需求：「函数参数值从哪来」

</specifics>

<deferred>
## Deferred Ideas

- 跨图数据流追踪（函数调用跨 UberEdGraph） — 不在 v9.0 范围内，可能需要 Phase 55 或后续 milestone
- 嵌套结构体全递归展开（第二级 SubPin） — 如有需求可后续扩展
- JSON function_graphs 独立数组输出 — Phase 55
- 局部变量追踪 — v2 scope，不在 v9.0 范围内
- 控制流节点详细展开 — v2 scope，不在 v9.0 范围内

None — discussion stayed within phase scope

</deferred>

---

*Phase: 54-数据流追踪*
*Context gathered: 2026-05-17*