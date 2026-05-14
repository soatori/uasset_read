---
status: complete
phase: 20-整合输出
source: [20-01-SUMMARY.md, 20-02-SUMMARY.md]
started: "2026-05-04T18:15:00.000Z"
updated: "2026-05-04T18:20:00.000Z"
---

## Current Test

[testing complete]

## Tests

### 1. 节点输出包含 node_name 字段
expected: 解析蓝图资产后，JSON 输出中每个节点包含 node_name 字段，格式为 "K2Node_CallFunction_0"（class_name + idx）。
result: pass
verified: format_node_dict(node, 0) 输出 "K2Node_CallFunction_0"

### 2. 节点输出包含 node_type 字段
expected: JSON 输出中每个节点包含 node_type 字段（而非 class_name），值为节点类型名如 "K2Node_CallFunction"。
result: pass
verified: format_node_dict() 输出 node_type = class_name

### 3. 节点输出包含 position 结构
expected: JSON 输出中每个节点包含 position 结构 {"x": 100, "y": 200}（而非扁平的 node_pos_x/node_pos_y）。
result: pass
verified: format_node_dict() 输出 position: {'x': 100, 'y': 200}

### 4. CallFunction 节点包含顶层 function_reference
expected: CallFunction 类型节点的 JSON 输出包含顶层 function_reference 字段，含 member_name、member_parent、self_context。
result: pass
verified: function_reference: {'member_name': 'Jump', 'member_parent': '/Script/Engine.Character', 'self_context': True}

### 5. Graph 输出包含 graph_type 字段
expected: JSON 输出中每个 Graph 包含 graph_type 字段，值为 "event" 或 "uber"（而非 EdGraph/UberEdGraph）。
result: pass
verified: GRAPH_TYPE_MAP: {'EdGraph': 'event', 'UberEdGraph': 'uber'}, graph_type: 'event'

### 6. JSON 输出包含 blueprint 对象
expected: format_json_full() 输出包含单一 blueprint 对象（而非 blueprint_metadata），内含 blueprint_name、parent_class、variables、graphs。
result: pass
verified: blueprint keys: ['blueprint_name', 'parent_class', 'variables', 'detection_warning']

### 7. graphs 在 blueprint 对象内部
expected: graphs 数组在 blueprint 对象内部，顶层不再有独立的 graphs 字段。
result: pass
verified: top-level has graphs: False, blueprint has graphs: True

### 8. output_version 为 4.0
expected: JSON 输出的 output_version 字段值为 "4.0"（反映输出结构重大变化）。
result: pass
verified: output_version: '4.0'

## Summary

total: 8
passed: 8
issues: 0
pending: 0
skipped: 0

## Gaps

[none - all tests passed]