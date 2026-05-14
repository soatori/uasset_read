---
phase: "35d"
plan: "06"
subsystem: parsers/constants
tags: [dead-code, duplicate-constants, duplicate-functions, cleanup, MED-14, HIGH-08]
requires: []
affects:
  - src/uasset_read/constants.py
  - src/uasset_read/parsers/property_parser.py
  - src/uasset_read/parsers/property_types.py
  - src/uasset_read/__init__.py
tech-stack:
  added: []
  patterns:
    - "UE5_PROPERTY_TAG_COMPLETE_TYPE_NAME = PROPERTY_TAG_COMPLETE_TYPE_NAME — alias pattern for duplicate constants (MED-14)"
    - "Removed duplicate _derive_node_name from property_types.py — single canonical copy in flow_builder.py"
key-files:
  created: []
  modified:
    - src/uasset_read/constants.py
    - src/uasset_read/parsers/property_parser.py
    - src/uasset_read/parsers/property_types.py
    - src/uasset_read/__init__.py
decisions:
  - "MED-14: UE5_PROPERTY_TAG_COMPLETE_TYPE_NAME (1012) same value as PROPERTY_TAG_COMPLETE_TYPE_NAME (1012) — make alias, keep primary as the canonical definition"
  - "MED-14: _derive_node_name had two copies — removed property_types copy, kept flow_builder copy (imported via formatters __init__)"
  - "HIGH-08: Unreachable return None after all dispatch branches in parse_property_value — removed dead code"
metrics:
  duration: null
  completed_date: 2026-05-13
---

# Phase 35d Plan 06: Dead Code & Duplicate Cleanup Summary

**One-liner:** Remove three code quality issues: duplicate `UE5_PROPERTY_TAG_COMPLETE_TYPE_NAME` constant (make alias), unreachable `return None` in `parse_property_value`, and duplicate `_derive_node_name` function in `property_types.py`.

## Overview

Cleaned up three maintenance hazards across 4 files:

- **MED-14 (constants)**: `UE5_PROPERTY_TAG_COMPLETE_TYPE_NAME = 1012` had the same literal value as `PROPERTY_TAG_COMPLETE_TYPE_NAME = 1012`. Changed to an alias referencing the primary constant — ensures they stay in sync and making the primary definition the single source of truth.
- **HIGH-08 (property_parser.py)**: The final `return None  # Fallback D-05` in `parse_property_value` is unreachable because all registered property types are covered by the `elif` dispatch chain, and unknown types already return `None` at the handler-lookup stage (line 79). Removed dead code.
- **MED-14 (duplicate function)**: `_derive_node_name` existed in both `property_types.py` and `flow_builder.py` with identical logic. Removed the `property_types.py` copy and updated the import chain in `__init__.py` to only reference the canonical `flow_builder` version.

## Tasks Executed

| # | Task | Type | Commit | Files Modified |
|---|------|------|--------|----------------|
| 4 | Fix duplicate UE5_PROPERTY_TAG_COMPLETE_TYPE_NAME constant | auto | b7d21c1 | src/uasset_read/constants.py |
| 5 | Remove unreachable return None in property_parser.py | auto | 429e080 | src/uasset_read/parsers/property_parser.py |
| 6 | Remove duplicate _derive_node_name from property_types.py | auto | da50471 | src/uasset_read/parsers/property_types.py, src/uasset_read/__init__.py |

### Task 4: Fix duplicate constant (MED-14)

**Files modified:** `src/uasset_read/constants.py`

**Change:**
- Line 86: `UE5_PROPERTY_TAG_COMPLETE_TYPE_NAME = 1012` → `UE5_PROPERTY_TAG_COMPLETE_TYPE_NAME = PROPERTY_TAG_COMPLETE_TYPE_NAME  # alias (same value 1012)`

**Rationale:** Both constants had the same numeric value (1012). Having separate literal definitions creates a maintenance hazard — if one is updated without the other, they drift silently. Making `UE5_PROPERTY_TAG_COMPLETE_TYPE_NAME` an alias ensures the primary `PROPERTY_TAG_COMPLETE_TYPE_NAME` is the single source of truth.

### Task 5: Remove unreachable code (HIGH-08)

**Files modified:** `src/uasset_read/parsers/property_parser.py`

**Change:**
- Removed line 97: `return None  # Fallback D-05`

**Rationale:** In `parse_property_value`:
1. Line 78-79: `if handler is None: return None` catches all unknown types
2. Lines 82-95: `elif` chain covers every registered property type (Bool, Int, Float, Str, Name, Object, SoftObject, Array, Struct, Map, Set, Enum, Text, Delegate)
3. The final `return None` at line 97 is **unreachable** — no code path reaches it.

Per D-05: returning `None` for unknown types is already handled at the handler-lookup stage.

### Task 6: Remove duplicate function (MED-14)

**Files modified:**
- `src/uasset_read/parsers/property_types.py` (removed function definition)
- `src/uasset_read/__init__.py` (removed duplicate import, updated comment)

**Changes:**
- `property_types.py`: Removed the entire `_derive_node_name` section (lines 447-457)
- `__init__.py` line 247: `from .parsers.property_types import _derive_node_name, ...` → `from .parsers.property_types import ...`
- `__init__.py` line 255-256: Updated comment to remove `_derive_node_name` from pending list

**Rationale:** `_derive_node_name` had two identical copies — one in `property_types.py` (line 451, `Any` typed) and one in `flow_builder.py` (line 25, `UEdGraphNode` typed). The `flow_builder.py` version is typed correctly (`UEdGraphNode`) and is used directly within `flow_builder.py` at 4 call sites. The top-level `__init__.py` already imports `_derive_node_name` from `formatters` (which re-exports from `flow_builder`) at line 219, making the duplicate import from `property_types` at line 247 redundant.

## Test Results

- **401 passed, 67 skipped** (excluding pre-existing asset-dependent tests)
- No regressions from any of the three changes
- All environment-dependent failures confirmed pre-existing

## Verification

- [x] `UE5_PROPERTY_TAG_COMPLETE_TYPE_NAME` is now an alias of `PROPERTY_TAG_COMPLETE_TYPE_NAME`
- [x] No unreachable code remains in `parse_property_value`
- [x] `_derive_node_name` removed from `property_types.py`, only `flow_builder.py` copy remains
- [x] Import chain in `__init__.py` fixed — no duplicate imports
- [x] All existing references to `_derive_node_name` still resolve correctly (via `formatters.__init__` re-export from `flow_builder`)

## Deviations from Plan

None — plan executed exactly as described.

## Known Stubs

None.

## Threat Flags

None.

## Self-Check: PASSED

- [x] Commit `b7d21c1` exists: `fix(35d-06): make UE5_PROPERTY_TAG_COMPLETE_TYPE_NAME an alias`
- [x] Commit `429e080` exists: `fix(35d-06): remove unreachable return None in parse_property_value`
- [x] Commit `da50471` exists: `fix(35d-06): remove duplicate _derive_node_name from property_types`
- [x] `src/uasset_read/constants.py` modified
- [x] `src/uasset_read/parsers/property_parser.py` modified
- [x] `src/uasset_read/parsers/property_types.py` modified
- [x] `src/uasset_read/__init__.py` modified
- [x] Tests pass (401 passed, 67 skipped)
