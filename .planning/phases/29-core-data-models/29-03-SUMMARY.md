---
phase: "29-core-data-models"
plan: 03
status: complete
completed: "2026-05-11"
---

# Plan 29-03 Summary: ParseResult, StatusInfo, Blueprint Metadata

## Objective
创建 `models/result.py` 定义 ParseResult 和 StatusInfo，创建 `models/blueprint.py` 定义 BlueprintMetadata 等辅助类，并更新所有模块导出。

## What Was Built
- `src/uasset_read/models/result.py` — ParseResult (14 fields matching source exactly), StatusInfo (3 fields)
- `src/uasset_read/models/blueprint.py` — 6 @dataclass:
  - FunctionParameter (8 fields)
  - MulticastDelegate (3 fields)
  - BlueprintEvent (25 fields)
  - BlueprintFunction (28 fields)
  - BlueprintVariable (36 fields)
  - BlueprintMetadata (6 fields)
- Updated `models/__init__.py` — complete 16-class export
- Updated `src/uasset_read/__init__.py` — backward-compatible re-export of all 18 classes

## Key Details
- ParseResult uses TYPE_CHECKING imports for serializers types (avoids circular imports)
- ParseResult does NOT use from_archive (it's an aggregation result)
- BlueprintVariable.var_type uses forward reference "FEdGraphPinType"
- All blueprint classes use field(default_factory=dict) instead of __post_init__ for mutable defaults
- Field names match uasset_read.py source exactly

## Verification
- All 18 classes importable from `uasset_read` ✓
- ParseResult has 14 fields (correct count from source) ✓
- BlueprintVariable has 36 fields ✓
- asdict(ParseResult) works ✓
- StatusInfo instantiation works ✓

## Deviation
Plan claimed ParseResult has 16 fields; actual source has 14. Implementation matches source.
