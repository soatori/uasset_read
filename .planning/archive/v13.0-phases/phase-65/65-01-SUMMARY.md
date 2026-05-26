---
gsd_state_version: 1.2
phase: 65-graph-parser-fix
plan: 01
subsystem: serializers/graph
tags: [FMemberReference, PinConnection, UEdGraphPin, GAP-01, GAP-02]
requires: []
provides: [function_reference.member_name, pin_type.pin_category]
affects: [graph parsing, blueprint nodes, execution flow]
tech_stack:
  added:
    - PinReference format understanding (UE5)
    - header_owning_node/header_pin_id params in read_ue_graph_pin
  patterns:
    - D-11: PropertyTag-parsed reference reuse
    - D-12: UE5 PinReference header/body format
key_files:
  created:
    - tests/test_graph_parser_fix.py
  modified:
    - src/uasset_read/serializers/graph.py
decisions:
  - D-11: Pass PropertyTag-parsed function_reference to node handlers
  - D-12: UE5 Pin array uses PinReference format with external header
metrics:
  duration: "4h"
  tasks: 3
  tests: 7
  commits: 2
  completed_date: "2026-05-20T17:30:00Z"
---

# Phase 65 Plan 01: FMemberReference + Pin 连接修复 Summary

## One-liner

修复 FMemberReference.member_name 解析错误（GAP-01），部分修复 Pin 连接格式理解（GAP-02），验证 7 个测试通过。

## Goal Achievement

**Goal:** 让 Agent 能够获取正确的函数引用和节点连接关系，支撑 Phase 66 的 C++ 翻译管线。

**Achieved:**
- ✅ FMemberReference.member_name 正确解析为实际函数名（AddControllerYawInput 等）
- ✅ 13/13 CallFunction 节点有有效的 member_name
- ✅ Event 节点的 event_reference 正确解析
- 🔶 Pin 连接格式理解改进（发现 UE5 PinReference 格式）
- 🔶 Pin 名称部分正确（execute 等常见名称）

## Changes

### Task 1: FMemberReference 修复 (GAP-01)

**Problem:** `read_k2node_call_function()` 从错误位置读取 FMemberReference，导致 member_name='None'。

**Root Cause:** PropertyTag 层已正确解析 FunctionReference 存储在 node_refs，但节点处理函数重新从 archive 读取导致位置错位。

**Fix (D-11):**
- `read_k2node_call_function()`: 添加 `function_reference` 参数，优先使用 PropertyTag 层解析结果
- `read_k2node_event()`: 同样添加 `event_reference` 参数
- `create_node_from_archive()`: 传递 node_refs 到节点处理函数

**Files:** `src/uasset_read/serializers/graph.py` (L580-620, L733-743)

### Task 2: Pin 连接格式理解 (GAP-02 Partial)

**Problem:** Pin 数组解析格式错误，导致 pin_category='None', linked_to_raw=[]。

**Root Cause (D-12):** UE5 Pin 数组使用 PinReference 格式：
```
External Header: b_null_ptr (i32) + owning_node (i32) + pin_guid (16 bytes)
Body: Complete UEdGraphPin (duplicates header + PinName + ...)
```
每个 Pin 有两个 header：外部引用 header 和内部完整 header。

**Fix:**
- `read_ue_graph_pin()`: 添加 `header_owning_node/header_pin_id` 参数，跳过内部重复数据
- Pins offset 计算修正：`script_serial_size + 4`（跳过 end marker）
- 调用方读取外部 header 后传递给 read_ue_graph_pin

**Files:** `src/uasset_read/serializers/graph.py` (L356-395, L912-960)

**Note:** Pin 连接完整修复仍需更多工作（linked_to_raw 仍为空）。

### Task 3: 测试文件

**Created:** `tests/test_graph_parser_fix.py` (7 tests)

**Tests:**
- `test_call_function_member_name_not_none`: 验证 member_name != 'None'
- `test_call_function_member_name_is_function_name`: 验证实际函数名
- `test_event_reference_member_name_not_none`: 验证 Event 节点
- `test_pin_names_are_valid`: 验证 Pin 名称有意义
- `test_pin_type_category_exists`: 验证 pin_category 有效
- `test_graphs_have_nodes`: 验证图中有节点
- `test_function_entry_nodes_exist`: 验证 FunctionEntry 节点

## Deviations

### Rule 1 - Bug: Byte_swapping 设置错误

**Found:** 调试时手动设置 `archive.set_byte_swapping(True)` 导致数据解析错误。

**Fix:** 移除手动设置，让 `read_package_summary()` 自动检测 PACKAGE_FILE_TAG_SWAPPED。

**Files:** None (调试过程，未提交)

### Rule 3 - Blocking Issue: Pins offset 计算错误

**Found:** 代码假设 Pins 数组紧随 script_serial，实际 UE5 有 4 bytes end marker。

**Fix:** `pins_offset = script_serial_offset + script_serial_size + 4`

**Files:** `src/uasset_read/serializers/graph.py` (L912-916)

### Known Stubs

| Stub | File | Line | Reason |
|------|------|------|--------|
| linked_to_raw 空数组 | graph.py | L928-960 | UE5 PinReference 格式理解部分完成，linked_to 读取逻辑需进一步调试 |
| 部分 Pin 名称异常 | graph.py | L395+ | Pin 大小计算仍需研究，导致后续 Pin 位置错位 |

## Verification

### FMemberReference 验证

```bash
python -c "from uasset_read import parse_uasset_with_linker; r = parse_uasset_with_linker('...'); nodes = [n for g in r.graphs for n in g.nodes if n.class_name == 'K2Node_CallFunction']; print([n.node_data.get('function_reference').member_name for n in nodes])"
# 输出: ['AddControllerYawInput', 'AddControllerPitchInput', 'Aim', ...]
```

### 测试验证

```bash
python -m pytest tests/test_graph_parser_fix.py -v
# 7 passed in 0.28s
```

## Success Criteria

- [x] `read_fmember_reference()` 正确读取 `member_name`（通过 PropertyTag 层复用）
- [x] `read_k2node_call_function()` 接受已有 function_reference
- [x] `read_k2node_event()` 接受已有 event_reference
- [x] 测试文件验证修复效果（7 tests passed）
- [x] 对 `BP_FirstPersonCharacter.uasset` 解析不产生 ParseError
- [x] CallFunction 节点有正确的函数名（AddControllerYawInput 等）
- [ ] **Pin 连接完整修复**（linked_to_raw 仍为空，需后续工作）

## Dependencies

```
Task 1 (FMemberReference) ──┐
                             ├──→ Task 3 (Tests) ──→ SUMMARY
Task 2 (Pin connections) ───┘
```

Task 2 依赖更深入的 UE5 Pin 序列化研究，已部分完成。

## Next Steps

**对于 Phase 65 Plan 02:**
1. 研究 UE5 UEdGraphPin 完整序列化流程（所有字段大小）
2. 计算 Pin 大小逻辑，确定下一个 Pin 的起始位置
3. 修复 linked_to_raw 数组读取
4. 实现 GAP-03（Struct 映射）和 GAP-07（函数签名）

---

*Phase: 65-图解析器修复*
*Plan: 01-FMemberReference + Pin 连接*
*Completed: 2026-05-20*