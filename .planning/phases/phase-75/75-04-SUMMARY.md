---
gsd_state_version: 1.0
phase: 75
plan: 04
subsystem: serializers
tags: [K2Node_Event, bOverrideFunction, PropertyTag, tail-blind-read-removal]
dependency_graph:
  requires: [Phase 73 Pin serialization, Phase 74 PinReference alignment]
  provides: [K2Node_Event PropertyTag field extraction, bOverrideFunction correct parsing]
  affects: [src/uasset_read/serializers/graph.py]
tech-stack:
  added: [_read_tag_bool, _read_tag_i32, _read_tag_fname helper functions]
  patterns: [PropertyTag-first reading, fallback validation, node_refs propagation]
key-files:
  modified:
    - src/uasset_read/serializers/graph.py
decisions:
  - bOverrideFunction read from PropertyTag first, legacy fallback only when PropertyTag absent
  - Added b_internal_event, custom_function_name, function_flags as new node_data fields
  - FString length=-1 boundary condition fixed (UE empty string marker)
metrics:
  duration: ~10m
  completed: "2026-05-26"
---

# Phase 75 Plan 04: 移除事件节点尾部盲读 总结

**One-liner:** 修正 `read_k2node_event()` 移除尾部盲读，4 个 Touch Interface 事件 `bOverrideFunction` 全部正确解析为 True。

## 实现内容

### read_k2node_event() 修改

| # | 修改项 | 说明 |
|---|--------|------|
| 1 | 新增参数 | `b_override_function`, `b_internal_event`, `custom_function_name`, `function_flags` 从 PropertyTag 传入 |
| 2 | 移除盲读 | `b_override_function` 优先使用 PropertyTag 值，仅在未提供时 fallback |
| 3 | 返回新字段 | `b_internal_event`, `custom_function_name`, `function_flags` 附加字段 |

### PropertyTag 处理增强

| # | PropertyTag | 目标变量 | 类型 |
|---|-------------|----------|------|
| 1 | `bOverrideFunction` | `b_override_function` | bool |
| 2 | `bInternalEvent` | `b_internal_event` | bool |
| 3 | `CustomFunctionName` | `custom_function_name` | FName |
| 4 | `FunctionFlags` | `function_flags` | int |

### Helper 函数新增

| 函数 | 用途 |
|------|------|
| `_read_tag_bool()` | 统一处理 inline bool 与 value body 两种形态 |
| `_read_tag_i32()` | 读取 int32 并确保 seek 到 value_end_offset |
| `_read_tag_fname()` | 读取 FName 并确保 seek 到 value_end_offset |

### FString 边界条件修复

修复 `length == -1` 边界条件（UE 空字符串标记），避免错误读取后续字段。

## 验证结果

**验收标准：** 4 个 Touch Interface 事件均为 `bOverrideFunction=True`

| 事件 | bOverrideFunction | 状态 |
|------|-------------------|------|
| Primary Thumbstick | True | OK |
| Secondary Thumbstick | True | OK |
| Touch Jump Start | True | OK |
| Touch Jump End | True | OK |

**对比 PLAN-75-02 基线：**
- Secondary Thumbstick: False → True (修复)
- Touch Jump Start: False → True (修复)
- Touch Jump End: False → True (修复)
- Primary Thumbstick: True → True (保持正确)

## 回归测试

```
tests/test_phase73_bp_first_person_e2e.py: 24 passed
tests/test_phase73_linkedto_recovery.py: passed
tests/test_phase74_pin_reference_layout.py: passed
Total: 24 passed, 9 warnings, 0 regressions
```

## Deviations from Plan

None - plan executed exactly as written.

## 已知遗留问题

以下问题不属于 Plan 75-04 范围，将在后续 plan 处理：

| 问题 | 范围 | 状态 |
|------|------|------|
| EnhancedInputAction pin direction 错位 (114/46) | Plan 75-05/75-06 | 待修复 |
| Primary Thumbstick Axis_X direction=0, pin_category='/Game/...' | Plan 75-05/75-06 | 待修复 |
| FunctionEntry 参数 pin 缺失 | Plan 75-03/75-07 | 待修复 |

## 提交

```
ab40745 feat(phase-75-04): remove K2Node_Event tail blind read for bOverrideFunction
```