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
    choice: UE5 >= 1004 时在 CustomVersions 前读取 SavedHash
    rationale: 匹配 UE 5.7 PackageFileSummary.cpp line 176-180 序列化顺序
metrics:
  duration_minutes: 13
  tasks_completed: 4
  tests_passed: 14
  files_modified: 2
---

# 阶段 01 计划 03：SavedHash 缺口填补摘要

## 一句话概述

修复 UE5 文件版本 >= PACKAGE_SAVED_HASH (1004) 的 SavedHash 解析 bug，添加 20-byte FIoHash 和早期 TotalHeaderSize 在 CustomVersions 前读取。

## 所做工作

### 问题

UAT 测试真实 Lyra UE5 文件时，解析器失败报 "Cannot read 1701736270 bytes at position 216" —— NameOffset 包含垃圾值。根本原因：解析器遗漏 UE5 文件版本 >= 1004 的 SavedHash (20 bytes) 和早期 TotalHeaderSize (4 bytes)，导致所有后续字段读取偏移 24 bytes。

### 解决方案

在 read_package_summary() 添加条件性 SavedHash/TotalHeaderSize 读取：
1. 向 PackageFileSummary dataclass 添加 `saved_hash: bytes` 字段
2. UE5 >= PACKAGE_SAVED_HASH (1004) 时，在 LicenseeVersion 后读取 SavedHash (20 bytes) 和 TotalHeaderSize (4 bytes)
3. UE5 >= 1004 时跳过后期 TotalHeaderSize 读取，因为已早期读取

### UE 源码参考

UE 5.7 PackageFileSummary.cpp line 176-180:
```cpp
if (Sum.GetFileVersionUE() >= EUnrealEngineObjectUE5Version::PACKAGE_SAVED_HASH)
{
    Record << SA_VALUE(TEXT("SavedHash"), Sum.SavedHash);      // 20 bytes (FIoHash)
    Record << SA_VALUE(TEXT("TotalHeaderSize"), Sum.TotalHeaderSize);  // 4 bytes
}
```

## 已完成任务

| 任务 | 名称 | 状态 | 提交 | 文件 |
|------|------|--------|--------|-------|
| 1 | 向 PackageFileSummary 添加 saved_hash 字段 | done | 2d66bbf | uasset_read.py |
| 2 | 更新 read_package_summary() 以处理 SavedHash | done | 2d66bbf | uasset_read.py |
| 3 | 添加 SavedHash 解析测试 | done | 60622c5 | tests/test_uasset_read.py |
| 4 | 验证所有测试通过 | done | N/A | verification |

## 关键变更

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

3. **条件性 TotalHeaderSize** (lines 491-493):
   ```python
   if not (legacy_file_version <= -8 and file_version_ue5 >= PACKAGE_SAVED_HASH_VERSION):
       total_header_size = archive.read_i32()
   ```

### tests/test_uasset_read.py

添加 `test_saved_hash_ue5_package_saved_hash_version`：
- 验证 UE5 < 1004 文件的 saved_hash 为空
- 验证 UE5 >= 1004 触发 SavedHash 读取
- 确认 saved_hash 字段存在于 PackageFileSummary

## 验证

- 全部 14 个测试通过（13 个现有 + 1 个新）
- 现有功能无回归
- SavedHash 修复正确条件性基于 UE5 版本

## 与计划的偏差

### 自动修复的问题

无 —— 计划完全按指定执行。

### 已知桩代码

无 —— 修复完整且功能正常。

## 威胁表面

未引入新威胁表面。SavedHash 读取使用现有 FArchive 边界验证。

---

*完成时间：2026-04-28T04:05:02Z*