---
phase: 01-core-parsing
plan: 01
subsystem: parser
tags: [core, parsing, uasset, ue5]
depends_on: []
provides:
  - FArchive binary reader with byte-swapping support
  - PackageFileSummary header parser
  - NameMap, ImportMap, ExportMap extraction
  - Asset class identification
  - Version validation and error handling
  - Unit test framework
affects:
  - Phase 02 (property parsing)
  - Phase 03 (blueprint extraction)
  - Phase 04 (output formatting)
tech-stack:
  added:
    - Python struct for binary unpacking
    - dataclasses for data models
    - tempfile for test file generation
    - pytest for unit testing
  patterns:
    - FArchive pattern (mirroring UE FArchive)
    - Byte-swapping detection via magic tag
    - PackageIndex signed encoding (>0 export, <0 import, 0 null)
key-files:
  created:
    - uasset_read.py (719 lines)
    - tests/test_uasset_read.py (549 lines)
  modified: []
decisions:
  - D-01: Single FArchive class (not hierarchical)
  - D-03: UE 5.x only focus
  - D-04: Strict version validation (legacy_version in [-2, -9], ue5_version >= 1000)
  - D-05: Store custom version GUIDs without validation
  - D-06: Use dataclasses for all models
  - D-07: PackageIndex stores raw int32 (delayed resolution)
  - D-08: Read all PackageFileSummary fields
  - D-10: FString UTF-8 only (UE 5.x standard)
  - D-11: Byte-swapping detection via magic tag comparison
  - D-12: Store PackageFlags without interpretation
  - D-14: Boundary validation for seek/read operations
  - D-15: Graceful degradation with partial results
metrics:
  duration: "2026-04-27T16:33:52Z - 2026-04-27T17:15:00Z"
  tasks_completed: 4
  files_created: 2
  tests_passed: 13
  lines_added: 1268
---

# 阶段 1 计划 01：核心解析器实现摘要

## 一句话概述

实现了完整的 UE 5.x .uasset 文件核心解析器，包含 FArchive 二进制读取器、PackageFileSummary 文件头解析、名称表/导入表/导出表提取、版本验证和错误处理，通过 13 个单元测试验证。

## 组件摘要

### 已实现组件

| 组件 | 描述 | 状态 |
|-----------|-------------|--------|
| **FArchive** | 二进制读取器，含字节交换、边界验证 | 完成 |
| **PackageFileSummary** | 文件头 dataclass，含所有字段 | 完成 |
| **CustomVersion** | 自定义版本 GUID 存储 | 完成 |
| **PackageIndex** | 有符号索引编码，含属性方法 | 完成 |
| **ObjectImport** | 导入表条目 dataclass | 完成 |
| **ObjectExport** | 导出表条目 dataclass | 完成 |
| **ParseResult** | 结果容器，支持部分数据 | 完成 |
| **read_package_summary** | 文件头解析器，含版本验证 | 完成 |
| **read_name_table** | UTF-8 名称表提取 | 完成 |
| **read_import_map** | 导入表解析器 | 完成 |
| **read_export_map** | 导出表解析器 | 完成 |
| **parse_uasset** | 主入口，含错误处理 | 完成 |
| **get_asset_class** | 从 class_index 识别资产类型 | 完成 |

### 测试覆盖

| 测试 | 目的 | 结果 |
|------|---------|--------|
| test_package_summary_valid | 有效 UE5 文件头解析 | PASSED |
| test_byte_swapping_detection | 字节交换检测 | PASSED |
| test_name_table_extraction | NameMap 提取 | PASSED |
| test_import_map | ImportMap 解析 | PASSED |
| test_export_map | ExportMap 解析 | PASSED |
| test_asset_class_identification | 资产类查找 | PASSED |
| test_unsupported_legacy_version | 版本错误处理 | PASSED |
| test_invalid_tag | 无效魔术标签错误 | PASSED |
| test_low_ue5_version | UE5 版本验证 | PASSED |
| test_package_index_properties | PackageIndex 属性 | PASSED |
| test_farchive_boundary_validation | Seek 边界检查 | PASSED |
| test_farchive_read_boundary | Read 边界检查 | PASSED |
| test_parse_result_structure | ParseResult 结构 | PASSED |

**总计：13 个测试，全部通过**

## 需求覆盖

| 需求 | 状态 | 备注 |
|-------------|--------|-------|
| CORE-01 | 已实现 | PackageFileSummary 含魔术标签、版本、偏移 |
| CORE-02 | 已实现 | 通过 PACKAGE_FILE_TAG_SWAPPED 检测字节交换 |
| CORE-03 | 已实现 | 从 NameOffset/NameCount 提取 NameMap |
| CORE-04 | 已实现 | 从 ImportOffset 提取 ImportMap |
| CORE-05 | 已实现 | 从 ExportOffset 提取 ExportMap |
| CORE-06 | 已实现 | 通过 get_asset_class 识别资产类 |
| CORE-07 | 已实现 | 自定义版本 GUID 已存储（按 D-05 不验证） |
| CORE-08 | 已实现 | 优雅失败，含清晰错误信息 |

## 与计划的偏差

### 自动修复的问题

**1. [规则 1 - Bug] 修复 PackageFileSummary dataclass 字段顺序**
- **发现时机：** 任务 4 测试执行
- **问题：** Python dataclass 报 TypeError: non-default argument follows default argument
- **修复：** 将 `custom_versions` 字段移至末尾，与其他有默认值字段在一起
- **修改文件：** uasset_read.py
- **提交：** bd99e61

其他无 —— 计划按预期执行，仅有此 Python dataclass 约束修复。

## 威胁标记

无 —— 无超出计划威胁模型的新安全相关表面。

## 已知桩代码

无 —— 所有核心功能已实现并测试。

## 未解决问题

无 —— 所有任务成功完成。

## 用户测试备注（D-17）

按计划的 D-17 决策，与真实 .uasset 文件的集成测试需要用户提供样本。

**推荐测试流程：**
```bash
# 用户提供 UE 5.x .uasset 文件
python uasset_read.py <user_file.uasset>

# 预期输出（文本格式 - 阶段 4 将实现）
# Summary:
#   Tag: 0x9E2A83C1
#   LegacyFileVersion: -8
#   UE5Version: 1000+
#   NameMap: X entries
#   ImportMap: Y entries
#   ExportMap: Z entries
```

**用户应验证：**
1. 魔术标签匹配预期值 0x9E2A83C1
2. 版本号在支持范围内
3. NameMap 包含预期的资产名称
4. ImportMap 显示正确的依赖关系
5. ExportMap 显示资产对象，含正确的 class_index

## 后续步骤

阶段 1 完成。准备阶段 2（属性解析）规划。

**生产使用的阻塞项：**
- CLI 接口（--json、--text 标志）- 阶段 4
- 真实 .uasset 文件集成测试 - 需要用户样本

---

*摘要创建：2026-04-27*
*执行器：Claude Code*
*计划：01-01-PLAN.md*