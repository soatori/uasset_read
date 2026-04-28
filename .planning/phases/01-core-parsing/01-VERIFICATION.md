---
phase: 01-core-parsing
verified: 2026-04-28T08:30:00Z
status: gaps_found
score: 2/4 must-haves verified
overrides_applied: 0
re_verification:
  previous_status: human_needed
  previous_score: 4/4
  gaps_closed:
    - "SavedHash parsing for UE5 >= PACKAGE_SAVED_HASH (1004) - implemented in 01-03"
    - "LegacyUE3Version field reading - implemented in 01-02"
    - "UE5 version conditional correction (<= -8 not >= -8) - implemented in 01-02"
  gaps_remaining:
    - "Lyra UE5 file parsing fails due to missing PackageName field"
    - "Inline names handling incorrectly triggered for legacy=-7"
  regressions: []
gaps:
  - truth: "给定任意有效 .uasset 文件，解析器读取文件头后 PackageFileSummary 包含正确的魔术标签、版本号和偏移"
    status: failed
    reason: "Parser missing PackageName FString field between TotalHeaderSize and PackageFlags; inline names handling incorrectly triggered for legacy=-7"
    severity: blocker
    artifacts:
      - path: "uasset_read.py"
        issue: "read_package_summary() jumps from TotalHeaderSize directly to PackageFlags, missing PackageName FString (variable bytes); incorrect condition `legacy >= -5` triggers inline names for legacy=-7 when NameOffset should be read"
    missing:
      - "PackageName FString field reading after TotalHeaderSize (UE PackageFileSummary.cpp line 258)"
      - "Remove inline names handling for modern files (legacy < 0 always has NameOffset field)"
  - truth: "给定有效 .uasset 文件，解析器读取名称表和映射表后 NameMap、ImportMap、ExportMap 包含所有条目及正确值"
    status: failed
    reason: "NameOffset calculated incorrectly due to missing PackageName field, causing seek to invalid position 1701736270 (ASCII 'None') instead of correct 448"
    severity: blocker
    artifacts:
      - path: "uasset_read.py"
        issue: "NameOffset=1701736270 (garbage) instead of correct 448; caused by missing PackageName field shifting all subsequent field reads"
    missing:
      - "Same as above - PackageName field missing causes 9+ byte offset error in all downstream field positions"
human_verification: []
---

# Phase 1: Core Parsing Verification Report

**Phase Goal:** 解析 .uasset 文件头、名称表、导入表和导出表；识别资产结构和类型

**Verified:** 2026-04-28T08:30:00Z
**Status:** gaps_found
**Re-verification:** Yes - after 01-03 SavedHash gap closure

## Goal Achievement

### Observable Truths

| #   | Truth | Status | Evidence |
| --- | --- | --- | --- |
| 1 | 给定任意有效 .uasset 文件，解析器读取文件头后 PackageFileSummary 包含正确的魔术标签、版本号和偏移 | FAILED | Lyra Character_Default.uasset: NameOffset=1701736270 (invalid, exceeds file size 20154); root cause: missing PackageName FString field |
| 2 | 给定带有交换字节序魔术标签的文件，解析器检测后启用字节交换，后续所有读取正确 | VERIFIED | test_byte_swapping_detection passes; byte swapping logic implemented correctly in read_package_summary() |
| 3 | 给定有效 .uasset 文件，解析器读取名称表和映射表后 NameMap、ImportMap、ExportMap 包含所有条目及正确值 | FAILED | Cannot seek to NameOffset=1701736270; parser throws "Cannot read 1701736270 bytes at position 216" |
| 4 | 给定不支持的版本 .uasset，解析器返回清晰错误信息而不崩溃 | VERIFIED | test_unsupported_legacy_version, test_invalid_tag, test_low_ue5_version all pass; error messages clear |

**Score:** 2/4 truths verified

### Re-Verification Context

Previous verification (2026-04-28T12:00:00Z) had status: human_needed, stating:
- "Integration test with real UE 5.x .uasset file" needed
- "Per CONTEXT.md D-17: user provides sample files"

**This re-verification performed real file testing:**
- Lyra Starter Game UE5 files available in `LyraStarterGame/` directory
- Character_Default.uasset (legacy=-7, UE4 version 521) tested
- Discovered critical bugs not visible in synthetic tests

### Gap Analysis

#### Gap 1: Missing PackageName FString Field

**Discovery Process:**
1. Ran `parse_uasset('Character_Default.uasset')` - failed with "Cannot read 1701736270 bytes"
2. Traced byte positions manually following UE PackageFileSummary.cpp order
3. Found position mismatch: parser reads PackageFlags at 208, but UE source shows PackageName FString at 208

**File Structure Analysis (Lyra Character_Default.uasset):**
```
Position 0-3:   Tag = 0x9e2a83c1
Position 4-7:   LegacyFileVersion = -7
Position 8-11:  LegacyUE3Version = 864
Position 12-15: FileVersionUE4 = 521
Position 16-19: FileVersionLicenseeUE = 0
Position 20-23: CustomVersionsCount = 9
Position 24-203: CustomVersions (9 entries)
Position 204-207: TotalHeaderSize = 14620
Position 208-211: PackageName FString length = 5
Position 212-216: PackageName = "None\x00" (5 bytes)
Position 217-220: PackageFlags = 262144
Position 221-224: NameCount = 129
Position 225-228: NameOffset = 448 (VALID!)
```

**UE Source Reference (PackageFileSummary.cpp line 258):**
```cpp
Record << SA_VALUE(TEXT("PackageName"), Sum.PackageName);  // FString, not FName!
```

**Current Parser Code (uasset_read.py lines 439-441):**
```python
# PackageFlags (D-12 仅存储)
package_flags = archive.read_u32()  # Position 204 expected, but PackageName starts here!
```

**Result:**
- Parser reads PackageName length (5) as PackageFlags
- Parser reads "None\x00" bytes as NameCount/NameOffset
- All downstream field reads are offset by 9 bytes (5 + 4 length bytes)
- NameOffset becomes garbage value 1701736270 = ASCII "None" reversed

#### Gap 2: Incorrect Inline Names Handling

**Current Code (uasset_read.py lines 443-461):**
```python
if legacy_file_version >= -5:
    name_offset = archive.read_i32()
else:
    # legacy < -5: inline names
    name_offset = archive.tell()
    # Skip inline name data...
```

**Problem:**
- For legacy=-7: condition `-7 >= -5` is False (mathematically -7 < -5)
- Code incorrectly enters inline names branch
- But UE source shows NameOffset field is ALWAYS present for modern files (legacy < 0)

**UE Source Reference (PackageFileSummary.cpp line 278):**
```cpp
Record << SA_VALUE(TEXT("NameCount"), Sum.NameCount) << SA_VALUE(TEXT("NameOffset"), Sum.NameOffset);
// No conditional - NameOffset always serialized for modern files
```

**Correct Behavior:**
- All UE4/UE5 files (LegacyFileVersion -2 to -9) have NameOffset field
- Inline names format only for UE3 files (LegacyFileVersion >= 0)
- Parser should always read NameOffset when legacy < 0

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
| ----------- | ---------- | ----------- | ------ | -------- |
| CORE-01 | 01-01-PLAN | 解析器能读取 .uasset 文件头，包含魔术标签、版本信息和各区块偏移 | FAILED | PackageName field missing; NameOffset invalid for real UE5 files (legacy=-7) |
| CORE-02 | 01-01-PLAN | 字节序检测和处理 | VERIFIED | test_byte_swapping_detection passes |
| CORE-03 | 01-01-PLAN | 名称表提取 | FAILED | NameOffset seek fails - position 1701736270 exceeds file size |
| CORE-04 | 01-01-PLAN | 导入表解析 | BLOCKED | Depends on correct NameOffset (blocked by CORE-03) |
| CORE-05 | 01-01-PLAN | 导出表解析 | BLOCKED | Depends on correct NameOffset (blocked by CORE-03) |
| CORE-06 | 01-01-PLAN | 资产类型识别 | VERIFIED | get_asset_class() works (synthetic test passes) |
| CORE-07 | 01-01-PLAN | 版本处理 | VERIFIED | LegacyUE3Version, UE5 conditionals fixed in 01-02 |
| CORE-08 | 01-01-PLAN | 错误处理 | VERIFIED | VersionError, ParseError with partial results work |

### Deferred Items

None - all gaps must be addressed in this phase.

### Key Files Analysis

| Artifact | Exists | Substantive | Wired | Data Flows | Status |
| -------- | ------ | ----------- | ----- | ---------- | ------ |
| uasset_read.py | Yes (756 lines) | Yes | Yes | Partial | HOLLOW - missing PackageName field breaks real file parsing |
| tests/test_uasset_read.py | Yes (649 lines) | Yes | Yes | Yes | VERIFIED - 14 tests pass (but synthetic only) |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
| -------- | ------- | ------ | ------ |
| Synthetic unit tests | `python -m pytest tests/ -v` | 14/14 passed | PASS |
| Lyra Character_Default.uasset | `parse_uasset('Character_Default.uasset')` | "Cannot read 1701736270 bytes at position 216" | FAIL |
| Correct simulation | Manual trace with PackageName field | NameOffset=448 valid, 5 names read successfully | PROOF OF FIX |

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
| ---- | ---- | ------- | -------- | ------ |
| uasset_read.py | 443-461 | Missing PackageName field + incorrect inline names condition `legacy >= -5` | BLOCKER | Real UE5 files (legacy=-7) fail to parse |
| uasset_read.py | 639-644 | Script serialization read uses `file_version_ue5 >= UE5_VERSION_MIN` where UE5_VERSION_MIN=0 | WARNING | May read non-existent fields for legacy=-7 files |

### Gaps Summary

**Two critical bugs discovered:**

1. **Missing PackageName FString field** (severity: blocker)
   - Location: read_package_summary() after TotalHeaderSize (around line 439)
   - Effect: All subsequent header fields offset by PackageName size (variable)
   - Fix: Add FString reading for PackageName before PackageFlags

2. **Incorrect inline names condition** (severity: blocker)
   - Location: lines 443-461
   - Effect: legacy=-7 incorrectly treated as inline names format
   - Fix: Remove inline names handling for modern files (always read NameOffset when legacy < 0)

**Fixes from previous plans verified working:**
- 01-02: LegacyUE3Version reading for legacy != -4
- 02-02: UE5 version conditional (legacy <= -8, not >= -8)
- 01-03: SavedHash reading for UE5 >= 1004

**Why synthetic tests didn't catch this:**
- create_test_uasset() helper doesn't emit PackageName field
- Synthetic files match parser's assumptions, not real UE file format
- Real file testing was deferred to "human verification" in previous phases

---

## Recommended Fix

```python
# In read_package_summary(), after TotalHeaderSize (around line 439):

# PackageName (FString) - Reference: UE PackageFileSummary.cpp line 258
# Note: PackageName is FString type, serialized as int32 length + UTF-8 data
package_name_len = archive.read_i32()
if package_name_len > 0:
    package_name_data = archive.read(package_name_len)
    # PackageName stored but not used in core parsing
elif package_name_len < 0:
    archive.read(-package_name_len * 2)  # UTF-16 (legacy format)
# else: package_name_len == 0, empty string, no data to read

# PackageFlags (line 265 in UE source)
package_flags = archive.read_u32()

# NameCount + NameOffset (line 278) - ALWAYS present for modern UE4/UE5 files
# Remove the incorrect inline names conditional
name_count = archive.read_i32()
name_offset = archive.read_i32()  # Always read for legacy < 0

# Remove lines 448-461 inline names handling entirely
# Inline names only for UE3 files (legacy >= 0), not supported per D-04
```

---

_Verified: 2026-04-28T08:30:00Z_
_Verifier: Claude (gsd-verifier)_