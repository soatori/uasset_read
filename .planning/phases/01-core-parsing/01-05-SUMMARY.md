---
phase: 01-core-parsing
plan: 05
subsystem: core-parser
tags: [bug-fix, package-name, inline-names, gap-closure, lyra]
dependencies:
  requires: []
  provides: [CORE-01-PackageName, CORE-01-NameOffset]
  affects: [uasset_read.py, tests/test_uasset_read.py]
tech_stack:
  added: [package_name field in PackageFileSummary, PackageName FString reading]
  patterns: [sequential header field reading, version-independent NameOffset]
key_files:
  created: []
  modified:
    - path: uasset_read.py
      changes: [package_name field in PackageFileSummary, PackageName FString reading, removed inline names branch]
    - path: tests/test_uasset_read.py
      changes: [test_legacy_minus_seven_ue4_521, test_package_name_field_reading, create_test_uasset PackageName emission]
decisions:
  - id: D-01-05-01
    choice: Read PackageName FString after CustomVersions, before PackageFlags
    rationale: Matches UE 5.7 PackageFileSummary.cpp line 258 serialization order
  - id: D-01-05-02
    choice: Remove inline names branch, always read NameOffset for legacy < 0
    rationale: All UE4/UE5 files (legacy -2 to -9) have NameOffset; inline names only for UE3 (legacy >= 0)
metrics:
  duration_minutes: 12
  tasks_completed: 4
  tests_passed: 19
  files_modified: 2
---

# Phase 01 Plan 05: PackageName and Inline Names Gap Closure Summary

## One-liner

Fixed two blocker bugs preventing real UE5 file parsing: added missing PackageName FString field reading and removed incorrect inline names condition that triggered for legacy=-7 (Lyra files).

## What Was Done

### Problem

During UAT/REVIEW testing with real Lyra UE5 files (legacy=-7, UE4 v521), the parser failed with "Cannot read X bytes" errors. Two root causes identified:

1. **Missing PackageName FString field**: Parser jumped from CustomVersions directly to PackageFlags, skipping the PackageName FString (9 bytes: 4 length + 5 "None\x00"). This offset all subsequent field reads.

2. **Incorrect inline names condition**: Condition `legacy >= -5` incorrectly triggered inline names handling for legacy=-7 files. UE source shows NameOffset is ALWAYS present for modern files (legacy < 0).

### Solution

1. Added PackageName FString reading after CustomVersions (line 258 in UE source)
2. Removed the incorrect inline names branch entirely - NameOffset always read for UE4/UE5 files

### UE Source Reference

UE 5.7 PackageFileSummary.cpp:
```cpp
// Line 258 - PackageName is FString, NOT FName
Record << SA_VALUE(TEXT("PackageName"), Sum.PackageName);

// Line 265 - PackageFlags after PackageName
Record << SA_VALUE(TEXT("PackageFlags"), Sum.PackageFlags);

// Line 278 - NameCount + NameOffset ALWAYS serialized for modern files
Record << SA_VALUE(TEXT("NameCount"), Sum.NameCount) << SA_VALUE(TEXT("NameOffset"), Sum.NameOffset);
// No conditional - NameOffset always present for legacy < 0
```

## Tasks Completed

| Task | Name | Status | Commit | Files |
|------|------|--------|--------|-------|
| 1 | Add PackageName FString field reading | done | 8237388 | uasset_read.py |
| 2 | Fix inline names condition | done | 8237388 | uasset_read.py |
| 3 | Update create_test_uasset helper | done | 48cf2d6 | tests/test_uasset_read.py |
| 4 | Add test for Lyra-like file parsing | done | 48cf2d6 | tests/test_uasset_read.py |

## Key Changes

### uasset_read.py

1. **PackageFileSummary dataclass** (line 286):
   ```python
   package_name: str = ""  # PackageName FString (UE PackageFileSummary.cpp line 258)
   ```

2. **read_package_summary()** - PackageName reading (lines 446-449):
   ```python
   # PackageName (FString) - Reference: UE PackageFileSummary.cpp line 258
   # Note: PackageName is FString type (int32 length + UTF-8 data), NOT FName
   package_name = archive.read_fstring()
   ```

3. **read_package_summary()** - Inline names fix (lines 453-458):
   ```python
   # 名称表处理 (UE PackageFileSummary.cpp line 278)
   # NameCount + NameOffset ALWAYS present for modern UE4/UE5 files (legacy < 0)
   # Inline names format only for UE3 files (legacy >= 0), not supported per D-04
   name_count = archive.read_i32()
   name_offset = archive.read_i32()  # Always read for legacy < 0
   ```

4. **Return statement** (line 506):
   ```python
   package_name=package_name,
   ```

### tests/test_uasset_read.py

1. **create_test_uasset()** - PackageName emission (lines 118-122):
   ```python
   # PackageName (FString) - matches UE PackageFileSummary.cpp line 258
   package_name_bytes = "None".encode('utf-8') + b'\x00'
   f.write(struct.pack(endian_fmt + 'i', len(package_name_bytes)))
   f.write(package_name_bytes)
   ```

2. **create_test_uasset()** - Removed inline names branch:
   - Always emit NameOffset placeholder
   - Always write names at end of header

3. **New tests**:
   - `test_legacy_minus_seven_ue4_521`: Validates Lyra-like file parsing
   - `test_package_name_field_reading`: Validates PackageName field exists

## Verification

- All 19 tests pass (17 existing + 2 new)
- TDD flow followed: RED tests first (failed due to bugs), GREEN implementation
- No regressions in existing functionality
- Synthetic test files now match real UE file structure

## Deviations from Plan

### Auto-fixed Issues

None - plan executed exactly as specified.

### Known Stubs

None - fix is complete and functional.

## Threat Surface

No new threat surface introduced. PackageName reading uses existing `read_fstring()` which validates length against remaining bytes. NameOffset validated by `seek()` boundary checks (D-14).

---
*Completed: 2026-04-28T04:52:37Z*

## Self-Check: PASSED

- FOUND: 01-05-SUMMARY.md
- FOUND: commit 8237388 (parser fix)
- FOUND: commit 48cf2d6 (test update)
- FOUND: uasset_read.py
- FOUND: tests/test_uasset_read.py