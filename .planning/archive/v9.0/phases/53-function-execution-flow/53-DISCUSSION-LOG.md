# Phase 53: 函数内执行流追踪 - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-17
**Phase:** 53-函数内执行流追踪
**Areas discussed:** FunctionEntry输出组织, CallFunction处理, Pure函数处理, Knot节点

---

## FunctionEntry输出组织

| Option | Description | Selected |
|--------|-------------|----------|
| 复用现有 output | 复用 build_execution_flows() 输出结构，FunctionEntry 自动作为起点纳入 | ✓ |
| 独立数组 | 新增 function_graphs[].execution_flows 独立数组 | |

**User's choice:** "不考虑兼容，你来决定，目标3"（目标3 = C++ 可翻译性）
**Notes:** 用户明确表示不考虑向后兼容，以 C++ 可翻译性为目标。推荐复用现有结构，因为 (1) FunctionEntry 已在 START_EVENT_TYPES 中 (2) _trace_execution_from_event 已有处理逻辑 (3) 翻译器按 start_event 前缀区分 Event vs Function 即可。

## CallFunction处理

| Option | Description | Selected |
|--------|-------------|----------|
| 标记 CallFunction 类型 | 区分外部函数 vs 本图函数，标记引用 | ✓ |
| 跨图展开 | 递归展开同 uasset 中的被调用函数 | |
| 仅记录引用 | 只记录 {function_name, params}，不展开 | |

**User's choice:** "仅记录引用 (推荐)"
**Notes:** C++ 翻译中函数调用就是引用而非内联展开。被调用函数可能在不同蓝图/C++ 中，无法展开。完整调用链分析留给 Phase 54+ 数据流追踪。

## Pure函数处理

| Option | Description | Selected |
|--------|-------------|----------|
| 跳过 Pure 函数 | Pure 函数无 exec pin，执行流自然跳过 | |
| 标记 Pure 函数节点 | 在执行流中记录但标记 pure=true | ✓ |
| You decide | 由 Claude 决定 | |

**User's choice:** "You decide" → 选择"标记 Pure 函数节点"
**Notes:** 执行流中仍然记录 Pure 函数节点，但标记为 pure=true，表明它是数据驱动而非执行驱动。这样 C++ 翻译器能看到完整的节点序列，但知道 Pure 函数是作为表达式/内联调用而非语句。

## Knot节点

| Option | Description | Selected |
|--------|-------------|----------|
| 透明穿透 | Phase 52 D-02 已决定：Knot 不产生独立记录 | ✓ |
| 保留为节点 | Knot 在执行流中保留为独立节点 | |

**User's choice:** "透明穿透 (已决定)"
**Notes:** 沿用 Phase 52 CONTEXT.md D-02 决定。Knot 在 C++ 翻译中无对应概念。

---

## Claude's Discretion

- `_trace_execution_from_event` 中对 FunctionEntry 的 `_get_start_event_name` 实现细节
- CallFunction 类型标记的具体字段结构（如 `is_blueprint_callable`, `target_graph` 等）

## Deferred Ideas

- Pure 函数的数据流追踪（返回值 → 参数输入） — Phase 54
- 跨图函数调用展开（递归展开被调用函数的 execution_flow） — 不在 v9.0 范围内
- JSON function_graphs 独立数组输出 — Phase 55
- 局部变量追踪 — v2 scope
- 控制流节点详细展开 — v2 scope
