---
phase: 31-graph-parsing
plan: 05
subsystem: tests
tags: [test-fix, api-alignment, legacy-shim]
requires: [31-04]
provides: [test_phase13_transform.py-fixed, test_phase26_blueprint_metadata_enhancement.py-fixed]
affects: []
key-decisions:
  - "Use parse_component_transform (new) instead of extract_component_transforms (legacy)"
  - "Use parse_property_flags_to_labels shim instead of non-existent FArchive._parse_property_flags"
  - "Add CPF_Edit and CPF_BlueprintVisible constants to public API exports"
tech-stack:
  added: []
  patterns: [dict-return-type, list-label-membership]
key-files:
  created: []
  modified:
    - tests/test_phase13_transform.py
    - tests/test_phase26_blueprint_metadata_enhancement.py
    - src/uasset_read/blueprint/variable_extractor.py
    - src/uasset_read/__init__.py
---

# Phase 31 Plan 05: Fix Test Files API Alignment Summary

修复 2 个测试文件的函数名/返回类型不匹配问题，使测试通过。

## 一句话概述

test_phase13 使用 parse_component_transform (dict 返回类型)，test_phase26 使用 parse_property_flags_to_labels (列表返回类型)，添加 CPF_Edit/CPF_BlueprintVisible 导出。

## 任务执行

| 任务 | 状态 | 提交 | 关键文件 |
|------|------|------|----------|
| Task 1: Fix test_phase13_transform.py | ✅ 完成 | 72cf64c | tests/test_phase13_transform.py, src/uasset_read/blueprint/variable_extractor.py |
| Task 2: Fix test_phase26_blueprint_metadata_enhancement.py | ✅ 完成 | a3af4d0 | tests/test_phase26_blueprint_metadata_enhancement.py, src/uasset_read/__init__.py |

## 偏差记录

### 自动修复问题

**1. [Rule 1 - Bug] 修复 _extract_vector/_extract_rotator 不处理 StructValue 类型**
- **发现于:** Task 1 测试运行时
- **问题:** `_extract_vector` 和 `_extract_rotator` 函数只检查 `isinstance(value, dict)`，不处理 `StructValue` dataclass 类型，导致测试返回默认值 0.0
- **修复:** 添加 `StructValue` 类型检查，从 `value.fields` 提取字段值
- **文件修改:** src/uasset_read/blueprint/variable_extractor.py
- **提交:** 72cf64c

**2. [Rule 2 - Critical] 添加 CPF_Edit 和 CPF_BlueprintVisible 常量导出**
- **发现于:** Task 2 测试导入时
- **问题:** `parse_property_flags_to_labels` 使用 `CPF_Edit` 常量触发 "EditAnywhere" 标签，但该常量未导出到公共 API
- **修复:** 添加 `CPF_Edit` (0x00000001) 和 `CPF_BlueprintVisible` (0x00000004) 到 `__init__.py` 导出列表
- **文件修改:** src/uasset_read/__init__.py
- **提交:** a3af4d0

## 验收标准验证

| 标准 | 结果 |
|------|------|
| test_phase13_transform.py: 0 failures (was 5) | ✅ 9 passed |
| test_phase26_blueprint_metadata_enhancement.py: 0 failures (was 2) | ✅ 7 passed |
| grep confirms extract_component_transforms replaced with parse_component_transform | ✅ 0 matches |
| grep confirms _parse_property_flags replaced with parse_property_flags_to_labels | ✅ 11 matches |
| grep confirms VectorValue/RotatorValue/ScaleValue imports removed from test_phase13 | ✅ 0 matches |
| grep confirms relative_scale3d key name used | ✅ 1 match |

## 测试结果

```
tests/test_phase13_transform.py: 9 passed
tests/test_phase26_blueprint_metadata_enhancement.py: 7 passed
总计: 16 passed, 0 failed
```

## 关键决策

1. **parse_component_transform vs extract_component_transforms**: 新版 API 返回 dict 类型（键名如 `relative_scale3d`），旧版返回 dataclass。测试改为使用 dict 键访问。

2. **parse_property_flags_to_labels vs _parse_property_flags**: FArchive 没有 `_parse_property_flags` 方法。使用 legacy shim 的 `parse_property_flags_to_labels` 函数，返回标签列表而非布尔标志字典。

3. **CPF_Edit vs CPF_EditAnywhere**: `parse_property_flags_to_labels` 检查 `CPF_Edit` (0x00000001) 触发 "EditAnywhere" 标签，而 `CPF_EditAnywhere` (0x02000000) 是不同用途的标志。

## 执行时间

- 开始时间: 2026-05-12T10:00:00Z (估算)
- 结束时间: 2026-05-12T10:15:00Z (估算)
- 持续时间: ~15 分钟
- 任务数: 2
- 文件修改数: 4

## Self-Check: PASSED

- tests/test_phase13_transform.py 存在且通过测试 ✅
- tests/test_phase26_blueprint_metadata_enhancement.py 存在且通过测试 ✅
- 提交 72cf64c 存在 ✅
- 提交 a3af4d0 存在 ✅