---
status: testing
phase: 52-struct-offset-alignment
source: 52-01-SUMMARY.md, 52-02-PLAN.md
started: "2026-05-17T03:45:00.000Z"
updated: "2026-05-17T03:45:00.000Z"
---

## Current Test

[testing complete]

## Tests

### 1. START_EVENT_TYPES 包含 K2Node_FunctionEntry
expected: |
  - "K2Node_FunctionEntry" in START_EVENT_TYPES 返回 True
  - len(START_EVENT_TYPES) == 5（原有4种 + 新增1种）
  - 原有4种类型（K2Node_Event, K2Node_EnhancedInputAction, K2Node_VariableSet, K2Node_CustomEvent）仍在集合中
result: pass

### 2. _get_start_event_name 提取 FunctionEntry 函数名
expected: |
  - K2Node_FunctionEntry 节点的 _get_start_event_name 返回 function_reference.member_name（如 'Move'、'Aim'）
  - node_data=None 时 fallback 到 class_name（"K2Node_FunctionEntry"）
  - function_reference.member_name 为 "None" 时 fallback 到 class_name
result: pass

### 3. is_function_graph 正确区分图类型
expected: |
  - 含 K2Node_FunctionEntry 的图（Move、Aim、UserConstructionScript）返回 True
  - 含 K2Node_Event 的图（EventGraph）返回 False
  - Fallback: graph_name="EventGraph" 的无特征图返回 False
result: pass

### 4. FunctionEntry 作为执行流起点
expected: |
  - Move 图的 execution_flows 中 start_event = "Move"
  - Aim 图的 execution_flows 中 start_event = "Aim"
  - UserConstructionScript 图的 execution_flows 中 start_event = "UserConstructionScript"
  - EventGraph 的执行流输出与修改前完全一致（无回归）
result: pass

### 5. format_node_dict 输出 function_entry_reference
expected: |
  - K2Node_FunctionEntry 节点的 format_node_dict 输出 `function_entry_reference` 字段
  - 包含 member_name、member_parent、self_context（或 None）
  - 不与 CallFunction 的 `function_reference` 冲突
result: pass

### 6. BP_FirstPersonCharacter 整体验证
expected: |
  - FunctionEntry 节点：3个（Aim、Move、UserConstructionScript图各1个）
  - is_function_graph：Aim=True, Move=True, UserConstructionScript=True, EventGraph=False
  - execution_flows start_event：Aim="Aim", Move="Move", UserConstructionScript="UserConstructionScript"
  - EventGraph 向后兼容：4个 K2Node_Event 执行流输出不变
result: pass

## Summary

total: 6
passed: 6
issues: 0
pending: 0
skipped: 0
blocked: 0

## Gaps

<!-- YAML format for plan-phase --gaps consumption -->
[none yet]
