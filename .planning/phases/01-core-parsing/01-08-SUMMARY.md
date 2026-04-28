---
phase: 01-core-parsing
plan: 08
subsystem: core-parsing
tags: [gap-closure, ue4, localization, name-hash, bug-fix]
requires: [CORE-01, CORE-04, CORE-05]
provides: [UE4-file-parsing, Lyra-file-support]
affects: [uasset_read.py, tests/test_uasset_read.py]
tech-stack:
  added:
    - LocalizationId FString field in PackageFileSummary
    - GatherableTextData Count/Offset fields in PackageFileSummary
    - Name hash bytes (4 bytes) after each FString for UE4 >= 502
    - SoftObjectPaths conditional (UE5 only)
  patterns:
    - UE4 version-gated field reading
    - FNameEntrySerialized format (FString + hash bytes)
key-files:
  created: []
  modified:
    - uasset_read.py: PackageFileSummary fields, read_package_summary(), read_name_table()
    - tests/test_uasset_read.py: create_test_uasset helper, test_ue4_total_header_size_at_correct_position, test_real_lyra_character_default_file
decisions:
  - LocalizationId/GatherableTextData only for UE4 files (legacy > -8)
  - SoftObjectPaths only for UE5 files (legacy <= -8)
  - Name hash bytes for UE4 >= VER_UE4_NAME_HASHES_SERIALIZED (502)
metrics:
  duration: ~45 minutes
  tasks_completed: 5
  files_modified: 2
  tests_added: 3
  tests_passed: 28
completed_date: 2026-04-28T06:00:00Z
---

# Phase 1 Plan 08: LocalizationId and GatherableTextData Gap Closure Summary

**One-liner:** Fixed UE4 file parsing by adding LocalizationId, GatherableTextData fields, SoftObjectPaths conditional, and name table hash bytes - Lyra Character_Default.uasset now parses successfully.

## Context

VERIFICATION.md identified that Lyra Character_Default.uasset (UE4 file, legacy=-7, UE4 v521) failed parsing due to missing LocalizationId and GatherableTextData fields in header. The parser read garbage values for ImportOffset (910241842 instead of 4776), blocking ImportMap/ExportMap parsing.

## Tasks Completed

| Task | Name | Status | Commit |
|------|------|--------|--------|
| 1 | Add LocalizationId and GatherableTextData fields to PackageFileSummary | COMPLETE | 817e412 |
| 2 | Read LocalizationId and GatherableTextData in read_package_summary() | COMPLETE | 5f4e2eb |
| 3 | Update create_test_uasset helper to emit fields for UE4 files | COMPLETE | 5f4e2eb |
| 4 | Add test for UE4 LocalizationId field parsing | COMPLETE | 5f4e2eb |
| 5 | Add real Lyra file parsing test | COMPLETE | 5c5cafa |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] SoftObjectPaths was read for UE4 files (should be UE5 only)**
- **Found during:** Task 2 - Lyra file test failed with UTF-16 error
- **Issue:** Parser read SoftObjectPaths (8 bytes) for UE4 files, shifting position
- **Fix:** Added conditional - only read SoftObjectPaths for UE5 files (legacy <= -8)
- **Files modified:** uasset_read.py lines 488-496
- **Commit:** 5c5cafa

**2. [Rule 1 - Bug] Name table hash bytes not read for UE4 >= 502**
- **Found during:** Task 5 - Lyra file parsing showed UTF-16 error at position 487
- **Issue:** UE4 >= VER_UE4_NAME_HASHES_SERIALIZED (502) has 4-byte hash suffix after each FString
- **Fix:** read_name_table now reads 4 hash bytes after each FString for UE4 >= 502
- **Files modified:** uasset_read.py read_name_table function
- **Commit:** 5c5cafa

**3. [Rule 3 - Blocking] Synthetic tests needed hash bytes**
- **Found during:** After name hash fix, synthetic tests failed
- **Issue:** create_test_uasset didn't emit hash bytes for UE4 >= 502
- **Fix:** Updated helper to emit 4-byte hash after each name for UE4 >= 502
- **Files modified:** tests/test_uasset_read.py create_test_uasset
- **Commit:** 5c5cafa

**4. [Rule 3 - Blocking] Manual test file missing UE4 fields**
- **Found during:** test_ue4_total_header_size_at_correct_position failed
- **Issue:** Manual file creation in test didn't include LocalizationId, GatherableTextData, or hash bytes
- **Fix:** Updated test to emit all UE4 fields correctly
- **Files modified:** tests/test_uasset_read.py
- **Commit:** 5c5cafa

## Key Technical Decisions

### UE Version Constants Discovered

From UE 5.7 source ObjectVersion.h:
- VER_UE4_NAME_HASHES_SERIALIZED = 502 (name hashes after FString)
- VER_UE4_ADDED_PACKAGE_SUMMARY_LOCALIZATION_ID = 514
- VER_UE4_SERIALIZE_TEXT_IN_PACKAGES = 457 (GatherableTextData)

### Field Reading Logic

| Field | UE4 (legacy > -8) | UE5 (legacy <= -8) |
|-------|-------------------|--------------------|
| SoftObjectPaths | NO | YES |
| LocalizationId | YES (UE4 >= 514) | NO |
| GatherableTextData | YES (UE4 >= 457) | NO |
| Name Hash Bytes | YES (UE4 >= 502) | NO |

### Name Table Format

UE4 >= 502 uses FNameEntrySerialized format:
- FString (int32 length + UTF-8 data + null terminator)
- 4 bytes hash (NonCasePreservingHash uint16 + CasePreservingHash uint16)

## Verification Results

### Lyra Character_Default.uasset

```
Success: True
NameMap count: 129
ImportMap count: 20
ExportMap count: 35
LocalizationId: 20A614D64ED8D59F9004C9AAB041067E
ImportOffset: 4776
ExportOffset: 3516
```

All values match VERIFICATION.md expected values. ImportMap and ExportMap correctly populated.

### Test Results

All 28 tests pass including:
- test_real_lyra_character_default_file (integration test)
- test_ue4_localization_id_field_reading (field validation)
- test_ue4_total_header_size_at_correct_position (manual file test)

## Files Modified

### uasset_read.py

1. PackageFileSummary dataclass: Added localization_id, gatherable_text_data_count, gatherable_text_data_offset fields
2. read_package_summary(): 
   - SoftObjectPaths conditional (UE5 only)
   - LocalizationId reading for UE4 files
   - GatherableTextData reading for UE4 files
3. read_name_table(): Added hash bytes reading for UE4 >= 502

### tests/test_uasset_read.py

1. create_test_uasset: 
   - SoftObjectPaths conditional (UE5 only)
   - LocalizationId/GatherableTextData emission for UE4
   - Name hash bytes emission for UE4 >= 502
2. test_ue4_total_header_size_at_correct_position: Updated manual file creation
3. test_real_lyra_character_default_file: New integration test
4. test_ue4_localization_id_field_reading: New field validation test

## Success Criteria Met

1. All tests pass (existing + new) - 28/28 passed
2. Lyra Character_Default.uasset parses successfully - VERIFIED
3. LocalizationId field populated with GUID string - "20A614D64ED8D59F9004C9AAB041067E"
4. ImportOffset=4776, ExportOffset=3516 (valid values) - VERIFIED
5. ImportMap and ExportMap populate correctly - 20 imports, 35 exports

## Self-Check: PASSED

- All files exist and modified correctly
- All commits in git log (817e412, 5f4e2eb, 5c5cafa)
- All tests pass (28/28)
- Lyra file parses with correct values

---
*Completed: 2026-04-28T06:00:00Z*
*Executor: Claude (gsd-execute-phase)*