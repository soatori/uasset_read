---
phase: 18-pin-serialization
plan: 02
subsystem: core
tags: [pin-reference, helper-functions, serialization]
requires: [18-01]
provides: [read_pin_reference(), read_pin_array()]
affects: [uasset_read.py]
tech-stack:
  added: [Pin reference parsing helpers, SerializePin format support]
  patterns: [UE source verification, FPackageIndex resolution]
key-files:
  created: []
  modified:
    - path: uasset_read.py
      changes: Added read_pin_reference() and read_pin_array() helper functions
decisions:
  - FPackageIndex resolution: >0 ExportMap (1-indexed), <0 ImportMap (negated)
  - PinGuid hex format: uppercase for consistency
  - Null pin handling: return None for bNullPtr=true
metrics:
  duration: "1 minute"
  completed: "2026-05-04T06:36:54Z"
  tasks: 2
  files: 1
---

# Phase 18 Plan 02: Pin引用解析辅助函数 Summary

实现 Pin 引用解析辅助函数，为 read_ue_graph_pin() 重写提供 SerializePin 格式支持。

## Completed Tasks

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | 实现 read_pin_reference() 函数 | b254413 | uasset_read.py |
| 2 | 实现 read_pin_array() 函数 | b254413 | uasset_read.py |

## Key Changes

### Task 1: read_pin_reference() 函数

在 `read_ue_graph_pin()` 之前添加了 `read_pin_reference()` 函数：

**SerializePin 格式解析（来自 UE 源码 EdGraphPin.cpp L2132-2296）：**
1. `bNullPtr` (bool/uint8) — 空指针标记
2. `OwningNode` (FPackageIndex/int32) — 所属节点索引
3. `PinGuid` (FGuid 16 bytes) — Pin GUID

**FPackageIndex 解析规则：**
- `> 0`: ExportMap，索引为 `index - 1`（FPackageIndex 是 1-indexed）
- `< 0`: ImportMap，索引为 `-index - 1`
- 返回节点名称字符串

**返回格式：**
```python
{
    "owning_node": str,  # 节点名称
    "pin_guid": str      # FGuid hex (uppercase)
}
```

### Task 2: read_pin_array() 函数

在 `read_pin_reference()` 之后添加了 `read_pin_array()` 函数：

**SerializePinArray 格式解析（来自 UE 源码 EdGraphPin.cpp L2063-2098）：**
1. `ArrayNum` (int32) — 数组元素数量
2. 循环调用 `read_pin_reference()` 解析每个元素

**安全边界：**
- 使用 `MAX_LINKEDTO_PER_PIN` (100) 限制数组大小
- 负数 count 抛出 `ParseError`
- 超限 count 抛出 `ParseError`

**返回格式：**
```python
List[dict]  # 每个 dict 为 pin reference
```

## Deviations from Plan

None - plan executed exactly as written.

## Verification

**自动化验证通过：**
- `read_pin_reference()` 函数存在 (grep -c = 1)
- `read_pin_array()` 函数存在 (grep -c = 1)
- `b_null_ptr = archive.read_bool()` 存在 (grep -c = 1)
- `owning_node_index = archive.read_i32()` 存在 (grep -c = 1)
- `MAX_LINKEDTO_PER_PIN` 边界检查存在 (grep -c = 15)
- Python 语法验证通过
- 359 测试通过，49 跳过

## Next Steps

- Phase 18-03: 实现 `read_ue_graph_pin()` 函数重写，使用 `read_pin_reference()` 和 `read_pin_array()`

## Self-Check: PASSED

- [x] `read_pin_reference()` 函数存在
- [x] `read_pin_array()` 函数存在
- [x] 边界检查使用 `MAX_LINKEDTO_PER_PIN`
- [x] 返回类型为 dict 格式
- [x] 提交 b254413 已创建