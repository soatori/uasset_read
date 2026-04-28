---
phase: 01-core-parsing
plan: 06
subsystem: core-parser
tags: [bug-fix, security, bounds-validation, tdd, gap-closure]
dependencies:
  requires: []
  provides: [SAFE-01, SAFE-02]
  affects: [uasset_read.py, tests/test_uasset_read.py]
tech_stack:
  added: [MAX_NAME_COUNT, MAX_IMPORT_COUNT, MAX_EXPORT_COUNT, MAX_CUSTOM_VERSIONS constants, UTF-16 overflow check]
  patterns: [bounds validation, overflow prevention, version-based conditional]
key_files:
  created: []
  modified:
    - path: uasset_read.py
      changes: [script_serial condition fix, bounds validation constants, UTF-16 overflow check]
    - path: tests/test_uasset_read.py
      changes: [test_ue4_export_no_script_serialization, test_name_count_bounds_validation, test_export_count_bounds_validation, test_utf16_length_overflow]
decisions:
  - id: D-01-06-01
    choice: Check legacy_file_version <= -8 instead of file_version_ue5 >= 0 for script_serial fields
    rationale: UE4 files (legacy > -8) have file_version_ue5=0, so ue5_version >= 0 was always True
  - id: D-01-06-02
    choice: Set MAX_NAME_COUNT=10M, MAX_IMPORT/EXPORT_COUNT=1M
    rationale: Real UE files have counts in hundreds/thousands; these bounds prevent DoS
  - id: D-01-06-03
    choice: Reject UTF-16 strings > 10M bytes
    rationale: Prevents -length * 2 overflow (4GB read for INT_MIN)
metrics:
  duration_minutes: 15
  tasks_completed: 5
  tests_passed: 23
  files_modified: 2
---

# Phase 01 Plan 06: Critical and Warning Issues Fix Summary

## One-liner

Fixed three security/robustness issues: correct UE4 script_serial skip, array count bounds validation, and UTF-16 length overflow prevention.

## What Was Done

### Problems Fixed

1. **CR-02: Script serialization fields always read**: Condition `file_version_ue5 >= UE5_VERSION_MIN` (where MIN=0) was always True, causing parser to read 16 extra bytes for UE4 files (legacy > -8). This caused parse errors for real UE4 files like Lyra assets.

2. **WR-01: No bounds validation on array counts**: Counts read directly into loops without validation, potential DoS risk from malicious files with huge counts.

3. **WR-02: Integer overflow in UTF-16 string length**: Calculation `-length * 2` could overflow for extreme values like INT_MIN, potentially causing 4GB read attempt.

### Solutions

1. Changed condition from `file_version_ue5 >= UE5_VERSION_MIN` to `legacy_file_version <= -8` for reading script_serial fields.

2. Added bounds validation constants (MAX_NAME_COUNT=10M, MAX_IMPORT/EXPORT_COUNT=1M, MAX_CUSTOM_VERSIONS=10K) and validation checks in read_package_summary().

3. Added UTF-16 length overflow check: reject strings with length > 10M bytes.

## Tasks Completed

| Task | Name | Status | Commit | Files |
|------|------|--------|--------|-------|
| 1 | Fix script serialization field condition | done | 862a63c | uasset_read.py, tests/test_uasset_read.py |
| 2 | Add bounds validation constants and checks | done | 28b3994 | uasset_read.py, tests/test_uasset_read.py |
| 3 | Add UTF-16 string length overflow check | done | 27db5c6 | uasset_read.py, tests/test_uasset_read.py |
| 4 | Add tests for bounds validation | merged | 28b3994 | tests/test_uasset_read.py |
| 5 | Add test for UE4 script serialization skip | merged | 862a63c | tests/test_uasset_read.py |

Note: Tasks 4 and 5 were incorporated into Tasks 2 and 1 during TDD execution (tests written before implementation).

## Key Changes

### uasset_read.py

1. **Constants section** (lines 32-36):
   ```python
   # Bounds validation constants (WR-01 mitigation)
   MAX_NAME_COUNT = 10_000_000      # Maximum name table entries
   MAX_IMPORT_COUNT = 1_000_000     # Maximum import table entries
   MAX_EXPORT_COUNT = 1_000_000     # Maximum export table entries
   MAX_CUSTOM_VERSIONS = 10_000     # Maximum custom version entries
   ```

2. **read_export_map() - CR-02 fix** (lines 634-644):
   ```python
   # CR-02 fix: Check if file is actually UE5 (legacy <= -8), NOT ue5_version >= 0
   # UE4 files (legacy > -8) don't have these fields - file_version_ue5 stays at 0
   is_ue5_file = summary.legacy_file_version <= -8

   if is_ue5_file:
       script_serial_size = archive.read_i64()
       script_serial_offset = archive.read_i64()
   else:
       script_serial_size = 0
       script_serial_offset = 0
   ```

3. **read_package_summary() - Bounds validation**:
   ```python
   # CustomVersions validation
   custom_versions_count = archive.read_u32()
   if custom_versions_count > MAX_CUSTOM_VERSIONS:
       raise ParseError(f"Custom versions count {custom_versions_count} exceeds maximum {MAX_CUSTOM_VERSIONS}")

   # Name count validation
   name_count = archive.read_i32()
   if name_count > MAX_NAME_COUNT:
       raise ParseError(f"Name count {name_count} exceeds maximum {MAX_NAME_COUNT}")

   # Import count validation
   import_count = archive.read_i32()
   if import_count > MAX_IMPORT_COUNT:
       raise ParseError(f"Import count {import_count} exceeds maximum {MAX_IMPORT_COUNT}")

   # Export count validation
   export_count = archive.read_i32()
   if export_count > MAX_EXPORT_COUNT:
       raise ParseError(f"Export count {export_count} exceeds maximum {MAX_EXPORT_COUNT}")
   ```

4. **read_fstring() - WR-02 fix** (lines 195-201):
   ```python
   if length < 0:
       # WR-02 fix: Sanity check for overflow prevention
       utf16_len = -length * 2
       if utf16_len > 10_000_000:
           raise ParseError(f"UTF-16 string length {utf16_len} too large")
       self.read(utf16_len)
       return ""
   ```

### tests/test_uasset_read.py

1. **create_test_uasset() - CR-02 fix in helper** (lines 201-206):
   ```python
   # UE5+ script_serial fields (CR-02 fix: check legacy_version <= -8, NOT ue5_version >= 0)
   is_ue5_file = legacy_version <= -8
   if is_ue5_file:
       f.write(struct.pack(endian_fmt + 'q', 0))  # ScriptSerialSize
       f.write(struct.pack(endian_fmt + 'q', 0))  # ScriptSerialOffset
   ```

2. **New tests**:
   - `test_ue4_export_no_script_serialization`: Validates UE4 files skip script_serial fields
   - `test_name_count_bounds_validation`: Validates name_count > MAX raises error
   - `test_export_count_bounds_validation`: Validates export_count > MAX raises error
   - `test_utf16_length_overflow`: Validates UTF-16 > 10M bytes raises error

## Verification

- All 23 tests pass (19 existing + 4 new)
- TDD flow followed for all fixes
- Constants properly exported: `MAX_NAME_COUNT=10000000, MAX_IMPORT_COUNT=1000000, MAX_EXPORT_COUNT=1000000`
- No regressions in existing functionality

## Deviations from Plan

### Auto-fixed Issues

None - plan executed exactly as specified with TDD approach.

### Merged Tasks

Tasks 4 and 5 (add tests) were merged into Tasks 2 and 1 during TDD execution. This is the expected TDD pattern where tests are written first (RED) before implementation (GREEN).

## Threat Surface

### Mitigated Threats (per threat_model)

| Threat ID | Category | Mitigation |
|-----------|----------|------------|
| T-01-06-01 | DoS | MAX_*_COUNT bounds prevent memory exhaustion |
| T-01-06-02 | DoS | UTF-16 length sanity check prevents 4GB read attempt |
| T-01-06-03 | Tampering | Correct version check prevents reading wrong fields |

### New Surface Added

None - all mitigations are defensive checks, not new trust boundaries.

---
*Completed: 2026-04-28T04:57:30Z*

## Self-Check: PASSED

- All tests pass (23 tests)
- All commits exist in git log
- Constants properly exported