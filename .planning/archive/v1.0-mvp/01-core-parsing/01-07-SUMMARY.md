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
      changes: [UE4 文件的 TotalHeaderSize 位置修复，版本感知条件]
    - path: tests/test_uasset_read.py
      changes: [test_ue4_total_header_size_at_correct_position, test_total_header_size_position_ue4, create_test_uasset SavedHash/TotalHeaderSize update]
decisions:
  - id: D-01-07-01
    choice: UE4 文件（legacy > -8）的 TotalHeaderSize 在 CustomVersions 后读取
    rationale: UE 源码 PackageFileSummary.cpp lines 254-258 显示版本 < PACKAGE_SAVED_HASH 时 TotalHeaderSize 在 PackageName 前
  - id: D-01-07-02
    choice: UE5 >= PACKAGE_SAVED_HASH 时 SavedHash + TotalHeaderSize 在 CustomVersions 前读取
    rationale: UE 源码 lines 236-240 显示 UE5 >= 1004 时 SavedHash 块位置
metrics:
  duration_minutes: 25
  tasks_completed: 3
  tests_passed: 25
  files_modified: 2
---

# 阶段 01 计划 07：TotalHeaderSize 位置修复摘要

## 一句话概述

修复 TotalHeaderSize 读取位置 bug，阻止 Lyra UE4 文件解析，通过将解析器与 UE 源码参考对齐版本感知文件头结构。

## 所做工作

### 修复问题

**UE4 文件 TotalHeaderSize 在错误位置**：解析器在 trailer 位置读取 TotalHeaderSize（BulkDataStartOffset 后），但 UE 源码显示：
- UE4 文件（< PACKAGE_SAVED_HASH）：CustomVersions 后、PackageName 前的 TotalHeaderSize
- UE5 >= PACKAGE_SAVED_HASH：SavedHash 块中的 TotalHeaderSize（已正确）
- UE5 < PACKAGE_SAVED_HASH：trailer 位置的 TotalHeaderSize（与 UE4 trailer 相同）

**影响**：Lyra Character_Default.uasset（legacy=-7, UE4 v521）失败：
- 解析器读取 TotalHeaderSize=14620 作为 PackageName FString length
- 读取 14620 bytes 作为 package_name（整个文件）
- NameOffset 变为垃圾值 589824

### 解决方案

修改 read_package_summary() 以在 UE 版本感知的正确位置读取 TotalHeaderSize：
1. UE4 文件（legacy > -8）：CustomVersions 后、PackageName 前的 TotalHeaderSize
2. UE5 >= PACKAGE_SAVED_HASH：SavedHash 块中已有 TotalHeaderSize（无需改动）
3. UE5 < PACKAGE_SAVED_HASH：trailer 位置的 TotalHeaderSize（不变）

更新 create_test_uasset helper 以在所有 UE 版本的正确位置输出 TotalHeaderSize。

## 已完成任务

| 任务 | 名称 | 状态 | 提交 | 文件 |
|------|------|--------|--------|-------|
| 1 | 将 TotalHeaderSize 移至 UE4 文件正确位置 | done | 93c5f1b | uasset_read.py |
| 2 | 添加 TotalHeaderSize 位置验证测试 | done | 5dfe9ab | tests/test_uasset_read.py |
| 3 | 更新 create_test_uasset helper 以处理 TotalHeaderSize | done | 5dfe9ab | tests/test_uasset_read.py |

注意：任务按 TDD 顺序执行（RED: Task 2/3 test + helper, GREEN: Task 1 implementation）。

## 关键变更

### uasset_read.py

**TotalHeaderSize 位置修复**（lines ~460-470）：
```python
# CustomVersions 后（line ~458）：
# UE4 文件的 TotalHeaderSize（legacy > -8, version < PACKAGE_SAVED_HASH）
if legacy_file_version > -8:
    # UE4 file: TotalHeaderSize 在 CustomVersions 后，PackageName 前
    total_header_size = archive.read_i32()

# PackageName（总是）
package_name = archive.read_fstring()
```

**UE5 < PACKAGE_SAVED_HASH 的 Trailer TotalHeaderSize**（lines ~519-524）：
```python
# UE5 文件 < PACKAGE_SAVED_HASH（version < 1004）的 TotalHeaderSize
if legacy_file_version <= -8 and file_version_ue5 < PACKAGE_SAVED_HASH_VERSION:
    # UE5 file with version < 1004: trailer 位置的 TotalHeaderSize
    total_header_size = archive.read_i32()
```

### tests/test_uasset_read.py

**create_test_uasset SavedHash/TotalHeaderSize update**（lines ~110-130）：
```python
# UE5 >= PACKAGE_SAVED_HASH（version 1004）的 SavedHash 和 TotalHeaderSize
PACKAGE_SAVED_HASH_VERSION = 1004
is_ue5_file = legacy_version <= -8

if is_ue5_file and ue5_version >= PACKAGE_SAVED_HASH_VERSION:
    # UE5 >= PACKAGE_SAVED_HASH: CustomVersions 前的 SavedHash + TotalHeaderSize
    f.write(b'\x00' * 20)  # SavedHash placeholder（20 bytes）
    total_header_size_pos = f.tell()
    f.write(struct.pack(endian_fmt + 'i', 0))  # TotalHeaderSize placeholder

# CustomVersions（总是）
f.write(struct.pack(endian_fmt + 'I', len(custom_versions)))
...

# UE4 文件的 TotalHeaderSize（legacy > -8）
if not is_ue5_file:
    # UE4 file: 正确位置的 TotalHeaderSize placeholder
    total_header_size_pos = f.tell()
    f.write(struct.pack(endian_fmt + 'i', 0))  # Placeholder
```

**新测试**：
- `test_ue4_total_header_size_at_correct_position`：手动创建正确 TotalHeaderSize 位置的 UE4 文件
- `test_total_header_size_position_ue4`：使用 helper 验证 UE4 文件解析

## 验证

- 全部 25 个测试通过（23 个现有 + 2 个新）
- 遵循 TDD 流程（RED: test + helper, GREEN: implementation）
- Lyra 类 UE4 文件现在正确解析
- UE5 文件解析无回归

## 与计划的偏差

### 自动修复的问题

无 —— 计划完全按指定执行，采用 TDD 方法。

## 威胁表面

### 缓解威胁（per threat_model）

| Threat ID | Category | Mitigation |
|-----------|----------|------------|
| T-01-07-01 | Tampering | TotalHeaderSize 值用于边界检查（D-14） - 无新表面 |

### 新增表面

无 —— 修复将解析器与 UE 源码对齐，无新信任边界。

---
*完成时间：2026-04-28T05:12:37Z*

## 自检：通过

- 所有测试通过（25 tests）
- 所有提交存在于 git log
- UE4 和 UE5 文件的 TotalHeaderSize 在正确位置