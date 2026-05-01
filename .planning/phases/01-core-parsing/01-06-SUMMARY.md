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
    choice: 检查 legacy_file_version <= -8 而非 file_version_ue5 >= 0 以读取 script_serial 字段
    rationale: UE4 文件（legacy > -8）有 file_version_ue5=0，所以 ue5_version >= 0 总是 True
  - id: D-01-06-02
    choice: 设置 MAX_NAME_COUNT=10M, MAX_IMPORT/EXPORT_COUNT=1M
    rationale: 真实 UE 文件计数在数百/数千；这些边界防止 DoS
  - id: D-01-06-03
    choice: 拒绝 UTF-16 字符串 > 10M bytes
    rationale: 防止 -length * 2 溢出（INT_MIN 时 4GB 读取）
metrics:
  duration_minutes: 15
  tasks_completed: 5
  tests_passed: 23
  files_modified: 2
---

# 阶段 01 计划 06：严重和警告问题修复摘要

## 一句话概述

修复三个安全/健壮性问题：正确的 UE4 script_serial 跳过、数组计数边界验证、UTF-16 长度溢出防止。

## 所做工作

### 修复的问题

1. **CR-02: Script serialization 字段总是读取**：条件 `file_version_ue5 >= UE5_VERSION_MIN`（MIN=0）总是 True，导致解析器为 UE4 文件（legacy > -8）多读 16 bytes。这导致真实 UE4 文件如 Lyra assets 解析错误。

2. **WR-01: 数组计数无边界验证**：计数直接读入循环无验证，恶意文件巨大计数的潜在 DoS 风险。

3. **WR-02: UTF-16 字符串长度整数溢出**：计算 `-length * 2` 对极端值如 INT_MIN 可能溢出，可能导致 4GB 读取尝试。

### 解决方案

1. 从 `file_version_ue5 >= UE5_VERSION_MIN` 改为 `legacy_file_version <= -8` 条件以读取 script_serial 字段。

2. 添加边界验证常量（MAX_NAME_COUNT=10M, MAX_IMPORT/EXPORT_COUNT=1M, MAX_CUSTOM_VERSIONS=10K）和 read_package_summary() 中验证检查。

3. 添加 UTF-16 长度溢出检查：拒绝长度 > 10M bytes 的字符串。

## 已完成任务

| 任务 | 名称 | 状态 | 提交 | 文件 |
|------|------|--------|--------|-------|
| 1 | 修复 script serialization 字段条件 | done | 862a63c | uasset_read.py, tests/test_uasset_read.py |
| 2 | 添加边界验证常量和检查 | done | 28b3994 | uasset_read.py, tests/test_uasset_read.py |
| 3 | 添加 UTF-16 字符串长度溢出检查 | done | 27db5c6 | uasset_read.py, tests/test_uasset_read.py |
| 4 | 添加边界验证测试 | merged | 28b3994 | tests/test_uasset_read.py |
| 5 | 添加 UE4 script serialization 跳过测试 | merged | 862a63c | tests/test_uasset_read.py |

注意：任务 4 和 5 在 TDD 执行中合并到任务 2 和 1（实现前写测试）。

## 关键变更

### uasset_read.py

1. **常量部分**（lines 32-36）：
   ```python
   # 边界验证常量（WR-01 缓解）
   MAX_NAME_COUNT = 10_000_000      # 最大名称表条目数
   MAX_IMPORT_COUNT = 1_000_000     # 最大导入表条目数
   MAX_EXPORT_COUNT = 1_000_000     # 最大导出表条目数
   MAX_CUSTOM_VERSIONS = 10_000     # 最大自定义版本条目数
   ```

2. **read_export_map() - CR-02 修复**（lines 634-644）：
   ```python
   # CR-02 fix: 检查文件是否为 UE5（legacy <= -8），而非 ue5_version >= 0
   # UE4 文件（legacy > -8）无这些字段 - file_version_ue5 保持 0
   is_ue5_file = summary.legacy_file_version <= -8

   if is_ue5_file:
       script_serial_size = archive.read_i64()
       script_serial_offset = archive.read_i64()
   else:
       script_serial_size = 0
       script_serial_offset = 0
   ```

3. **read_package_summary() - 边界验证**：
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

4. **read_fstring() - WR-02 修复**（lines 195-201）：
   ```python
   if length < 0:
       # WR-02 fix: 溢出防止合理性检查
       utf16_len = -length * 2
       if utf16_len > 10_000_000:
           raise ParseError(f"UTF-16 string length {utf16_len} too large")
       self.read(utf16_len)
       return ""
   ```

### tests/test_uasset_read.py

1. **create_test_uasset() - helper 中 CR-02 修复**（lines 201-206）：
   ```python
   # UE5+ script_serial fields（CR-02 fix: 检查 legacy_version <= -8，而非 ue5_version >= 0）
   is_ue5_file = legacy_version <= -8
   if is_ue5_file:
       f.write(struct.pack(endian_fmt + 'q', 0))  # ScriptSerialSize
       f.write(struct.pack(endian_fmt + 'q', 0))  # ScriptSerialOffset
   ```

2. **新测试**：
   - `test_ue4_export_no_script_serialization`：验证 UE4 文件跳过 script_serial 字段
   - `test_name_count_bounds_validation`：验证 name_count > MAX 抛错误
   - `test_export_count_bounds_validation`：验证 export_count > MAX 抛错误
   - `test_utf16_length_overflow`：验证 UTF-16 > 10M bytes 抛错误

## 验证

- 全部 23 个测试通过（19 个现有 + 4 个新）
- 所有修复遵循 TDD 流程
- 常量正确导出：`MAX_NAME_COUNT=10000000, MAX_IMPORT_COUNT=1000000, MAX_EXPORT_COUNT=1000000`
- 现有功能无回归

## 与计划的偏差

### 自动修复的问题

无 —— 计划完全按指定执行，采用 TDD 方法。

### 合并任务

任务 4 和 5（添加测试）在 TDD 执行中合并到任务 2 和 1。这是预期 TDD 模式，实现（GREEN）前先写测试（RED）。

## 威胁表面

### 缓解威胁（per threat_model）

| Threat ID | Category | Mitigation |
|-----------|----------|------------|
| T-01-06-01 | DoS | MAX_*_COUNT 边界防止内存耗尽 |
| T-01-06-02 | DoS | UTF-16 长度合理性检查防止 4GB 读取尝试 |
| T-01-06-03 | Tampering | 正确版本检查防止读取错误字段 |

### 新增表面

无 —— 所有缓解是防御检查，非新信任边界。

---
*完成时间：2026-04-28T04:57:30Z*

## 自检：通过

- 所有测试通过（23 tests）
- 所有提交存在于 git log
- 常量正确导出