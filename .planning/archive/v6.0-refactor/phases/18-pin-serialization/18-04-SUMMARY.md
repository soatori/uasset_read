---
phase: 18-pin-serialization
plan: 04
subsystem: core
tags: [pin-serialization, version-check, custom-version]
requires: [18-01, 18-03]
provides: [read_ed_graph_pin_type() version checks]
affects: [uasset_read.py]
tech-stack:
  added: [Version-dependent PinCategory/PinSubCategory, Version-dependent ContainerType, Legacy bool flags handling]
  patterns: [UE source EdGraphPin.cpp L163-346 verification]
key-files:
  created: []
  modified:
    - path: uasset_read.py
      changes: Added version checks to read_ed_graph_pin_type() per UE source
decisions:
  - PinCategory/PinSubCategory use FName when framework_version >= 20, else FString
  - ContainerType use uint8 when framework_version >= 15, else legacy bool flags
  - Simplified legacy handling without FBlueprintsObjectVersion check (modern assets)
metrics:
  duration: "2 minutes"
  completed: "2026-05-04T06:43:42Z"
  tasks: 1
  files: 1
---

# Phase 18 Plan 04: 修复 read_ed_graph_pin_type() 版本检查 Summary

修复 `read_ed_graph_pin_type()` 函数的版本条件检查，使其正确处理 FName/FString 格式转换和 ContainerType 版本依赖字段。

## Completed Tasks

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | 修复 read_ed_graph_pin_type() 版本检查 | 4bac806 | uasset_read.py |

## Key Changes

### Task 1: read_ed_graph_pin_type() 版本检查

**序列化顺序（UE 源码 EdGraphPin.cpp L163-346 验证）：**

| 序号 | 字段 | 格式 | 版本依赖 |
|------|------|------|----------|
| 1 | PinCategory | FName/FString | framework_version >= PINS_STORE_FNAME (20) |
| 2 | PinSubCategory | FName/FString | framework_version >= PINS_STORE_FNAME (20) |
| 3 | PinSubCategoryObject | FPackageIndex | 无版本依赖 |
| 4 | ContainerType | uint8/bool flags | framework_version >= ED_GRAPH_PIN_CONTAINER_TYPE (15) |
| 5 | PinValueType | FEdGraphTerminalType | ContainerType == Map 时读取 |
| 6 | bIsReference | bool | 无版本依赖 |
| 7 | bIsWeakPointer | bool | 无版本依赖 |
| 8 | PinSubCategoryMemberReference | FSimpleMemberReference | VER_UE4_MEMBERREFERENCE_IN_PINTYPE |
| 9 | bIsConst | bool | VER_UE4_SERIALIZE_PINTYPE_CONST |
| 10 | bIsUObjectWrapper | bool | release_version >= PinTypeUObjectWrapper (10) |

**关键变更：**

1. **PinCategory/PinSubCategory 版本检查（L174-188）：**
   - `framework_version >= FFRAMEWORK_VERSION_PINS_STORE_FNAME (20)`：使用 FName 格式
   - `framework_version < 20`：使用 FString 格式（legacy）

2. **ContainerType 版本检查（L215-246）：**
   - `framework_version >= FFRAMEWORK_VERSION_ED_GRAPH_PIN_CONTAINER_TYPE (15)`：读取 uint8
   - `framework_version < 15`：读取 legacy bool flags（bIsMap, bIsSet, bIsArray），转换到 ContainerType

3. **版本获取使用 18-01 定义的常量：**
   - `FFRAMEWORK_OBJECT_VERSION_GUID`
   - `FRELEASE_OBJECT_VERSION_GUID`
   - `FFRAMEWORK_VERSION_PINS_STORE_FNAME = 20`
   - `FFRAMEWORK_VERSION_ED_GRAPH_PIN_CONTAINER_TYPE = 15`

**代码变更详情：**

```python
# 旧实现（无版本检查）
pin_type.pin_category = archive.read_name(name_map)
pin_type.pin_sub_category = archive.read_name(name_map)
pin_type.container_type = archive.read_u8()

# 新实现（版本检查）
framework_version = summary.custom_version.get(FFRAMEWORK_OBJECT_VERSION_GUID, 0)

if framework_version >= FFRAMEWORK_VERSION_PINS_STORE_FNAME:
    pin_type.pin_category = archive.read_name(name_map)
    pin_type.pin_sub_category = archive.read_name(name_map)
else:
    pin_type.pin_category = archive.read_fstring()
    pin_type.pin_sub_category = archive.read_fstring()

if framework_version >= FFRAMEWORK_VERSION_ED_GRAPH_PIN_CONTAINER_TYPE:
    pin_type.container_type = archive.read_u8()
else:
    b_is_map = archive.read_bool()
    b_is_set = archive.read_bool()
    b_is_array = archive.read_bool()
    # Convert to ContainerType...
```

## Deviations from Plan

None - plan executed exactly as written.

## Verification

**自动化验证通过：**
- `grep -c "framework_version.*PINS_STORE_FNAME"` = 2 ✓
- `grep -c "FFRAMEWORK_VERSION_ED_GRAPH_PIN_CONTAINER_TYPE"` = 2 ✓
- `grep -c "b_is_map.*read_bool"` = 2 ✓ (legacy flags)
- Python 语法验证通过 ✓
- 359 测试通过，49 跳过 ✓

## Next Steps

- Phase 18 完成：Pin 序列化解析全部修复
- Phase 19: 构建连接映射（使用 LinkedTo 中的 OwningNode + PinGuid）

## Self-Check: PASSED

- [x] PinCategory/PinSubCategory 版本检查存在
- [x] ContainerType 版本检查存在
- [x] Legacy bool flags 处理存在
- [x] Map 容器 PinValueType 处理存在
- [x] 使用 18-01 定义的 CustomVersion 常量
- [x] 测试通过（359 passed）
- [x] 提交 4bac806 已创建

## Self-Check Verification

- SUMMARY.md 文件存在: FOUND
- 提交 4bac806 存在于 git log: FOUND