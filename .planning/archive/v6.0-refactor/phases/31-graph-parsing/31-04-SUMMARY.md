---
phase: 31-graph-parsing
plan: 04
subsystem: legacy-compat
tags: [test-fix, shim-compat, FEdGraphPinType]
dependencies:
  requires: []
  provides: [format_variable_type-compat, test-data-fix]
  affects: [test_phase12_blueprint_variables.py, test_property_parsing.py]
tech_stack:
  added: []
  patterns: [getattr-fallback, pytest.skip]
key_files:
  created: []
  modified:
    - uasset_read_legacy.py
    - tests/test_phase12_blueprint_variables.py
    - tests/test_property_parsing.py
decisions:
  - D-01: Use getattr() for backward compat with missing FEdGraphPinType fields
  - D-02: Skip is_const test (field removed in v6.0)
  - D-03: Update ObjectProperty test to expect enhanced dict format
metrics:
  duration: 15min
  tasks_completed: 3
  files_modified: 3
  tests_fixed: 9
  completed_date: 2026-05-12
---

# Phase 31 Plan 04: Legacy Shim Compatibility Fix Summary

修复 9 个测试失败，通过修复 legacy shim 兼容性和测试数据构造。

## 一句话总结

使用 getattr() 兼容新 FEdGraphPinType 字段名，跳过已移除字段测试，更新 ObjectProperty 测试期望格式。

## 任务完成

| 任务 | 名称 | 状态 | 提交 |
|------|------|------|------|
| 1 | Fix format_variable_type shim compatibility | 完成 | 411a137 |
| 2 | Fix test_phase12_blueprint_variables.py is_const test | 完成 | 2130df5 |
| 3 | Fix test_property_parsing.py ObjectProperty expectations | 完成 | 128a8c0 |

## 详细修改

### Task 1: format_variable_type shim compatibility

修复 uasset_read_legacy.py 中的 format_variable_type 函数，使其兼容新的 FEdGraphPinType 数据类：

- **pin_subcategory 访问**: 使用 `getattr(pin_type, 'pin_subcategory', getattr(pin_type, 'pin_sub_category', ''))` 兼容新旧字段名
- **pin_subcategory_object 检查**: 使用 `getattr(pin_type, 'pin_subcategory_object', None) is not None` 代替 `!= 0`（新类型是 Optional[str]）
- **is_weak_pointer 访问**: 使用 `getattr(pin_type, 'is_weak_pointer', False)` 默认为强指针（添加 * 后缀）
- **is_const 访问**: 使用 `getattr(pin_type, 'is_const', False)` 默认无 const 前缀
- **docstring 更新**: pin_sub_category_object -> pin_subcategory_object

### Task 2: test_phase12_blueprint_variables.py

跳过 `test_format_const_type_adds_const_prefix` 测试，因为 FEdGraphPinType 在 v6.0 中移除了 is_const 字段。

### Task 3: test_property_parsing.py

更新两个 ObjectProperty 测试的期望值：

- **test_object_property_in_parse_properties**: 期望 ref dict 格式（parse_properties_from_export 增强逻辑会替换 int）
- **test_object_property_null_in_parse_properties**: 期望 int 0（null 引用不被增强）

## 偏离计划

### 自动修复

**1. [Rule 1 - Bug] is_weak_pointer 默认值修正**
- **发现于**: Task 1 验证阶段
- **问题**: 使用 True 作为默认值导致 object 类型没有 * 后缀
- **修复**: 改为 False 默认值，表示默认是强指针
- **文件**: uasset_read_legacy.py
- **提交**: 411a137

**2. [Rule 1 - Bug] ObjectProperty 测试期望格式调整**
- **发现于**: Task 3 验证阶段
- **问题**: 计划期望 int，但 parse_properties_from_export 增强逻辑会替换为 dict
- **修复**: 更新期望为实际的 ref dict 格式
- **文件**: tests/test_property_parsing.py
- **提交**: 128a8c0

## 验证结果

```bash
python -m pytest tests/test_phase12_blueprint_variables.py tests/test_property_parsing.py -v --tb=short
# 结果: 89 passed, 1 skipped in 0.43s
```

## 自检

- [x] format_variable_type works with new FEdGraphPinType
- [x] test_phase12_blueprint_variables.py: 0 failures (32 passed, 1 skipped)
- [x] test_property_parsing.py: 0 failures (57 passed)
- [x] grep 确认裸 pin_sub_category 访问已替换（format_variable_type 中）
- [x] grep 确认 is_const 测试已跳过
- [x] grep 确认 raw_index/resolved dict 期望已移除

## 自检: PASSED

所有修改文件已验证存在，所有提交已在 git log 中确认。