---
phase: 18-pin-serialization
plan: 01
subsystem: core
tags: [constants, dataclass, pin-serialization]
requires: []
provides: [CustomVersion constants, UEdGraphPin extended fields]
affects: [uasset_read.py]
tech-stack:
  added: [CustomVersion GUID constants, Version threshold constants]
  patterns: [UE source verification]
key-files:
  created: []
  modified:
    - path: uasset_read.py
      changes: Added CustomVersion constants, extended UEdGraphPin dataclass
decisions:
  - GUID values from UE 5.7 source (DevObjectVersion.cpp, EngineVersion.cpp)
  - Version thresholds from enum positions (0-indexed)
  - linked_to_raw type changed from List[str] to List[dict] for proper Pin reference format
metrics:
  duration: "5 minutes"
  completed: "2026-05-04T06:35:00Z"
  tasks: 2
  files: 1
---

# Phase 18 Plan 01: CustomVersion常量 + UEdGraphPin dataclass扩展 Summary

添加 CustomVersion 常量定义和扩展 UEdGraphPin dataclass，为后续函数重写提供类型基础。

## Completed Tasks

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | 添加 CustomVersion 常量定义 | 04e52a8 | uasset_read.py |
| 2 | 扩展 UEdGraphPin dataclass 字段 | 04e52a8 | uasset_read.py |

## Key Changes

### Task 1: CustomVersion 常量定义

在常量定义区添加了三个 CustomVersion GUID 常量和四个版本阈值：

**GUID 常量：**
- `FFRAMEWORK_OBJECT_VERSION_GUID = "CFFC743F-43B04480-939114DF-171D2073"`
- `FUE5_MAINSTREAM_VERSION_GUID = "697DD581-E64F41AB-AA4A51EC-BEB7B628"`
- `FRELEASE_OBJECT_VERSION_GUID = "9C54D522-A8264FBE-94210746-61B482D0"`

**版本阈值：**
- `FFRAMEWORK_VERSION_ED_GRAPH_PIN_CONTAINER_TYPE = 15` (EdGraphPinContainerType)
- `FFRAMEWORK_VERSION_PINS_STORE_FNAME = 20` (PinsStoreFName)
- `FUE5_MAINSTREAM_VERSION_ED_GRAPH_PIN_SOURCE_INDEX = 50` (EdGraphPinSourceIndex)
- `FRELEASE_VERSION_PIN_TYPE_UOBJECT_WRAPPER = 10` (PinTypeIncludesUObjectWrapperFlag)

### Task 2: UEdGraphPin dataclass 扩展

扩展 UEdGraphPin dataclass 添加以下字段组：

**PIN-01 基础信息：**
- `pin_tooltip: str = ""` - FString PinToolTip 字段

**PIN-03 默认值：**
- `default_object: Optional[int] = None` - FPackageIndex 引用
- `default_text_value: Optional[str] = None` - FText 简化

**PIN-04 连接引用：**
- `linked_to_raw: List[dict]` - 改为 dict 格式支持完整 Pin 引用
- `sub_pins: List[dict]` - 同 linked_to 格式
- `parent_pin: Optional[dict]` - 同 linked_to 格式

**PIN-05 显示属性（BitField 解析）：**
- `hidden: bool = False` - bit 0
- `not_connectable: bool = False` - bit 1
- `advanced_view: bool = False` - bit 4
- `orphaned_pin: bool = False` - bit 5

**内部字段：**
- `owning_node_index: int = 0` - FPackageIndex (序列化起始)
- `source_index: Optional[int] = None` - int32 版本依赖
- `persistent_guid: Optional[str] = None` - FGuid hex EditorOnly

## Deviations from Plan

None - plan executed exactly as written.

## Verification

**自动化验证通过：**
- CustomVersion GUID 常量存在（三个 GUID）
- 版本阈值常量存在（PinsStoreFName=20, EdGraphPinContainerType=15, EdGraphPinSourceIndex=50, PinTypeUObjectWrapper=10）
- UEdGraphPin 新字段存在（pin_tooltip, hidden, default_object）
- linked_to_raw 类型已改为 List[dict]

## Next Steps

- Phase 18-02: 实现 `read_ue_graph_pin()` 函数重写，使用新常量和扩展的 dataclass

## Self-Check: PASSED

- [x] CustomVersion 常量定义存在
- [x] UEdGraphPin dataclass 扩展字段存在
- [x] 提交 04e52a8 已创建