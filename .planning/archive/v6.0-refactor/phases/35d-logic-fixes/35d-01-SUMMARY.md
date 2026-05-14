---
phase: "35d"
plan: "01"
subsystem: parsers
tags: [property_types, array, map, remaining_size, MAX_ARRAY_COUNT, comma-splitting]
requires: []
affects: [src/uasset_read/parsers/property_types.py, src/uasset_read/constants.py]
tech-stack:
  added:
    - "MAX_ARRAY_COUNT = 1_000_000 constant in constants.py"
  patterns:
    - "remaining_size = tag.size - 4 — subtract ArrayProperty 4-byte count field from remaining_size tracking"
    - "params.split(',', 1) — first-comma-only split for nested MapProperty type names"
    - "MAX_ARRAY_COUNT validation — separate, more permissive boundary for array element counts"
key-files:
  created: []
  modified:
    - src/uasset_read/parsers/property_types.py
    - src/uasset_read/constants.py
decisions:
  - "D-16: ArrayProperty remaining_size must exclude the 4-byte count field for accurate byte tracking"
  - "D-08: MapProperty type names like StructProperty(/Script/Module.Type) may contain inner commas — use split(',', 1)"
  - "HIGH-07: ArrayProperty element count needs MAX_ARRAY_COUNT (1M) not MAX_PROPERTY_COUNT (10K) — arrays legitimately hold more elements than property loop limits"
metrics:
  duration: null
  completed_date: 2026-05-13
---

# Phase 35d Plan 01: property_types.py Logic Fixes Summary

**One-liner:** Fix ArrayProperty remaining_size byte tracking (subtract 4-byte count), fix MapProperty type name comma splitting (first-comma-only), and add MAX_ARRAY_COUNT boundary validation in `property_types.py`.

## Overview

Fixed three logic issues in `property_types.py`:

- **D-16**: `parse_array_property` used `tag.size` as the remaining size tracker, but the first 4 bytes are consumed by the element count field. Changed to `tag.size - 4` so the dynamic inner_size distribution tracks the actual element data bytes correctly.
- **D-08**: `_extract_map_types_from_tag` used `split(",")` on the inner type string, which would break when type names contain commas (e.g., `StructProperty(/Script/Module.Type)`). Changed to `split(",", 1)` to split only on the first comma.
- **HIGH-07**: ArrayProperty element count used `MAX_PROPERTY_COUNT (10K)` as the upper bound, which is too restrictive — arrays can legitimately hold millions of elements. Added `MAX_ARRAY_COUNT = 1_000_000` in `constants.py` and updated the validation in `parse_array_property`.

## Tasks Executed

| # | Task | Type | Commit | Files Modified |
|---|------|------|--------|----------------|
| 1 | Fix array remaining_size = tag.size - 4 | auto | d23e924 | src/uasset_read/parsers/property_types.py |
| 2 | Fix nested comma splitting in _extract_map_types_from_tag | auto | 2f533e2 | src/uasset_read/parsers/property_types.py |
| 3 | Add MAX_ARRAY_COUNT validation | auto | 2340ecb | src/uasset_read/constants.py, src/uasset_read/parsers/property_types.py |

### Task 1: Fix ArrayProperty remaining_size calculation

**Files modified:** `src/uasset_read/parsers/property_types.py`

**Change:**
- Line 116: `remaining_size = tag.size` → `remaining_size = tag.size - 4  # subtract 4-byte count field`

**Rationale:** `parse_array_property` reads a 4-byte `i32` count field before entering the element loop. The remaining_size tracker must exclude these 4 bytes to accurately distribute remaining bytes across elements via `remaining_size // remaining_count`. Without this fix, the last element would always be assigned 4 extra bytes, causing incorrect parsing.

### Task 2: Fix MapProperty type name comma splitting

**Files modified:** `src/uasset_read/parsers/property_types.py`

**Change:**
- Line 329: `parts = params.split(",")` → `parts = params.split(",", 1)  # split on first comma only`

**Rationale:** UE5 type name format uses `MapProperty(KeyType,ValueType)` where ValueType may contain commas in nested type paths like `StructProperty(/Script/Module.Type,SubType)`. Using `split(",")` would split these inner commas, yielding incorrect type extraction. `split(",", 1)` ensures we only split on the outer comma separator.

### Task 3: Add MAX_ARRAY_COUNT boundary validation

**Files modified:**
- `src/uasset_read/constants.py` (new constant)
- `src/uasset_read/parsers/property_types.py` (import + usage)

**Changes:**
- `constants.py` line 33: added `MAX_ARRAY_COUNT = 1_000_000`
- `property_types.py` line 21: added `MAX_ARRAY_COUNT` to imports
- `property_types.py` lines 110-113: changed validation from `MAX_PROPERTY_COUNT (10K)` to `MAX_ARRAY_COUNT (1M)`

**Rationale:** `MAX_PROPERTY_COUNT (10,000)` is designed for property loop limits (number of tags within a struct/export), not for array element counts. Arrays in UE can legitimately hold hundreds of thousands of elements. Using `MAX_PROPERTY_COUNT` would cause false `ParseError` on valid assets.

## Test Results

- **401 passed, 67 skipped** (excluding pre-existing asset-dependent tests)
- No regressions from changes
- All environment-dependent failures (`test_phase21_verification`, `test_skill_integration`, `test_ue5_pin_integration`, `test_import_map_ue5_condition_fields`, `test_saved_hash`) confirmed pre-existing

## Verification

- [x] Array remaining_size correctly accounts for 4-byte count field
- [x] Map type extraction splits on first comma only
- [x] MAX_ARRAY_COUNT (1M) validation in place for ArrayProperty
- [x] MAX_ARRAY_COUNT constant added to `constants.py`
- [x] Import chain updated

## Deviations from Plan

None — plan executed exactly as described.

## Known Stubs

None.

## Threat Flags

None.

## Self-Check: PASSED

- [x] Commit `d23e924` exists: `fix(35d-01): subtract 4-byte count field from array remaining_size`
- [x] Commit `2f533e2` exists: `fix(35d-01): split map type params on first comma only`
- [x] Commit `2340ecb` exists: `fix(35d-01): add MAX_ARRAY_COUNT validation for ArrayProperty`
- [x] `src/uasset_read/parsers/property_types.py` modified
- [x] `src/uasset_read/constants.py` modified
- [x] Tests pass (401 passed, 67 skipped)
