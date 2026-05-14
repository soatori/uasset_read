---
phase: "35b"
plan: "01"
subsystem: "serialization"
tags: [ue5, bool, pintype, archive]
requires: []
provides: [read_bool_ue5, ue5-bool-serialization]
affects: [archive.py, graph.py]
tech_stack:
  added: [read_bool_ue5 method, conditional bool reading pattern]
  patterns: [ue4/ue5 serialization version branching]
key_files:
  created: [tests/test_ue5_bool_serialization.py]
  modified: [src/uasset_read/archive.py, src/uasset_read/serializers/graph.py]
decisions: [UE5 PinType bools use 1-byte serialization, conditional read pattern maintains UE4 compatibility]
metrics:
  duration: "2 minutes"
  completed_date: "2026-05-13"
  tasks: 3
  tests: 6 passed
  commits: 3
---

# Phase 35b Plan 01: UE5 Bool Serialization Fix Summary

## One-liner

Added read_bool_ue5() method (1-byte) and updated FEdGraphPinType serialization to use conditional bool reading for UE5/UE4 version branching.

## Description

UE5 uses 1-byte (uint8) bool serialization for FEdGraphPinType fields, while UE4 uses 4-byte (uint32). The existing read_bool() method was designed for UE4, causing position misalignment when parsing UE5 blueprint pins.

## Changes Made

### Task 1: Add read_bool_ue5() to FArchive (commit: b9839f2)

Added new method `read_bool_ue5()` in `archive.py` after `read_bool()`:
```python
def read_bool_ue5(self) -> bool:
    """Read UE5 bool (serialized as uint8, 1 byte)."""
    return self.read_u8() != 0
```

### Task 2: Update read_ed_graph_pin_type() for UE5 (commit: 7252a5e)

Updated 4 bool field reads in `graph.py` custom serialization branch to use conditional reading:
- L115: `is_reference` - uses read_bool_ue5() for UE5
- L116: `is_weak_pointer` - uses read_bool_ue5() for UE5
- L128: `is_const` - uses read_bool_ue5() for UE5
- L134: `is_uobject_wrapper` - uses read_bool_ue5() for UE5

Pattern: `archive.read_bool_ue5() if summary.file_version_ue5 > 0 else archive.read_bool()`

### Task 3: UE5 bool serialization tests (commit: a110f9e)

Created `tests/test_ue5_bool_serialization.py` with 6 tests:
- Byte consumption verification (1 vs 4 bytes)
- True/False return for 0x00, 0x01, 0xFF
- Sequence reading test

## Verification

- `tests/test_ue5_bool_serialization.py`: 6 passed
- Full test suite: 325 passed, 69 skipped, 1 pre-existing failure (skill directory)

## Deviations from Plan

### Auto-fixed Issues

None - plan executed exactly as written.

### Out of Scope

- Pre-existing skill directory test failure (test_skill_integration.py) - unrelated to this task
- VERIFICATION.md modification in worktree state - pre-existing, not committed

## Commits

| Commit | Message |
|--------|---------|
| b9839f2 | feat(35b-01): add read_bool_ue5() to FArchive |
| 7252a5e | feat(35b-01): use read_bool_ue5() for UE5 FEdGraphPinType bools |
| a110f9e | test(35b-01): add UE5 bool serialization unit tests |

## Self-Check: PASSED

- archive.py: read_bool_ue5() method exists
- graph.py: 4 conditional bool reads implemented
- tests/test_ue5_bool_serialization.py: file exists, 6 tests pass
- Commits verified: b9839f2, 7252a5e, a110f9e present in git log