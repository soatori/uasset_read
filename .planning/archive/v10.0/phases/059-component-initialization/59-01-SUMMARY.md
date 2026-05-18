---
phase: "059"
plan: "01"
subsystem: "cpp_gen"
tags: ["cpp", "ir-builder", "constructor"]
dependency_graph:
  requires: ["CppClassIR from cpp_json_ir.py", "extract_components from component_extractor.py"]
  provides: ["CppComponentCreation", "CppComponentAssignment", "CppDefaultValue", "build_component_creations", "build_component_assignments", "build_default_values", "build_transform_assignments"]
  affects: ["extract_cpp_skeleton.py", "CppClassIR.constructor"]
tech_stack:
  added: ["cpp_constructor_ir_builder.py"]
  patterns: ["dataclass IR models", "builder functions"]
key_files:
  created:
    - src/uasset_read/cpp_gen/cpp_constructor_ir_builder.py
    - tests/test_cpp_gen/test_cpp_constructor_ir_builder.py
    - tests/test_cpp_gen/__init__.py
  modified:
    - src/uasset_read/cpp_gen/extract_cpp_skeleton.py
decisions:
  - "UInputAction* types skipped in component_creations, marked needs_load_object=True in default_values (D-59-06)"
  - "Transform data flows through IR default_values with is_method_call=True, method_type='transform' (Blocker 2 fix)"
  - "components variable extracted from result.components with None-safe fallback"
  - "_sanitize_value implements T-059-02 injection prevention"
metrics:
  duration: "~15min"
  completed: "2026-05-18"
  tests: 50 new + 290 existing = 340 total passed
---

# Phase 059 Plan 01: cpp_constructor_ir_builder Summary

**One-liner:** CppComponentCreation, CppComponentAssignment, CppDefaultValue data models and 4 builder functions that populate CppClassIR.constructor from blueprint component/variable data, integrated into extract_cpp_skeleton.py.

## What Was Built

### Data Models (`cpp_constructor_ir_builder.py`)

1. **CppComponentCreation** — Represents `CreateDefaultSubobject<T>(TEXT("name"))` calls
2. **CppComponentAssignment** — Represents `SetupAttachment(parent, socket)` calls
3. **CppDefaultValue** — Represents property assignments with `method_type` and `needs_load_object` fields

### Builder Functions

1. **build_component_creations(ir)** — Extracts component creations from `ir.properties` (skips `UInputAction*`)
2. **build_component_assignments(components)** — Extracts attach relationships from components data
3. **build_default_values(ir, blueprint_vars)** — Extracts default values; InputAction marked `needs_load_object=True`
4. **build_transform_assignments(ir, components)** — Extracts transform data with `is_method_call=True, method_type="transform"`

### Integration

`extract_cpp_class_skeleton()` now calls all 4 builder functions to populate `ir.constructor` before returning.

## Deviations from Plan

None - plan executed exactly as written.

### Bug Fix (Deviation Rule 1)

**Issue:** `components` variable was referenced but not defined in `extract_cpp_class_skeleton()`.
**Fix:** Added `components = result.components or []` before calling builder functions.
**File:** `src/uasset_read/cpp_gen/extract_cpp_skeleton.py` line 117

## Security (T-059-02)

Implemented `_sanitize_value()` to strip `;`, `{`, `}`, `//` from default value strings, preventing C++ code injection via blueprint variable values.

## Tests

50 new unit tests covering all data models, builder functions, sanitization, and integration.

```
tests/test_cpp_gen/test_cpp_constructor_ir_builder.py: 50 passed
Full cpp_gen suite: 340 passed (no regressions)
```

## Self-Check: PASSED

- All created files exist
- All 50 new tests pass
- All 290 existing tests pass (no regressions)
- Commit hash: 4613bfc
