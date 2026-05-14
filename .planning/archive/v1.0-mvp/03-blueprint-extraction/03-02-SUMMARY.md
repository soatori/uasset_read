---
phase: 03
plan: 02
subsystem: blueprint_extraction
tags: [blueprint, variable-parsing, type-parsing, BLUE-03, BLUE-05]
requires: ["03-01"]
provides: ["read_ed_graph_pin_type", "parse_default_value", "read_blueprint_variable"]
affects: ["uasset_read.py"]
tech_stack:
  added: ["re module for regex parsing"]
  patterns: ["FArchive reader pattern", "dataclass return values"]
key_files:
  created: []
  modified: ["uasset_read.py"]
decisions:
  - D-08: 完整结构解析 (读取所有字段)
  - D-13: 解析 DefaultValue 为 Python 原生类型
  - D-14: 解析失败时 fallback 为原始字符串
  - D-15: 仅基本类型 (无数组、向量、对象)
  - D-16: 向量类型保持字符串 "(X=...,Y=...,Z=...)"
metrics:
  duration: "5 minutes"
  tasks: 4
  files: 1
  tests_passed: 21
  completed: "2026-05-01T13:06:36Z"
---

# Phase 03 Plan 02: Blueprint Type and Variable Parsing Summary

## One-liner

实现 `read_ed_graph_pin_type()`、`parse_default_value()` 和 `read_blueprint_variable()` 函数,用于带版本感知序列化的蓝图变量定义解析。

## Implementation Details

### Task 1: read_ed_graph_pin_type() (BLUE-05)

**Commit:** aafea28

实现 FEdGraphPinType 解析,遵循 UE 5.7 EdGraphPin.cpp lines 163-346 序列化顺序:
1. PinCategory (FName) - 主类型类别
2. PinSubCategory (FName) - 子类型标识符
3. PinSubCategoryObject (FPackageIndex) - 对象引用
4. ContainerType (uint8) - 0=None, 1=Array, 2=Set, 3=Map
5. PinValueType (FEdGraphTerminalType) - 为 Map containers skipped
6. bIsReference (bool)
7. bIsWeakPointer (bool)
8. PinSubCategoryMemberReference (FSimpleMemberReference) - 为 Phase 3 skipped
9. bIsConst (bool)
10. bIsUObjectWrapper (bool)

版本感知实现假设现代 UE 文件 (UE4 v521+, UE5),所有字段都存在。

### Task 2: parse_default_value() (BLUE-03)

**Commit:** 5c25e4d

实现 DefaultValue 字符串解析为 Python 原生类型:
- `bool` category: 解析 "true"/"false"/"1"/"0" 为 boolean
- `int`/`integer` category: 通过 regex 解析为 int
- `float`/`real`/`double` category: 通过 regex 解析为 float
- `string`/`name`/`text` category: 保持为 string
- Vector format "(X=...,Y=...,Z=...)": 按 D-16 保持为 string
- Unknown types: 按 D-14 fallback 为 raw string

添加 `re` module import 用于 regex pattern matching。

### Task 3: read_blueprint_variable() (BLUE-03)

**Commit:** c481486

实现 FBPVariableDescription 解析,遵循 Blueprint.h lines 200-256:
1. VarName (FName)
2. VarGuid (16 bytes) - skipped
3. VarType (FEdGraphPinType) - via read_ed_graph_pin_type()
4. FriendlyName (FString)
5. Category (FText) - simplified to FString
6. PropertyFlags (uint64)
7. RepNotifyFunc (FName) - skipped
8. ReplicationCondition (uint8) - skipped
9. MetaDataArray (TArray) - skipped (deferred to BLUE-04)
10. DefaultValue (FString) - via parse_default_value()

### Task 4: __all__ Export Update

**Commit:** ec3fd54

添加 Phase 3 函数到 public API exports:
- `read_ed_graph_pin_type`
- `parse_default_value`
- `read_blueprint_variable`

分组在新 "Blueprint parsing functions (Phase 3)" section 下。

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Missing `re` module import**
- **Found during:** Task 2 verification
- **Issue:** parse_default_value() used `re.match()` but module not imported
- **Fix:** Added `import re` after `import struct` in imports section
- **Files modified:** uasset_read.py line 18
- **Commit:** 5c25e4d

None other - plan executed exactly as written.

## Verification Results

### Automated Tests

```
tests/test_blueprint_extraction.py: 21 passed in 0.07s
```

所有 BLUE-03 和 BLUE-05 tests pass:
- TestEdGraphPinTypeParsing: 4 tests (basic, array, map, flags)
- TestBlueprintVariableParsing: 3 tests (basic, array type, version fields)
- TestVariableMetadata: 4 tests (bool, int, float, vector)
- TestBlueprintExtractionIntegration: 3 tests (full extraction, multiple vars, nested types)

### Manual Verification

```python
from uasset_read import read_ed_graph_pin_type, read_blueprint_variable, parse_default_value, FEdGraphPinType, BlueprintVariable
print('All imports OK')  # Success
```

## Self-Check: PASSED

- [x] read_ed_graph_pin_type() function exists at line 946
- [x] parse_default_value() function exists at line 1028
- [x] read_blueprint_variable() function exists at line 1085
- [x] All functions importable from uasset_read
- [x] All 21 tests pass
- [x] __all__ exports updated

## Threat Flags

None - all functions follow FArchive pattern with boundary validation.

## Known Stubs

None - no hardcoded placeholder values in implementation.