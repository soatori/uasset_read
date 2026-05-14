# Phase 19: 连接关系重建 - Context

**Gathered:** 2026-05-04
**Status:** Ready for planning

<domain>
## Phase Boundary

构建节点间连接图，输出清晰的执行流和数据流结构。Phase 19专注于connections数组构建、execution_flows扩展（新增起点类型）、data_flows新增实现、控制流分支标记。

**Requirements:** LINK-01~03 (节点连接映射、执行流图、数据流图)

**范围锚点：** 仅构建连接关系输出，不添加新的节点解析逻辑或蓝图功能扩展。

</domain>

<decisions>
## Implementation Decisions

### 连接引用格式
- **D-19-01:** Node引用保留node_guid格式 — 稳定可靠，现有代码已实现
- **D-19-02:** Pin引用使用pin_name格式 — 用户友好，需统一修改Phase 18输出
- **D-19-03:** 连接输出格式全局可选配置 — 支持guid模式和name模式切换
- **D-19-04:** 默认输出模式为name模式 — 符合REQUIREMENTS示例格式
- **D-19-05:** 查找失败时保留原始pin_id作为fallback — 便于调试，附带warning字段

### 数据流定义
- **D-19-06:** 数据流包含所有非exec pins — pin_type.category != "exec"的pins构成数据流
- **D-19-07:** data_flows输出结构为 `{source, target}` — 符合REQUIREMENTS LINK-03示例
- **D-19-08:** data_flows组织为扁平列表 — 每条数据流独立记录
- **D-19-09:** 数据流与执行流独立分离 — 不标记关联关系，各自分析

### 执行流起点类型
- **D-19-10:** 执行流起点类型扩展 — K2Node_Event、K2Node_EnhancedInputAction、K2Node_VariableSet、K2Node_CustomEvent
- **D-19-11:** 起点标识统一使用start_event字段 — 所有起点类型统一处理
- **D-19-12:** EnhancedInputAction各触发时机分别追踪 — Started/Triggered/Completed独立执行链路

### 控制流分支处理
- **D-19-13:** 控制流节点标记停止 — Branch/Switch等不继续追踪分支路径
- **D-19-14:** 控制流节点输出branch_type字段 — if_then_else/switch/switch_enum/switch_string/switch_integer/macro_instance
- **D-19-15:** 循环检测标记停止 — 检测到已访问节点时停止，标记cycle_detected=true

### Claude's Discretion
- branch_type字段的具体枚举值
- cycle_detected字段的输出位置（节点层级或执行流层级）
- name模式下节点名冲突的处理策略

</decisions>

<specifics>
## Specific Ideas

**REQUIREMENTS示例格式：**
```json
{
  "connections": [
    {"from": {"node": "K2Node_EnhancedInputAction_5", "pin": "Started"},
     "to": {"node": "K2Node_CallFunction_1193", "pin": "execute"}}
  ],
  "execution_flows": [
    {"entry": "K2Node_EnhancedInputAction_5",
     "chain": ["K2Node_CallFunction_1193", "K2Node_CallFunction_9386"]}
  ],
  "data_flows": [
    {"source": {"node": "K2Node_EnhancedInputAction_3", "pin": "ActionValue_X"},
     "target": {"node": "K2Node_CallFunction_5", "pin": "Left / Right"}}
  ]
}
```

**测试资产验证：**
- BP_FirstPersonCharacter.uasset (UE 5.7)
- 验证Jump执行流程：IA_Jump → Jump → StopJumping
- 验证数据流：ActionValue_X/Y → Left/Right/Forward/Backward参数

</specifics>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### UE 5.7 源码参考（只读）
- `E:\Develop\lib\UnrealEngine\Engine\Source\Runtime\Engine\Private\EdGraph\EdGraphPin.cpp` — Pin序列化核心（第1838-1964行）
- `E:\Develop\lib\UnrealEngine\Engine\Source\Runtime\BlueprintGraph\Private\K2Node_EnhancedInputAction.cpp` — EnhancedInputAction节点结构

### 项目研究文档
- `.planning/REQUIREMENTS.md` — v4.0需求定义（LINK-01~03规范，输出设计原则）
- `.planning/ROADMAP.md` — Phase 19目标和Success Criteria（第96-105行）

### Prior Phase Context
- `.planning/phases/18-Pin序列化解析/18-CONTEXT.md` — Phase 18 Pin解析修正、LinkedTo格式

</canonical_refs>

<code_context>
## Existing Code Insights

### 需修改的位置
1. **`build_connections_map()` (第4990-5039行)** — 添加可选name模式，修改pin引用格式
2. **`build_execution_flows()` (第5180-5225行)** — 扩展起点类型（EnhancedInputAction、VariableSet、CustomEvent）
3. **新增 `build_data_flows()`** — 构建非exec pin数据流
4. **Phase 18输出格式** — 统一修改linked_to输出为pin_name格式

### 已实现可复用
- `CONTROL_FLOW_NODES` frozenset (第4980-4987行) — 控制流节点类型列表
- `_trace_execution_from_event()` (第5228行) — 执行流追踪逻辑
- pin_lookup/node_lookup查找表构建模式 — 可复用于data_flows

### Integration Points
- 连接映射入口：`format_graphs_json()` 调用 `build_connections_map()`
- 执行流入口：`format_graphs_json()` 调用 `build_execution_flows()`
- 数据流入口：`format_graphs_json()` 新增调用 `build_data_flows()`

</code_context>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope. Phase 20将处理整合输出，Phase 21验证测试。

</deferred>

---

*Phase: 19-连接关系重建*
*Context gathered: 2026-05-04*