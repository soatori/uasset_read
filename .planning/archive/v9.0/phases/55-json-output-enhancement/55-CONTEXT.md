# Phase 55: JSON 输出增强 - Context

**Gathered:** 2026-05-17
**Status:** Ready for planning

<domain>
## Phase Boundary

在 Phase 53（函数内执行流追踪）和 Phase 54（数据流追踪）的基础上，
将函数图数据组织成顶层 `function_graphs` 数组，使 JSON 输出可直接翻译为
等价 C++ 函数实现。每个 FunctionEntry 对应一个 function_graph 条目，
包含执行流链路和数据流标注。
</domain>

<decisions>
## Implementation Decisions

### 输出结构
- **D-01:** `function_graphs` 作为顶层数组（与 `graphs_summary` 同级），不嵌套在 `blueprint` 内部。下游 C++ 翻译器可直接读取，保持顶层一致性。

### 函数粒度
- **D-02:** 每个 FunctionEntry 节点对应一个 `function_graph` 条目（函数级拆分），与 C++ 函数一对一映射。与 Phase 53 的 `build_execution_flows()` 行为一致。

### 数据流集成
- **D-03:** 数据流以内嵌标注方式集成 — 每个执行流节点对象增加 `data_providers` 和 `data_sources` 字段，标注该节点的数据依赖和产出。执行流和数据流在同一层级，C++ 翻译时可直接看到节点的数据上下文。

### 版本兼容
- **D-04:** `output_version` 从 "4.0" 升级到 "5.0"，视为 breaking change。提供配置开关控制是否输出 `function_graphs` 数组（默认关闭，向后兼容）。

### Claude's Discretion
- `function_graphs` 数组中每个条目的具体字段结构（如 `function_name`, `signature`, `parameters` 等）由 planner 根据 Phase 52-54 的数据模型确定
- 配置开关的具体实现方式（CLI flag / config file / environment variable）由 planner 根据现有 CLI 架构确定
- Phase 54 的 data_providers/data_sources 数据如何与 Phase 53 的执行流节点关联（通过节点 GUID / 节点名称 / 执行流索引）由 researcher 根据实际数据结构确定

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### 核心输出模块
- `src/uasset_read/formatters/json_formatter.py` — JSON 格式化主模块（format_json_full, format_json_summary）
- `src/uasset_read/formatters/json_formatter.py:format_json_full()` — L23-84，当前顶层输出结构（status, output_version, summary, exports, blueprint, graphs_summary, errors）
- `src/uasset_read/formatters/helpers.py` — build_status_info, build_schema_info 辅助函数

### 图流构建模块
- `src/uasset_read/graph/flow_builder.py` — 执行流/数据流/连接映射构建主模块
- `src/uasset_read/graph/flow_builder.py:build_graphs_summary()` — L536-574，当前 graphs_summary 结构
- `src/uasset_read/graph/flow_builder.py:build_execution_flows()` — L456+，执行流构建（已支持 FunctionEntry 起点）
- `src/uasset_read/graph/flow_builder.py:build_data_flows()` — L498+，数据流构建（Phase 54 实现）
- `src/uasset_read/graph/flow_builder.py:format_graphs_json()` — L577+，graph 完整 JSON 格式化

### 数据模型
- `src/uasset_read/models/node_types.py` — K2Node 数据类（K2NodeCallFunction, K2NodeFunctionEntry）
- `src/uasset_read/models/core.py` — UEdGraph/UEdGraphNode/UEdGraphPin 基类

### 上游决策
- `.planning/phases/53-function-execution-flow/53-CONTEXT.md` — Phase 53 决策：execution_flow 按 FunctionEntry 拆分，D-01 明确排除独立 function_graphs 数组留给 Phase 55
- `.planning/phases/54-data-flow-tracking/54-CONTEXT.md` — Phase 54 决策：双向追踪（data_providers + data_sources），Knot 透明穿透
- `.planning/phases/52-struct-offset-alignment/52-CONTEXT.md` — Phase 52 决策：FunctionEntry 识别策略、Knot 穿透

### 需求追溯
- `.planning/REQUIREMENTS.md` — OUT-01: JSON 输出中包含 function_graphs 数组
- `.planning/ROADMAP.md` — v9.0 Phase 52-55 路线图

### 参考
- `reference/蓝图节点文本参考.md` — BP_FirstPersonCharacter 蓝图节点文本参考

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `build_execution_flows()` — 已按 FunctionEntry 拆分 execution_flow，可直接复用为 function_graph 的执行流基础
- `build_data_flows()` — Phase 54 实现的双向追踪数据，需要与执行流节点关联
- `build_graphs_summary()` — 现有图摘要结构，function_graphs 可参考其字段组织
- `format_json_full()` — 顶层输出构建入口，function_graphs 在此函数中添加

### Established Patterns
- 版本管理: output_version 字段标识输出结构版本（当前 "4.0"）
- 分层输出: graphs（详细）和 graphs_summary（摘要）双层模式
- 配置开关: CLI 通过 argparse flags 控制输出选项（include_schema 等）

### Integration Points
- `format_json_full()` (json_formatter.py) — 在此函数中添加 function_graphs 顶层数组
- `build_execution_flows()` (flow_builder.py) — 需要增强以支持数据流内嵌标注
- `cli.py` — 添加 --include-function-graphs 或类似 flag

</code_context>

<specifics>
## Specific Ideas

- function_graphs 条目结构建议：
  ```json
  {
    "function_name": "Move",
    "start_event": "FunctionEntry.Move",
    "signature": { "return_type": "void", "parameters": [...] },
    "execution_flows": [
      {
        "nodes": [
          {
            "node_name": "CallFunction.K2_GetActorLocation",
            "data_providers": [...],
            "data_sources": [...]
          }
        ]
      }
    ]
  }
  ```
- output_version 升级时需在 changelog/文档中说明 breaking changes

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 55-JSON 输出增强*
*Context gathered: 2026-05-17*
