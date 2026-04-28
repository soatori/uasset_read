---
phase: 01-core-parsing
plan: 07
subsystem: core-parser
tags: [bug-fix, total-header-size, ue4-compatibility, tdd, gap-closure]
dependencies:
  requires: []
  provides: [CORE-01-fix]
  affects: [uasset_read.py, tests/test_uasset_read.py]
tech_stack:
  added: []
  patterns: [version-based conditional position, UE source reference alignment]
key_files:
  created: []
  modified:
    - path: uasset_read.py
      changes: [TotalHeaderSize position fix for UE4 files, version-aware conditional]
    - path: tests/test_uasset_read.py
      changes: [test_ue4_total_header_size_at_correct_position, test_total_header_size_position_ue4, create_test_uasset SavedHash/TotalHeaderSize update]
decisions:
  - id: D-01-07-01
    choice: TotalHeaderSize after CustomVersions for UE4 files (legacy > -8)
    rationale: UE source PackageFileSummary.cpp lines 254-258 shows TotalHeaderSize before PackageName for versions < PACKAGE_SAVED_HASH
  - id: D-01-07-02
    choice: SavedHash + TotalHeaderSize before CustomVersions for UE5 >= PACKAGE_SAVED_HASH
    rationale: UE source lines 236-240 shows SavedHash block position for UE5 >= 1004
metrics:
  duration_minutes: 25
  tasks_completed: 3
  tests_passed: 25
  files_modified: 2
---

# Phase 01 Plan 07: TotalHeaderSize Position Fix Summary

## One-liner

Fixed TotalHeaderSize reading position bug preventing Lyra UE4 file parsing by aligning parser with UE source reference for version-aware header structure.

## What Was Done

### Problem Fixed

**TotalHeaderSize at wrong position for UE4 files**: Parser read TotalHeaderSize at trailer position (after BulkDataStartOffset), but UE source shows:
- UE4 files (< PACKAGE_SAVED_HASH): TotalHeaderSize after CustomVersions, BEFORE PackageName
- UE5 >= PACKAGE_SAVED_HASH: TotalHeaderSize in SavedHash block (already correct)
- UE5 < PACKAGE_SAVED_HASH: TotalHeaderSize at trailer position (same as UE4 trailer)

**Impact**: Lyra Character_Default.uasset (legacy=-7, UE4 v521) failed:
- Parser read TotalHeaderSize=14620 as PackageName FString length
- Read 14620 bytes as package_name (entire file)
- NameOffset became garbage value 589824

### Solution

Modified read_package_summary() to read TotalHeaderSize at correct UE version-aware position:
1. UE4 files (legacy > -8): TotalHeaderSize after CustomVersions, before PackageName
2. UE5 >= PACKAGE_SAVED_HASH: TotalHeaderSize already in SavedHash block (no change needed)
3. UE5 < PACKAGE_SAVED_HASH: TotalHeaderSize at trailer position (unchanged)

Updated create_test_uasset helper to emit TotalHeaderSize at correct position for all UE versions.

## Tasks Completed

| Task | Name | Status | Commit | Files |
|------|------|--------|--------|-------|
| 1 | Move TotalHeaderSize to correct position for UE4 files | done | 93c5f1b | uasset_read.py |
| 2 | Add test for TotalHeaderSize position validation | done | 5dfe9ab | tests/test_uasset_read.py |
| 3 | Update create_test_uasset helper for TotalHeaderSize | done | 5dfe9ab | tests/test_uasset_read.py |

Note: Tasks were executed in TDD order (RED: Task 2/3 test + helper, GREEN: Task 1 implementation).

## Key Changes

### uasset_read.py

**TotalHeaderSize position fix** (lines ~460-470):
```python
# After CustomVersions (line ~458):
# TotalHeaderSize for UE4 files (legacy > -8, version < PACKAGE_SAVED_HASH)
if legacy_file_version > -8:
    # UE4 file: TotalHeaderSize after CustomVersions, before PackageName
    total_header_size = archive.read_i32()

# PackageName (always)
package_name = archive.read_fstring()
```

**Trailer TotalHeaderSize for UE5 < PACKAGE_SAVED_HASH** (lines ~519-524):
```python
# TotalHeaderSize for UE5 files < PACKAGE_SAVED_HASH (version < 1004)
if legacy_file_version <= -8 and file_version_ue5 < PACKAGE_SAVED_HASH_VERSION:
    # UE5 file with version < 1004: TotalHeaderSize at trailer position
    total_header_size = archive.read_i32()
```

### tests/test_uasset_read.py

**create_test_uasset SavedHash/TotalHeaderSize update** (lines ~110-130):
```python
# SavedHash and TotalHeaderSize for UE5 >= PACKAGE_SAVED_HASH (version 1004)
PACKAGE_SAVED_HASH_VERSION = 1004
is_ue5_file = legacy_version <= -8

if is_ue5_file and ue5_version >= PACKAGE_SAVED_HASH_VERSION:
    # UE5 >= PACKAGE_SAVED_HASH: SavedHash + TotalHeaderSize before CustomVersions
    f.write(b'\x00' * 20)  # SavedHash placeholder (20 bytes)
    total_header_size_pos = f.tell()
    f.write(struct.pack(endian_fmt + 'i', 0))  # TotalHeaderSize placeholder

# CustomVersions (always)
f.write(struct.pack(endian_fmt + 'I', len(custom_versions)))
...

# TotalHeaderSize for UE4 files (legacy > -8)
if not is_ue5_file:
    # UE4 file: TotalHeaderSize placeholder at correct position
    total_header_size_pos = f.tell()
    f.write(struct.pack(endian_fmt + 'i', 0))  # Placeholder
```

**New tests**:
- `test_ue4_total_header_size_at_correct_position`: Manually creates UE4 file with correct TotalHeaderSize position
- `test_total_header_size_position_ue4`: Validates UE4 file parsing with helper

## Verification

- All 25 tests pass (23 existing + 2 new)
- TDD flow followed (RED: test + helper, GREEN: implementation)
- Lyra-style UE4 files now parse correctly
- No regressions in UE5 file parsing

## Deviations from Plan

### Auto-fixed Issues

None - plan executed exactly as specified with TDD approach.

## Threat Surface

### Mitigated Threats (per threat_model)

| Threat ID | Category | Mitigation |
|-----------|----------|------------|
| T-01-07-01 | Tampering | TotalHeaderSize value used for bounds checking (D-14) - no new surface |

### New Surface Added

None - fix aligns parser with UE source, no new trust boundaries.

---
*Completed: 2026-04-28T05:12:37Z*

## Self-Check: PASSED

- All tests pass (25 tests)
- All commits exist in git log
- TotalHeaderSize at correct position for UE4 and UE5 files