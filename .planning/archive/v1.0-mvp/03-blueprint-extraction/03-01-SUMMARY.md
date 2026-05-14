---
phase: 03-blueprint-extraction
plan: 01
subsystem: blueprint-core
tags: [blueprint-detection, parent-class, dataclasses]

requires: []
provides:
  - BlueprintVariable dataclass (BLUE-03)
  - FEdGraphPinType dataclass (BLUE-05)
  - BlueprintMetadata dataclass (BLUE-01/02)
  - detect_blueprint() function (BLUE-01)
  - resolve_parent_class() function (BLUE-02)
affects: [03-02, 03-03]

tech-stack:
  added: []
  patterns: [dataclass-extension, get_asset_class-pattern, fpackageindex-resolution]

key-files:
  created: []
  modified:
    - uasset_read.py
    - tests/test_blueprint_extraction.py

key-decisions:
  - "BlueprintVariable uses forward reference for var_type: FEdGraphPinType"
  - "BlueprintMetadata stores detection_warning for D-03 graceful degradation"
  - "detect_blueprint() reuses get_asset_class() pattern from Phase 1"
  - "resolve_parent_class() returns Tuple[Optional[str], Optional[str]] per D-11"

requirements-completed: [BLUE-01, BLUE-02]

duration: 15 minutes
completed: 2026-05-01
---

# Phase 3 Plan 01: Blueprint Detection and Parent Class Resolution Summary

**Blueprint detection from ClassIndex and ParentClass FPackageIndex resolution with full dataclass definitions for blueprint metadata structures**

## Performance

- **Duration:** 15 minutes
- **Tasks:** 4 completed (all auto type)
- **Tests:** 21 blueprint extraction tests passing, 27 core tests passing

## Accomplishments

- 添加 FEdGraphPinType dataclass,包含 8 个字段,包括版本感知标志
- 添加 BlueprintVariable dataclass for FBPVariableDescription structure
- 添加 BlueprintMetadata dataclass,包含 is_blueprint、parent_class、variables、detection_warning
- 扩展 ParseResult with blueprint: Optional[BlueprintMetadata] field
- 实现 detect_blueprint() 使用 get_asset_class() pattern (checks "Blueprint" keyword)
- 实现 resolve_parent_class() 返回 (resolved_name, warning) tuple
- 更新 __all__ exports 包含 3 个新 dataclasses 和 2 个新函数
- 移除 test file 中已实现类的 TYPE_CHECKING stubs

## Files Created/Modified

- `uasset_read.py` - 添加 3 个 dataclasses、2 个函数、扩展 ParseResult、更新 imports 和 __all__
- `tests/test_blueprint_extraction.py` - 更新 imports 使用已实现类

## Implementation Details

### FEdGraphPinType Dataclass

按 RESEARCH.md Pitfall 1,包含版本感知字段:
- `pin_category`, `pin_sub_category`, `pin_sub_category_object` (base fields)
- `container_type` (EPinContainerType: 0=None, 1=Array, 2=Set, 3=Map)
- `is_reference`, `is_const`, `is_weak_pointer`, `is_uobject_wrapper` (flags)

### BlueprintVariable Dataclass

按 D-05/D-06:
- `var_name` (FName)
- `var_type` (FEdGraphPinType forward reference)
- `category`, `property_flags`, `default_value`, `friendly_name`

### BlueprintMetadata Dataclass

按 D-01/D-02/D-03:
- `is_blueprint` (bool)
- `parent_class` (Optional[str]) - 按 D-09 仅直接父类
- `variables` (List[BlueprintVariable])
- `detection_warning` (Optional[str]) - 按 D-03

### detect_blueprint() Function

按 D-01/D-04:
- 使用 get_asset_class() 解析 ClassIndex
- 检查类名中 "Blueprint" 关键字
- 不区分 BlueprintType (按 D-04 推迟)

### resolve_parent_class() Function

按 D-09/D-10/D-11:
- 处理 null index (returns None, None for UObject root)
- 解析 import/export indices 为 object_name
- 解析失败时返回 (None, warning) 按 D-11

## Decisions Made

- 使用前向引用字符串避免 BlueprintVariable 和 FEdGraphPinType 间循环定义
- 为 resolve_parent_class() return type 添加 Tuple import 到 typing imports
- 为逻辑排序所有 3 个 dataclasses 放在 ParseResult 前
- 为模式连续性函数放在 get_asset_class() 后

## Deviations from Plan

None - plan executed exactly as written.

## Verification

```bash
# Import verification
python -c "from uasset_read import BlueprintVariable, FEdGraphPinType; print('Import OK')"
# Result: Import OK

python -c "from uasset_read import BlueprintMetadata, BlueprintVariable, FEdGraphPinType, ParseResult; print('All imports OK')"
# Result: All imports OK

python -c "from uasset_read import detect_blueprint; print('Import OK')"
# Result: Import OK

python -c "from uasset_read import resolve_parent_class, PackageIndex; r, w = resolve_parent_class(PackageIndex(0), [], []); print('Import and null check OK')"
# Result: Import and null check OK

# Blueprint extraction tests
python -m pytest tests/test_blueprint_extraction.py -v
# Result: 21 passed

# Core tests
python -m pytest tests/test_uasset_read.py -v
# Result: 27 passed, 1 skipped
```

## Self-Check: PASSED

- FEdGraphPinType dataclass 存在,包含所有 8 个字段
- BlueprintVariable dataclass 存在,包含所有 6 个字段
- BlueprintMetadata dataclass 存在,包含所有 4 个字段
- ParseResult.blueprint field is Optional[BlueprintMetadata]
- detect_blueprint() function exists at line 876
- resolve_parent_class() function exists at line 901
- Commit 54ea924 verified in git log

## Next Steps

Plan 03-02 will implement:
- `read_ed_graph_pin_type()` function (BLUE-05 binary deserialization)
- `read_blueprint_variable()` function (BLUE-03 FBPVariableDescription parsing)
- `parse_default_value()` function (BLUE-06 default value parsing)

Plan 03-03 will implement:
- `extract_blueprint_metadata()` integration function
- Auto-detection in parse_uasset()