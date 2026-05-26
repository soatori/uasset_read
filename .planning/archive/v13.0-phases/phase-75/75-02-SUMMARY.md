---
gsd_state_version: 1.0
phase: 75
plan: 02
subsystem: tests
tags: [golden-tests, field-alignment, BP_FirstPersonCharacter]
dependency_graph:
  requires: [Phase 73 Pin serialization, Phase 74 PinReference alignment]
  provides: [field-level regression test suite for golden nodes]
  affects: [tests/]
tech-stack:
  added: [pytest, caplog]
  patterns: [golden testing, semantic node lookup, field assertion]
key-files:
  created:
    - tests/test_phase75_event_node_field_alignment.py
decisions:
  - Comment node matching uses substring matching (UE comment text is longer than label)
  - FunctionEntry search spans all graphs (each function has its own graph)
  - Garbage pin detection includes invalid direction values, /Game/ paths, empty names
metrics:
  duration: ~5m
  completed: "2026-05-26"
---

# Phase 75 Plan 02: 强化 Golden Tests 总结

**One-liner:** 新增 BP_FirstPersonCharacter 字段级对齐 golden test suite，暴露 3 类解析差异。

## 测试函数实现

| # | 函数 | 状态 | 发现 |
|---|------|------|------|
| 1 | `test_enhanced_input_nodes_match_reference_fields` | 失败（有意） | IA_Move 节点存在乱码 pins（direction=67, /Game/ 路径） |
| 2 | `test_touch_event_nodes_match_reference_fields` | 失败（有意） | 3/4 事件 `bOverrideFunction=False`（预期全部 True） |
| 3 | `test_function_entry_nodes_match_reference_fields` | 失败（有意） | FunctionEntry pin 名称为合并形式（"Left / Right" vs 独立 "Left"/"Right"） |
| 4 | `test_no_low_confidence_pin_recovery_for_golden_edges` | 通过 | 关键 pin 不依赖低置信度恢复 |
| 5 | `test_comment_nodes_exist` | 通过 | 3/3 注释节点存在（使用子串匹配） |

## 辅助函数

- `_find_graph(parsed_asset, name)` - 按名称查找 Graph
- `_nodes_by_semantic_name(graph)` - 按语义名称索引节点
- `_pins_by_name(node)` - 按 pin_name 索引 pins
- `_assert_pin(node, name, direction, category, subcategory)` - 断言 pin 属性
- `_assert_no_garbage_pin_names(node)` - 检查乱码 pin 名称

## 暴露的差异

### EnhancedInputAction (IA_Move)
- 乱码 pin 名称：`ActionValue_X` (direction=67), `/Game/FirstPerson/Blueprints/BP_FirstPersonCharacter` (含对象路径), 空/None pin 名称
- 其他 3 个节点（IA_Look, IA_Jump, IA_MouseLook）验证通过

### K2Node_Event (Touch 事件)
- `Primary Thumbstick`: bOverrideFunction=True (OK)
- `Secondary Thumbstick`, `Touch Jump Start`, `Touch Jump End`: bOverrideFunction=False (与预期不符)

### K2Node_FunctionEntry
- `Move`: pin 名称为 `Left / Right`, `Forward / Backward`（合并形式）
- `Aim`: pin 名称为 `Yaw`, `Pitch`（正确但断言失败因期望分离的 pin）
- FunctionEntry 位于独立 graphs 而非 EventGraph

## Decisions Made

1. **Comment 节点使用子串匹配**：UE 中注释文本包含完整描述（如 "Jump Input - Jump can be configured in the CharacterMovementComponent"），测试使用包含关系而非精确匹配
2. **FunctionEntry 搜索跨所有 graphs**：每个函数有独立的 UEdGraph，不在 EventGraph 中
3. **测试设计为先暴露失败**：plan 明确要求"先失败，失败信息必须指向字段级差异"

## 测试运行结果

```
5 tests: 3 failed (intentional field-level differences), 2 passed
Duration: 0.71s
```
