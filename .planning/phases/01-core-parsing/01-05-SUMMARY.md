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
    choice: 在 CustomVersions 后、PackageFlags 前读取 PackageName FString
    rationale: 匹配 UE 5.7 PackageFileSummary.cpp line 258 序列化顺序
  - id: D-01-05-02
    choice: 移除 inline names 分支，legacy < 0 时总是读取 NameOffset
    rationale: 所有 UE4/UE5 文件（legacy -2 至 -9）有 NameOffset；inline names 仅用于 UE3（legacy >= 0）
metrics:
  duration_minutes: 12
  tasks_completed: 4
  tests_passed: 19
  files_modified: 2
---

# 阶段 01 计划 05：PackageName 和 Inline Names 缺口填补摘要

## 一句话概述

修复两个阻止真实 UE5 文件解析的阻塞 bug：添加缺失的 PackageName FString 字段读取，移除错误触发 legacy=-7（Lyra 文件）inline names 条件。

## 所做工作

### 问题

UAT/REVIEW 测试真实 Lyra UE5 文件（legacy=-7, UE4 v521）时，解析器失败报 "Cannot read X bytes" 错误。识别两个根本原因：

1. **缺失 PackageName FString 字段**：解析器从 CustomVersions 直接跳到 PackageFlags，遗漏 PackageName FString（9 bytes：4 length + 5 "None\x00"）。这偏移了所有后续字段读取。

2. **错误的 inline names 条件**：条件 `legacy >= -5` 错误触发 legacy=-7 文件的 inline names 处理。UE 源码显示 NameOffset 对现代文件（legacy < 0）总是存在。

### 解决方案

1. 在 CustomVersions 后添加 PackageName FString 读取（UE 源码 line 258）
2. 完全移除错误的 inline names 分支 - UE4/UE5 文件总是读取 NameOffset

### UE 源码参考

UE 5.7 PackageFileSummary.cpp:
```cpp
// Line 258 - PackageName 是 FString，不是 FName
Record << SA_VALUE(TEXT("PackageName"), Sum.PackageName);

// Line 265 - PackageName 后的 PackageFlags
Record << SA_VALUE(TEXT("PackageFlags"), Sum.PackageFlags);

// Line 278 - NameCount + NameOffset 对现代文件总是序列化
Record << SA_VALUE(TEXT("NameCount"), Sum.NameCount) << SA_VALUE(TEXT("NameOffset"), Sum.NameOffset);
// 无条件 - legacy < 0 时 NameOffset 总是存在
```

## 已完成任务

| 任务 | 名称 | 状态 | 提交 | 文件 |
|------|------|--------|--------|-------|
| 1 | 添加 PackageName FString 字段读取 | done | 8237388 | uasset_read.py |
| 2 | 修复 inline names 条件 | done | 8237388 | uasset_read.py |
| 3 | 更新 create_test_uasset helper | done | 48cf2d6 | tests/test_uasset_read.py |
| 4 | 添加 Lyra 类文件解析测试 | done | 48cf2d6 | tests/test_uasset_read.py |

## 关键变更

### uasset_read.py

1. **PackageFileSummary dataclass**（line 286）：
   ```python
   package_name: str = ""  # PackageName FString（UE PackageFileSummary.cpp line 258）
   ```

2. **read_package_summary()** - PackageName 读取（lines 446-449）：
   ```python
   # PackageName (FString) - Reference: UE PackageFileSummary.cpp line 258
   # Note: PackageName 是 FString 类型（int32 length + UTF-8 data），不是 FName
   package_name = archive.read_fstring()
   ```

3. **read_package_summary()** - Inline names 修复（lines 453-458）：
   ```python
   # 名称表处理（UE PackageFileSummary.cpp line 278）
   # NameCount + NameOffset 对现代 UE4/UE5 文件（legacy < 0）总是存在
   # Inline names format only for UE3 files（legacy >= 0），按 D-04 不支持
   name_count = archive.read_i32()
   name_offset = archive.read_i32()  # legacy < 0 时总是读取
   ```

4. **Return statement**（line 506）：
   ```python
   package_name=package_name,
   ```

### tests/test_uasset_read.py

1. **create_test_uasset()** - PackageName 输出（lines 118-122）：
   ```python
   # PackageName (FString) - 匹配 UE PackageFileSummary.cpp line 258
   package_name_bytes = "None".encode('utf-8') + b'\x00'
   f.write(struct.pack(endian_fmt + 'i', len(package_name_bytes)))
   f.write(package_name_bytes)
   ```

2. **create_test_uasset()** - 移除 inline names 分支：
   - 总是输出 NameOffset 占位符
   - 总是在文件头末尾写入名称

3. **新测试**：
   - `test_legacy_minus_seven_ue4_521`：验证 Lyra 类文件解析
   - `test_package_name_field_reading`：验证 PackageName 字段存在

## 验证

- 全部 19 个测试通过（17 个现有 + 2 个新）
- 遵循 TDD 流程：RED 测试先行（因 bug 失败），GREEN 实现
- 现有功能无回归
- 合成测试文件现在匹配真实 UE 文件结构

## 与计划的偏差

### 自动修复的问题

无 —— 计划完全按指定执行。

### 已知桩代码

无 —— 修复完整且功能正常。

## 威胁表面

未引入新威胁表面。PackageName 读取使用现有 `read_fstring()` 验证 length 与剩余字节。NameOffset 由 `seek()` 边界检查验证（D-14）。

---
*完成时间：2026-04-28T04:52:37Z*

## 自检：通过

- 找到：01-05-SUMMARY.md
- 找到：commit 8237388（parser fix）
- 找到：commit 48cf2d6（test update）
- 找到：uasset_read.py
- 找到：tests/test_uasset_read.py