---
phase: "059"
plan: "03"
type: execute
wave: 2
subsystem: cpp_gen
tags: [constructor, formatter, cpp-generation]
dependency_graph:
  requires: [59-01/cpp_constructor_ir_builder, 59-02/cpp_default_value_formatter]
  provides: [format_cpp_constructor, build_constructor_sections, extract_cpp_constructor]
  affects: [extract_cpp_skeleton, cpp_gen/__init__]
tech-stack:
  added: [cpp_constructor_formatter module]
  patterns: [IR-driven code generation, topological sort, section-based assembly]
key-files:
  created:
    - src/uasset_read/cpp_gen/cpp_constructor_formatter.py
    - tests/test_cpp_gen/test_cpp_constructor_formatter.py
    - tests/test_cpp_gen/test_cpp_constructor_integration.py
  modified:
    - src/uasset_read/cpp_gen/__init__.py
    - src/uasset_read/cpp_gen/extract_cpp_skeleton.py
decisions:
  - "Normalized relative_scale3d -> relative_scale for format_cpp_transform compatibility (D-1)"
  - "Normalized dict-based transforms to VectorValue/RotatorValue objects (D-2)"
  - "Used Super::ClassName() unconditionally per D-59-05"
metrics:
  duration: "~30min"
  tests_added: 42
  tests_total: 153
  completed: 2026-05-18
---

# Phase 59 Plan 03: C++ Constructor Text Formatter Summary

**One-liner:** IR-driven C++ constructor text generation with section-based assembly, topological sort for component ordering, and InputAction LoadObject support.

## Tasks Completed

### Task 1: 构造函数文本格式化器 (D-59-04, D-59-05)

**File:** `src/uasset_read/cpp_gen/cpp_constructor_formatter.py`

Created module with:

- **`build_constructor_sections(ir)`**: Categorizes constructor IR into 5 sections:
  - `creation`: CreateDefaultSubobject calls (topologically sorted)
  - `attach`: SetupAttachment calls (with/without socket names)
  - `transform`: SetRelativeLocationAndRotation/Location/Rotation/Scale3D calls
  - `property`: Scalar property assignments
  - `load_object`: LoadObject<UInputAction> calls

- **`format_cpp_constructor(ir)`**: Assembles full constructor text:
  - `ClassName::ClassName()` signature
  - `: Super::ClassName()` init list (unconditional, D-59-05)
  - Sections in order, blank line between, empty sections skipped
  - 4-space indentation

- **`_topological_sort_creations()`**: Kahn's algorithm for component creation ordering (T-059-06)

- **`_normalize_transform_keys()`**: Fixes key type mismatch:
  - `relative_scale3d` -> `relative_scale` (format_cpp_transform expects different key)
  - Dict-based location/rotation -> VectorValue/RotatorValue objects

### Task 2: 集成到 extract_cpp_class_skeleton 和 golden-path 测试

**Modified:** `src/uasset_read/cpp_gen/extract_cpp_skeleton.py`
- Added `extract_cpp_constructor()` convenience function
- Integrated `format_cpp_constructor()` into `extract_cpp_class_skeleton()` (stores in `ir.constructor["constructor_text"]`)

**Modified:** `src/uasset_read/cpp_gen/__init__.py`
- Exported `build_constructor_sections`, `format_cpp_constructor`, `extract_cpp_constructor`

**Tests:**
- `test_cpp_constructor_formatter.py`: 35 unit tests
- `test_cpp_constructor_integration.py`: 7 golden-path integration tests
- Full suite: 153 tests pass

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Functionality] Transform value type normalization**
- **Found during:** Task 1 implementation + integration test
- **Issue:** `build_transform_assignments` stores raw dicts for transform values, but `format_cpp_transform` expects `VectorValue`/`RotatorValue` typed objects. Additionally, it stores `relative_scale3d` key but `format_cpp_transform` reads `relative_scale` key.
- **Fix:** Added `_normalize_transform_keys()` helper in `cpp_constructor_formatter.py` that converts dict-based values to typed objects and renames the scale key.
- **Files modified:** `src/uasset_read/cpp_gen/cpp_constructor_formatter.py`

## Decisions Made

| # | Decision | Reason |
|---|----------|--------|
| D-1 | Normalize `relative_scale3d` -> `relative_scale` | `format_cpp_transform` reads `relative_scale` but `build_transform_assignments` stores `relative_scale3d` |
| D-2 | Convert dict transforms to VectorValue/RotatorValue | `format_cpp_transform` accesses `.x`, `.y`, `.z` attributes (typed objects), not dict keys |

## Threat Flags

| Flag | File | Description |
|------|------|-------------|
| threat_flag:injection | cpp_constructor_formatter.py | String values passed to TEXT() are escaped via _escape_cpp_string (T-059-05) |
| threat_flag:ordering | cpp_constructor_formatter.py | Topological sort ensures parent components created before children (T-059-06) |
| threat_flag:injection | cpp_constructor_formatter.py | InputAction asset_path validated against /Game/... pattern (T-059-07) |

## Self-Check: PASSED

All created files exist, all 153 tests pass, commit `503f6c2` verified.
