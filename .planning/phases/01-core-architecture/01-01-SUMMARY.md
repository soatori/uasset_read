---
phase: 01-core-architecture
plan: 01
subsystem: constants-errors-types
tags: [tdd, foundation, ue-source-reference]
requires: []
provides: [constants, errors, types]
affects: [phase-02, phase-03, phase-04, phase-05]
tech_stack:
  added: [Python 3.14, pytest, dataclasses, IntEnum]
  patterns: [TDD RED/GREEN/REFACTOR, dataclass封装, source-location注释]
key_files:
  created:
    - src/uasset_read/__init__.py
    - src/uasset_read/constants.py
    - src/uasset_read/errors.py
    - src/uasset_read/types.py
    - tests/conftest.py
    - tests/test_constants.py
    - tests/test_errors.py
    - tests/test_types.py
  modified: []
decisions:
  - D-04: dataclass封装FPackageIndex和FPackageFileVersion
  - D-06: GUID映射单独定义在version.py（后续plan）
  - D-16: 四级日志配置ERROR/WARN/INFO/DEBUG
  - D-17: ParseError/MagicError/VersionError自定义异常
  - D-18: 异常包含file_path/offset/context丰富上下文
metrics:
  duration: "约 15 分钟"
  completed_date: "2026-05-01"
  test_count: 50
  test_passed: 50
  commits: 6
  files_created: 8
  ue_source_refs: 30+
---

# Phase 1 Plan 01: 基础模块 Summary

## 一句话总结

建立项目基础模块：包含 UE 魔数常量、版本枚举、自定义异常类和 FPackageIndex/FPackageFileVersion 封装类，所有常量均可追溯至 UE 源码定义。

## 完成状态

所有任务已完成，50 个测试全部通过。

## 交付物

### Task 1: 常量定义模块 (constants.py)

| 常量/枚举 | 值 | UE 源码位置 |
|-----------|-----|-------------|
| PACKAGE_FILE_TAG | 0x9E2A83C1 | ObjectVersion.h line 14 |
| PACKAGE_FILE_TAG_SWAPPED | 0xC1832A9E | ObjectVersion.h line 15 |
| VER_UE4_OLDEST_LOADABLE_PACKAGE | 214 | ObjectVersion.h line 114 |
| EUnrealEngineObjectUE4Version | 309 个版本 (214-522) | ObjectVersion.h lines 112-745 |
| EUnrealEngineObjectUE5Version | 19 个版本 (1000-1018) | ObjectVersion.h lines 40-109 |

每个枚举值都有源码位置注释，便于追溯验证。

### Task 2: 错误处理模块 (errors.py)

| 异常类 | 用途 | UE 源码关联 |
|--------|------|-------------|
| ParseError | 解析错误基类 | D-17, D-18 |
| MagicError | 魔数验证失败 | ObjectVersion.h 魔数定义 |
| VersionError | 版本过低/不支持 | ObjectVersion.h 版本定义 |
| FileOpenError | 文件无法打开 | D-17 |

日志配置：四级日志（ERROR/WARN/INFO/DEBUG），logger 实例名为 `uasset_read`。

### Task 3: 类型封装模块 (types.py)

| 类型 | 方法 | UE 源码位置 |
|------|------|-------------|
| FPackageIndex | is_import/is_export/is_null | ObjectResource.h lines 68-81 |
| FPackageIndex | to_import/to_export | ObjectResource.h lines 83-92 |
| FPackageIndex | from_import/from_export | ObjectResource.h lines 101-111 |
| FPackageFileVersion | is_ue5/to_value | ObjectVersion.h lines 783-793 |
| FPackageFileVersion | is_compatible | ObjectVersion.h lines 836-839 |

## TDD 执行记录

按照 TDD 流程执行，每个任务遵循 RED/GREEN/REFACTOR 周期：

| Task | RED Commit | GREEN Commit | 测试数 |
|------|------------|--------------|--------|
| Task 1 | 1c63282 | fc379dd | 12 |
| Task 2 | 010a4af | 50465a0 | 20 |
| Task 3 | 6ea4742 | a28a71e | 18 |

总计 6 个提交，50 个测试全部通过。

## Deviations from Plan

None - 计划完全按预期执行。

## 常量验证

所有常量值与 UE 源码一致：

```
PACKAGE_FILE_TAG = 0x9E2A83C1 ✓ (ObjectVersion.h line 14)
PACKAGE_FILE_TAG_SWAPPED = 0xC1832A9E ✓ (ObjectVersion.h line 15)
VER_UE4_OLDEST_LOADABLE_PACKAGE = 214 ✓ (ObjectVersion.h line 114)
VER_UE4_AUTOMATIC_VERSION = 522 ✓ (ObjectVersion.h line 744)
VER_UE5_INITIAL_VERSION = 1000 ✓ (ObjectVersion.h line 47)
VER_UE5_AUTOMATIC_VERSION = 1018 ✓ (ObjectVersion.h line 108)
```

## Threat Surface Scan

本 plan 未引入新的安全相关表面。所有模块均为基础定义：
- constants.py: 常量定义，不可篡改
- errors.py: 异常处理，无外部输入
- types.py: 数据封装，无 I/O 操作

## Known Stubs

None - 所有实现完整，无占位符。

## Self-Check: PASSED

- [x] 所有文件已创建并存在
- [x] 所有提交已记录 (6 commits)
- [x] 所有测试已通过 (50 passed)
- [x] 常量值与 UE 源码一致

---

## 下一步

- 01-02-PLAN: UAssetArchive 包装器（魔数验证、字节序检测）
- 依赖本 plan 的 constants.py 和 errors.py

*Completed: 2026-05-01*