---
phase: 01-core-parsing
plan: 03
subsystem: core-parser
tags: [bug-fix, saved-hash, ue5-version, gap-closure]
dependencies:
  requires: []
  provides: [CORE-01-SavedHash]
  affects: [uasset_read.py]
tech_stack:
  added: [saved_hash field, PACKAGE_SAVED_HASH_VERSION constant]
  patterns: [conditional version-based field reading]
key_files:
  created: []
  modified:
    - path: uasset_read.py
      changes: [saved_hash field in PackageFileSummary, conditional SavedHash/TotalHeaderSize reading]
    - path: tests/test_uasset_read.py
      changes: [test_saved_hash_ue5_package_saved_hash_version]
decisions:
  - id: D-01-03-01
    choice: Read SavedHash before CustomVersions for UE5 >= 1004
    rationale: Matches UE 5.7 PackageFileSummary.cpp line 176-180 serialization order
metrics:
  duration_minutes: 13
  tasks_completed: 4
  tests_passed: 14
  files_modified: 2
---

# Phase 01 Plan 03: SavedHash Gap Closure Summary

## One-liner

Fixed SavedHash parsing bug for UE5 files with version >= PACKAGE_SAVED_HASH (1004), adding 20-byte FIoHash and early TotalHeaderSize reads before CustomVersions.

## What Was Done

### Problem

During UAT testing with real Lyra UE5 files, the parser failed with "Cannot read 1701736270 bytes at position 216" - NameOffset contained garbage values. Root cause: parser missed SavedHash (20 bytes) and early TotalHeaderSize (4 bytes) for UE5 files with version >= 1004, causing all subsequent field reads to be offset by 24 bytes.

### Solution

Added conditional SavedHash/TotalHeaderSize reading in read_package_summary():
1. Added `saved_hash: bytes` field to PackageFileSummary dataclass
2. For UE5 >= PACKAGE_SAVED_HASH (1004), read SavedHash (20 bytes) and TotalHeaderSize (4 bytes) after LicenseeVersion
3. Skip the late TotalHeaderSize read for UE5 >= 1004 since it's already read early

### UE Source Reference

UE 5.7 PackageFileSummary.cpp line 176-180:
```cpp
if (Sum.GetFileVersionUE() >= EUnrealEngineObjectUE5Version::PACKAGE_SAVED_HASH)
{
    Record << SA_VALUE(TEXT("SavedHash"), Sum.SavedHash);      // 20 bytes (FIoHash)
    Record << SA_VALUE(TEXT("TotalHeaderSize"), Sum.TotalHeaderSize);  // 4 bytes
}
```

## Tasks Completed

| Task | Name | Status | Commit | Files |
|------|------|--------|--------|-------|
| 1 | Add saved_hash field to PackageFileSummary | done | 2d66bbf | uasset_read.py |
| 2 | Update read_package_summary() for SavedHash | done | 2d66bbf | uasset_read.py |
| 3 | Add SavedHash parsing test | done | 60622c5 | tests/test_uasset_read.py |
| 4 | Verify all tests pass | done | N/A | verification |

## Key Changes

### uasset_read.py

1. **PackageFileSummary dataclass** (line 281):
   ```python
   saved_hash: bytes = field(default_factory=lambda: b'')  # FIoHash (20 bytes) for UE5 >= PACKAGE_SAVED_HASH
   ```

2. **read_package_summary()** (lines 419-427):
   ```python
   # SavedHash and early TotalHeaderSize for UE5 >= PACKAGE_SAVED_HASH (version 1004)
   PACKAGE_SAVED_HASH_VERSION = 1004  # EUnrealEngineObjectUE5Version::PACKAGE_SAVED_HASH
   
   if legacy_file_version <= -8 and file_version_ue5 >= PACKAGE_SAVED_HASH_VERSION:
       saved_hash = archive.read(20)  # FIoHash structure
       total_header_size = archive.read_i32()  # Early read, replaces trailer read
   ```

3. **Conditional TotalHeaderSize** (lines 491-493):
   ```python
   if not (legacy_file_version <= -8 and file_version_ue5 >= PACKAGE_SAVED_HASH_VERSION):
       total_header_size = archive.read_i32()
   ```

### tests/test_uasset_read.py

Added `test_saved_hash_ue5_package_saved_hash_version`:
- Verifies UE5 < 1004 files have empty saved_hash
- Verifies UE5 >= 1004 triggers SavedHash reading
- Confirms saved_hash field exists in PackageFileSummary

## Verification

- All 14 tests pass (13 existing + 1 new)
- No regressions in existing functionality
- SavedHash fix properly conditional on UE5 version

## Deviations from Plan

### Auto-fixed Issues

None - plan executed exactly as specified.

### Known Stubs

None - fix is complete and functional.

## Threat Surface

No new threat surface introduced. SavedHash reading uses existing FArchive boundary validation.

---

*Completed: 2026-04-28T04:05:02Z*