---
phase: 01-core-architecture
plan: 03
subsystem: parser
tags:
  - summary
  - parser
  - version-detection
  - custom-version
requires:
  - archive-module
  - constants-module
  - types-module
provides:
  - PackageFileSummary
  - SummaryOffsets
  - FPackageFileSummaryParser
  - custom_version_count/offset for Plan 04
affects:
  - Plan 04 (CustomVersion parsing)
tech-stack:
  added:
    - dataclass for PackageFileSummary
    - version-aware field parsing
    - UE source code tracking
  patterns:
    - TDD development
    - version-gated field serialization
key-files:
  created:
    - src/uasset_read/parser/summary.py (450+ lines)
    - src/uasset_read/parser/__init__.py
    - tests/test_summary.py (600+ lines)
  modified: []
decisions:
  - PackageFileSummary as dataclass with 40+ fields
  - SummaryOffsets for version-dependent layout
  - Save custom_version_count/offset for Plan 04
  - Tag validation with unsigned conversion
metrics:
  duration: ~25 minutes
  completed_date: 2026-05-01
  test_count: 19 new tests, 87 total
  test_pass_rate: 100%
  coverage_estimate: 90%
---

# Phase 1 Plan 3: FPackageFileSummary Parser Summary

## One-liner

FPackageFileSummary 解析器实现版本检测、文件布局元数据解析，保存 CustomVersion 偏移供后续解析

## What was built

### PackageFileSummary dataclass

包含 40+ 字段的 dataclass，对应 UE PackageFileSummary.h 结构：

- 核心字段：tag, version (UE4+UE5), licensee_version, package_flags
- 表偏移：name_count/offset, export_count/offset, import_count/offset, depends_offset
- UE5 特有：saved_hash (20 bytes), payload_toc_offset, soft_object_paths, cell_export/import
- CustomVersion 支持：custom_version_count, custom_version_offset (供 Plan 04 使用)

### SummaryOffsets 类

版本感知偏移计算：

- 固定偏移常量：TAG=0, VERSION_UE4=12, VERSION_UE5=16
- 版本条件判断：has_custom_versions, has_saved_hash, has_payload_toc
- UE5 版本门控：PAYLOAD_TOC (1002), PACKAGE_SAVED_HASH (1016), IMPORT_TYPE_HIERARCHIES (1018)

### FPackageFileSummaryParser

完整序列化实现：

- 遵循 UE PackageFileSummary.cpp 序列化顺序
- LegacyFileVersion 处理 (-9 当前版本)
- UE5/UE4 双版本号解析
- SavedHash 条件读取 (UE5 >= 1016)
- CustomVersionContainer 偏移保存
- 所有表偏移正确解析
- 版本门控字段（SoftObjectPaths, CellExport, PayloadToc 等）

### 源码追踪

SUMMARY_FIELD_SOURCE 字典：

- 每个字段标注 UE 源码位置
- 便于追溯验证和文档生成

## Key decisions

1. **CustomVersion 偏移保存**：custom_version_offset 记录条目数组起始位置（不含 count），供 Plan 04 使用
2. **Tag 无符号转换**：用 `tag & 0xFFFFFFFF` 将有符号 int32 转换为无符号进行验证
3. **版本感知解析**：严格遵循 UE PackageFileSummary.cpp 的条件序列化逻辑
4. **测试数据生成**：创建完整的测试 uasset 数据模拟真实文件结构

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] log_warning vs log_warn 导入错误**
- **Found during:** 模块导入
- **Issue:** errors.py 中使用 log_warn 而非 log_warning
- **Fix:** 更正导入语句
- **Files modified:** src/uasset_read/parser/summary.py
- **Commit:** 同主提交

**2. [Rule 1 - Bug] Tag int32 验证错误**
- **Found during:** 测试运行
- **Issue:** 魔数 0x9E2A83C1 超出 int32 正数范围，read_int32 返回负数
- **Fix:** 用 `tag & 0xFFFFFFFF` 转换为无符号值验证
- **Files modified:** src/uasset_read/parser/summary.py
- **Commit:** 同主提交

**3. [Rule 3 - Blocking] 测试数据生成问题**
- **Found during:** 测试运行
- **Issue:** struct.pack('<i', 0x9E2A83C1) 失败，超出 int32 范围
- **Fix:** 使用 '<I' (无符号) 打包魔数，FGuid 字段也用无符号
- **Files modified:** tests/test_summary.py
- **Commit:** 同主提交

### Deferred Items

- UE4 专项测试：生成完整 UE4 测试数据复杂度高，核心功能已在 UE5 测试验证
- 真实 .uasset 文件测试：需从 UE 源码示例项目获取测试资产

## Test coverage

新增 19 个测试，覆盖：

- PackageFileSummary dataclass 字段验证 (4 tests)
- SummaryOffsets 偏移计算 (3 tests)
- FPackageFileSummaryParser 解析 (7 tests)
- CustomVersion 偏移保存 (2 tests)
- 模块导出验证 (3 tests)

## Files created/modified

| File | Lines | Purpose |
|------|-------|---------|
| src/uasset_read/parser/summary.py | 450+ | Parser implementation |
| src/uasset_read/parser/__init__.py | 25 | Module exports |
| tests/test_summary.py | 600+ | Unit tests |

## Next steps

Plan 04 将使用 custom_version_count 和 custom_version_offset 实现 CustomVersionContainer 解析。

## Verification

```bash
pytest tests/test_summary.py -v
# 19 passed

pytest tests/ -v
# 87 passed
```