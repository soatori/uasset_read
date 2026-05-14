---
phase: 30-property-parsing
plan: "02"
type: execute
subsystem: parsers
tags: [property-parsing, migration, v6.0]
dependency_graph:
  requires:
    - phase: 30
      plan: "01"
      provides: "PropertyTag, PropertyValue, StructValue, MapValue, SetValue, EnumValue, TextValue, DelegateValue dataclasses; read_property_tag serializer"
    - phase: 28
      plan: "core"
      provides: "FArchive, PackageFileSummary, ObjectExport, ObjectImport, PackageIndex"
  provides:
    - "14 parse_*_property functions"
    - "parse_property_value dispatcher (19 type mappings)"
    - "parse_properties_from_export entry point"
    - "resolve_package_index_to_reference in serializers"
  affects:
    - "src/uasset_read/parsers/"
    - "src/uasset_read/serializers/object_resources.py"
tech_stack:
  added: [parsers package, property type handlers, type dispatcher]
  patterns: [lazy import for circular dependency avoidance, TYPE_CHECKING, type dispatch dict]
key_files:
  created:
    - src/uasset_read/parsers/__init__.py
    - src/uasset_read/parsers/property_types.py
    - src/uasset_read/parsers/property_parser.py
  modified:
    - src/uasset_read/serializers/object_resources.py
decisions:
  - "Used lazy import pattern (_get_parse_property_value, _get_read_property_tag) to avoid circular dependency between property_types.py and property_parser.py"
  - "Added resolve_package_index_to_reference to serializers/object_resources.py (Rule 3) — missing dependency required by plan"
  - "Preserved exact function signatures from uasset_read.py source for equivalent migration"
metrics:
  duration: ~15min
  completed_date: "2026-05-11"
  tasks_completed: 3
  files_created: 3
  files_modified: 1
  tests_passing: 411
  tests_skipped: 47
---

# Phase 30 Plan 02: Property Type Parsers Summary

## One-liner

14 property type parser functions with type dispatch, boundary validation, and circular-dependency-safe lazy imports — equivalent migration from uasset_read.py lines 5289-6220.

## Completed Tasks

| Task | Name | Commit | Files |
| ---- | ---- | ------ | ----- |
| 1 | Create property type handlers in parsers/property_types.py | 3e5fa33 | property_types.py (342 lines) |
| 2 | Create dispatcher and export loop in parsers/property_parser.py | 76f51b2 | property_parser.py, object_resources.py |
| 3 | Create parsers/__init__.py with flat exports | 9794a16 | __init__.py |

## Output Files

### `src/uasset_read/parsers/property_types.py` (342 lines)
- **14 parse_*_property functions**: parse_bool_property, parse_int_property, parse_float_property, parse_str_property, parse_name_property, parse_object_property, parse_soft_object_property, parse_array_property, parse_struct_property, parse_map_property, parse_set_property, parse_enum_property, parse_text_property, parse_delegate_property
- **5 TypeName extraction helpers**: _get_inner_type, _extract_struct_type_from_tag, _extract_map_types_from_tag, _extract_set_type_from_tag, _extract_enum_type_from_tag
- **2 dispatch helpers**: _dispatch_key_parse, _dispatch_value_parse (used by MapProperty)
- **Lazy import pattern**: _get_parse_property_value() and _get_read_property_tag() to avoid circular imports

### `src/uasset_read/parsers/property_parser.py` (289 lines)
- **parse_property_value**: Type dispatch dictionary with 19 property type mappings. Returns None for unknown types (D-05).
- **parse_properties_from_export**: Property loop with boundary validation, MAX_PROPERTY_COUNT guard, SerializationControlExtensions handling, expected_end correction, ObjectProperty resolution via resolve_package_index_to_reference

### `src/uasset_read/parsers/__init__.py` (51 lines)
- Flat exports of all 16 public functions (per D-03)
- __all__ contains exactly 16 names

### `src/uasset_read/serializers/object_resources.py` (modified)
- Added `resolve_package_index_to_reference` and `_resolve_class_name` functions (Rule 3 deviation)

## Verification Results

All success criteria verified:
- [x] 14 parse_*_property functions exist in parsers/property_types.py
- [x] 5 _extract_*_from_tag helpers exist in parsers/property_types.py
- [x] parse_property_value dispatcher with type_dispatch dict exists in parsers/property_parser.py
- [x] parse_properties_from_export with boundary validation exists in parsers/property_parser.py
- [x] parsers/__init__.py exports all 16 public functions (per D-03)
- [x] Unknown property types return None (D-05) — verified with UnknownProperty test
- [x] No circular imports (TYPE_CHECKING + lazy imports used)
- [x] parse_property_value signature: (tag, archive, name_map, export_map, summary=None, depth=0) (D-08)
- [x] All 411 existing tests pass, 47 skipped

TypeName extraction helpers verified:
- `_extract_struct_type_from_tag("StructProperty(/Script/CoreUObject.Vector)")` → `"Vector"`
- `_extract_map_types_from_tag("MapProperty(IntProperty,StrProperty)")` → `("IntProperty", "StrProperty")`
- `_extract_set_type_from_tag("SetProperty(IntProperty)")` → `"IntProperty"`
- `_extract_enum_type_from_tag("EnumProperty(/Script/Game.EWalletState)")` → `"EWalletState"`

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Added resolve_package_index_to_reference to serializers/object_resources.py**
- **Found during:** Task 2
- **Issue:** Plan imports `resolve_package_index_to_reference` from `uasset_read.serializers.object_resources`, but the function only existed in `uasset_read.py` (not migrated to serializers package)
- **Fix:** Added `resolve_package_index_to_reference` and `_resolve_class_name` helper to `src/uasset_read/serializers/object_resources.py` as equivalent migration from uasset_read.py lines 991-1073
- **Files modified:** src/uasset_read/serializers/object_resources.py
- **Commit:** 76f51b2

## Threat Flags

| Flag | File | Description |
|------|------|-------------|
| threat_flag:depth-limit | parsers/property_types.py | MAX_DEPTH=5 for struct, MAX_DEPTH=10 for array — prevents stack overflow DoS (T-30-04, T-30-05) |
| threat_flag:loop-limit | parsers/property_parser.py | MAX_PROPERTY_COUNT=10,000 guard in property loop — prevents infinite loop DoS (T-30-06) |
| threat_flag:boundary | parsers/property_parser.py | expected_end = start_pos + tag.size validation with seek correction — prevents boundary tampering (T-30-08) |
| threat_flag:size-validation | parsers/property_parser.py | tag.size validated against remaining property data before parsing — prevents oversized reads (T-30-08) |
