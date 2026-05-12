---
phase: 01-core-architecture
plan: 02
subsystem: archive
tags: [tdd, binary-io, byte-order, fstring, magic-validation]
requires: [01-01-PLAN]
provides: [UAssetArchive, detect_byte_order, read_fstring]
affects: []
tech_stack:
  added:
    - Python struct module for binary parsing
    - UTF-8/UTF-16LE string decoding
  patterns:
    - Factory pattern (UAssetArchive.open)
    - Context manager pattern (with statement)
key_files:
  created:
    - src/uasset_read/archive.py
    - tests/test_archive.py
  modified: []
decisions:
  - D-01: Use struct module for binary parsing
  - D-03: Pre-compile struct formats for performance (future optimization)
  - Byte order detection via little-endian unpack + value comparison
metrics:
  duration: ~15 minutes
  completed_date: 2026-05-01
  test_count: 18
  coverage_estimate: 95%
---

# Phase 01 Plan 02: UAssetArchive 包装器 Summary

## 一句话概述

实现了 UAssetArchive 二进制文件包装器，包含魔数验证、字节序自动检测和 FString 读取方法（UTF-8/UTF-16 双编码支持）。

## 完成任务

### Task 1: detect_byte_order 函数

实现了 `detect_byte_order(tag: int, file_path: str = "") -> str` 函数：
- 输入魔数值（int），返回字节序标识符（'<' 或 '>'）
- `PACKAGE_FILE_TAG` (0x9E2A83C1) → 小端 '<'
- `PACKAGE_FILE_TAG_SWAPPED` (0xC1832A9E) → 大端 '>'
- 无效魔数抛出 `MagicError`（包含 expected/actual 值）

**关键发现**：UE 的字节序检测逻辑是用小端解析文件头字节序列，然后比较解析后的值：
- 小端解析得到 PACKAGE_FILE_TAG → 文件是小端
- 小端解析得到 PACKAGE_FILE_TAG_SWAPPED → 文件是大端

### Task 2: UAssetArchive 类基础结构

实现了 `UAssetArchive` 类：
- `open(path)` 工厂方法：自动检测字节序、验证魔数
- `read_int32/read_uint32/read_int64/read_uint64`：基础整数读取
- `read_bytes(length)`：原始字节读取
- `read_fstring()`：UE FString 读取（UTF-8 和 UTF-16 支持）
- `seek/tell/position`：位置追踪
- `set_version()`：版本设置接口（供后续 SummaryParser 使用）
- `with` 语句支持：自动资源管理

### Task 3: checkpoint:human-verify

计划中包含人工验证检查点，但由于 autonomous: true 设置，自动化完成核心功能。

## UE 源码追溯

| 功能 | UE 源码位置 |
|------|------------|
| PACKAGE_FILE_TAG 定义 | ObjectVersion.h lines 14-15 |
| 字节序检测逻辑 | ObjectVersion.h + LinkerLoad.cpp |
| FString 序列化 | String.cpp.inl lines 1779-1953 |
| Archive 概念 | LinkerLoad.h, Archive.h |

## FString 序列化格式

UE FString 序列化格式（Source: String.cpp.inl）：
1. `int32 SaveNum`：长度值
   - `SaveNum > 0`：UTF-8/ANSI 编码，包含 null terminator
   - `SaveNum < 0`：UTF-16 编码，|SaveNum| 包含 null terminator
   - `SaveNum == 0`：空字符串
2. 字符数据：UTF-8 或 UTF-16LE 编码
3. null terminator 包含在长度中

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] 大端字节序检测逻辑错误**
- **Found during:** Task 2 测试执行
- **Issue:** 初始实现错误地比较字节序列而非解析值
- **Fix:** 采用 UE 源码的实际逻辑：用小端解析字节序列，比较解析后的值
- **Files modified:** src/uasset_read/archive.py (open 方法)
- **Commit:** 378c921

**2. [Rule 1 - Bug] 测试中大端数据生成错误**
- **Found during:** Task 2 测试执行
- **Issue:** 测试使用 `struct.pack('>I', PACKAGE_FILE_TAG_SWAPPED)` 生成大端数据，但实际应使用 `struct.pack('>I', PACKAGE_FILE_TAG)`
- **Fix:** 修正测试数据生成逻辑
- **Files modified:** tests/test_archive.py
- **Commit:** 378c921

None - plan executed as specified after auto-fixes.

## TDD Gate Compliance

| Gate | Commit | Status |
|------|--------|--------|
| RED | 170c9bf | test(01-02): add tests for archive module |
| GREEN | 378c921 | feat(01-02): implement archive module with UAssetArchive |

TDD 流程正确执行：先提交测试，后提交实现。

## 测试覆盖

18 个测试全部通过：
- 4 个 detect_byte_order 测试
- 7 个 UAssetArchive 基础功能测试
- 5 个 FString 读取测试
- 1 个大端字节序测试
- 1 个 with 语句测试

## Threat Model 实施情况

| Threat ID | Mitigation | Status |
|-----------|------------|--------|
| T-01-03 | 验证 PACKAGE_FILE_TAG 魔数 | 已实现 |
| T-01-04 | 文件大小检查（部分） | 需后续完善 |
| T-01-05 | 错误消息包含文件路径 | 已实现 |
| T-01-06 | 检查 length 值范围，拒绝异常值 | 已实现（1M 字符限制） |

## Self-Check: PASSED

- [x] archive.py 存在于 src/uasset_read/
- [x] test_archive.py 存在于 tests/
- [x] 170c9bf commit 存在于 git log
- [x] 378c921 commit 存在于 git log
- [x] 所有 68 个测试通过

## 下一步建议

- 后续 SummaryParser 将使用 `archive.set_version()` 设置版本
- 可考虑添加 `read_float/read_double` 方法
- 可考虑添加文件大小检查（T-01-04 完善）