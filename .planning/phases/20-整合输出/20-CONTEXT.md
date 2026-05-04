# Phase 20: 整合输出 - Context

**Gathered:** 2026-05-04
**Status:** Ready for planning

<domain>
## Phase Boundary

输出完整的节点、Graph、蓝图JSON结构，遵循REQUIREMENTS OUT-01~03规范。Phase 20专注于字段名规范化、嵌套结构展开、蓝图层级重组、变量信息扩展，不添加新的解析能力。

**Requirements:** OUT-01~03 (节点完整结构、Graph完整结构、蓝图完整结构)

**范围锚点：** 仅规范化和重组现有输出结构，不修改解析逻辑或添加新解析功能。

</domain>

<decisions>
## Implementation Decisions

### 节点输出格式 (OUT-01)
- **D-20-01:** node_name派生策略 — class_name + index（使用现有 `_derive_node_name()` 函数），如 `K2Node_CallFunction_1193`
- **D-20-02:** 字段名规范化 — 仅新字段名，不保留旧字段名：
  - `class_name` → `node_type`
  - `node_pos_x/node_pos_y` → `position: {x, y}`
- **D-20-03:** 嵌套结构展开 — 仅常用字段：
  - `function_reference` 从 node_data 提升到节点顶层（CallFunction类型）
  - `event_reference` 从 node_data 提升到节点顶层（Event类型）
  - 其余 node_data 字段保持嵌套

### Graph输出格式 (OUT-02)
- **D-20-07:** graph_type语义化映射：
  - `EdGraph` → `event`
  - `UberEdGraph` → `uber`
- Graph结构保持现有字段：graph_name, nodes, connections, execution_flows, data_flows

### 蓝图输出格式 (OUT-03)
- **D-20-04:** 单一蓝图对象结构：
  ```json
  {
    "blueprint": {
      "blueprint_name": "...",
      "parent_class": "...",
      "graphs": [...],
      "variables": [...]
    }
  }
  ```
- graphs 从顶层移入 blueprint 对象内部
- **D-20-06:** variables扩展信息 — 输出变量名、变量类型、默认值（Phase 12数据扩展）

### 版本标识
- **D-20-05:** output_version升级到 `"4.0"` — 反映输出结构重大变化

### Claude's Discretion
- 节点 pins 输出的详细程度（是否包含所有 Phase 18 字段）
- 变量默认值的格式（字符串 vs 结构化）
- 多蓝图资产的处理策略

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### 项目规范文档
- `.planning/REQUIREMENTS.md` — v4.0需求定义（OUT-01~03规范，输出设计原则第186-193行）
- `.planning/ROADMAP.md` — Phase 20目标和Success Criteria（第112-120行）

### Prior Phase Context
- `.planning/phases/18-Pin序列化解析/18-CONTEXT.md` — Phase 18 Pin解析、LinkedTo格式
- `.planning/phases/19-连接关系重建/19-CONTEXT.md` — Phase 19 connections/execution_flows/data_flows构建

### UE 5.7 源码参考（只读）
- `E:\Develop\lib\UnrealEngine\Engine\Source\Runtime\Engine\Private\EdGraph\EdGraph.cpp` — Graph类型定义

</canonical_refs>

<code_context>
## Existing Code Insights

### 需修改的位置
1. **`format_json_full()` (第5639-5688行)** — 重组为单一蓝图对象结构，移除顶层 graphs
2. **`format_graphs_json()` (第5144-5193行)** — 添加字段名映射（graph_class→graph_type, class_name→node_type）
3. **节点输出 (第5175行)** — 使用 `_derive_node_name()` + position结构 + function_reference展开
4. **variables提取** — 扩展 Phase 12 blueprint.variables 输出格式

### 已实现可复用
- `_derive_node_name()` (第5018行) — node_name派生逻辑
- `blueprint.variables` (Phase 12) — 变量列表已解析
- `build_connections_map()` (Phase 19) — connections构建
- `build_execution_flows()` / `build_data_flows()` (Phase 19) — 流程图构建

### Integration Points
- JSON输出入口：`format_json_full()` 和 `format_json_summary()`
- CLI输出：`--full` 和 `--summary` 标志对应两种格式
- API导出：`__all__` 中 format_json_full/format_json_summary 需保持导出

</code_context>

<specifics>
## Specific Ideas

**REQUIREMENTS示例格式（OUT-01节点）：**
```json
{
  "node_name": "K2Node_CallFunction_1193",
  "node_type": "CallFunction",
  "node_guid": "F923268743B7B52D669FFB960CA79833",
  "position": {"x": 3136, "y": -1040},
  "function_reference": {
    "member_name": "Jump",
    "self_context": true
  },
  "pins": [
    {"pin_id": "...", "pin_name": "execute", "pin_type": {...}, "linked_to": [...]}
  ]
}
```

**REQUIREMENTS示例格式（OUT-03蓝图）：**
```json
{
  "blueprint": {
    "blueprint_name": "BP_FirstPersonCharacter",
    "parent_class": "FirstPersonCharacter",
    "graphs": [...],
    "variables": [...]
  }
}
```

**测试资产验证：**
- BP_FirstPersonCharacter.uasset (UE 5.7)
- 验证节点命名：K2Node_CallFunction_1193（Jump节点）
- 验证蓝图结构：blueprint_name、parent_class、graphs、variables完整性

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope. Phase 21将处理验证测试。

</deferred>

---

*Phase: 20-整合输出*
*Context gathered: 2026-05-04*