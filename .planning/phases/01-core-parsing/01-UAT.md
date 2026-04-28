---
status: testing
phase: 01-core-parsing
source: [01-01-SUMMARY.md, 01-02-SUMMARY.md]
started: 2026-04-28T12:30:00Z
updated: 2026-04-28T16:00:00Z
---

## Current Test

number: 2
name: Parse real UE5 .uasset file (Lyra)
expected: |
  解析 Lyra Character_Default.uasset 成功，NameMap/ImportMap/ExportMap 包含正确数据
awaiting: gap recorded

## Tests

### 1. Synthetic test files
expected: 所有合成测试文件通过
result: pass
note: 13/13 tests passed

### 2. Parse real UE5 .uasset file (Lyra)
expected: 解析 Lyra Character_Default.uasset 成功
result: issue
reported: "Cannot read 1701736270 bytes at position 216 - NameOffset contains garbage value 'None'"
severity: blocker
diagnosis: |
  **Root Cause Identified:**
  
  UE 源码 PackageFileSummary.cpp line 176-180 显示：
  ```cpp
  if (Sum.GetFileVersionUE() >= EUnrealEngineObjectUE5Version::PACKAGE_SAVED_HASH)
  {
      Record << SA_VALUE(TEXT("SavedHash"), Sum.SavedHash);      // 20 bytes (FIoHash)
      Record << SA_VALUE(TEXT("TotalHeaderSize"), Sum.TotalHeaderSize);  // 4 bytes
  }
  ```
  
  当前代码缺少这两个字段：
  - SavedHash (20 bytes, FIoHash structure)
  - TotalHeaderSize (int32, 但此处是 early read)
  
  **正确的字段顺序：**
  1. UE5Version
  2. LicenseeVersion
  3. SavedHash (20 bytes) ← **缺失**
  4. TotalHeaderSize (int32) ← **缺失**
  5. CustomVersions
  6. PackageFlags
  7. NameCount + NameOffset
  
  Lyra 文件 UE5Version=1004/1005 >= PACKAGE_SAVED_HASH，所以必须先读 SavedHash。
  当前代码跳过了这 24 bytes，导致后续所有字段错位。
  
  **修复方案：**
  在 read_package_summary() 中，UE5Version 和 LicenseeVersion 之后：
  ```python
  if file_version_ue5 >= 1004:  # PACKAGE_SAVED_HASH version
      saved_hash = archive.read(20)  # FIoHash
      total_header_size_early = archive.read_i32()
  ```
fix_required:
  - Add SavedHash field (20 bytes) to PackageFileSummary dataclass
  - Add early TotalHeaderSize read before CustomVersions for UE5 >= PACKAGE_SAVED_HASH
  - Update read_package_summary() to read these fields in correct order

### 3. Byte-swapping detection
expected: 解析器能正确检测和处理字节交换
result: pass

### 4. Asset class identification
expected: get_asset_class() 能正确识别导出的资产类名
result: pass

## Summary

total: 4
passed: 2
issues: 1
pending: 0
skipped: 0

## Gaps

- truth: "给定有效 UE5 .uasset 文件 (UE5Version >= PACKAGE_SAVED_HASH)，解析器能正确读取文件头所有字段"
  status: failed
  reason: "缺少 SavedHash (20 bytes) 和 early TotalHeaderSize (4 bytes) 字段读取"
  severity: blocker
  test: 2
  artifacts:
    - uasset_read.py:read_package_summary()
  missing:
    - SavedHash field in PackageFileSummary dataclass
    - Early TotalHeaderSize read for UE5 >= PACKAGE_SAVED_HASH files
  diagnosis_complete: true
  fix_plan_needed: true

---