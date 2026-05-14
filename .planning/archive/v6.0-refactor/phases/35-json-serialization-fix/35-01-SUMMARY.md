---
phase: "35"
plan: 01
subsystem: formatters
tags: [json, serialization, bugfix]
dependency_graph:
  requires: []
  provides:
    - "JSON 序列化 helper: serialize_property_value"
    - "format_properties_list 修复"
  affects:
    - "CLI --json 输出"
tech_stack:
  added: []
  patterns:
    - "dataclass to dict serialization with depth protection"
key_files:
  created: []
  modified:
    - src/uasset_read/formatters/json_formatter.py
decisions:
  - "使用 hasattr 类型检测而非 isinstance，避免导入循环并保持灵活性"
  - "递归深度保护默认 max_depth=10，超过返回 '[deep nesting truncated]'"
metrics:
  duration: "~5min"
  completed_date: "2026-05-12"
  tests: "397 passed, 71 skipped, 0 failed"
---

# Phase 35 Plan 01: JSON 序列化修复 Summary

## 一句话摘要

修复 `--json` 模式下 StructValue/MapValue/EnumValue/TextValue/DelegateValue/SetValue 序列化崩溃（P0 阻塞级 bug），添加 `serialize_property_value` helper 并集成到 `format_properties_list`。

## 完成的工作

### Task 1: 添加 serialize_property_value helper 并修复 format_properties_list

**修改文件**: `src/uasset_read/formatters/json_formatter.py`

**变更内容**:
1. 添加 `serialize_property_value(value, depth=0, max_depth=10)` 函数（L134-187），将高级 dataclass 转换为 JSON 兼容 dict
2. 处理 6 种高级属性类型：
   - StructValue -> `{"struct_type": ..., "fields": {...}}`
   - MapValue -> `{"key_type": ..., "value_type": ..., "entries": [...]}`
   - SetValue -> `{"element_type": ..., "elements": [...]}`
   - EnumValue -> `{"enum_type": ..., "value": ...}`
   - TextValue -> `{"namespace": ..., "key": ..., "source_string": ...}`
   - DelegateValue -> `{"object_ref": ..., "function_name": ...}`
3. 原生类型（None/str/int/float/bool/list/dict）直接返回不变
4. 递归深度保护：`max_depth=10`，超过返回 `"[deep nesting truncated]"`
5. 修改 `format_properties_list` 调用 `serialize_property_value(prop.value)` 替代直接使用 `prop.value`
6. 添加运行时 import：`StructValue, MapValue, SetValue, EnumValue, TextValue, DelegateValue`

## Deviations from Plan

None - plan executed exactly as written.

## Known Stubs

None.

## Threat Flags

无新增威胁面。`serialize_property_value` 已实现递归深度保护（mitigate T-35-01）。

## Self-Check: PASSED

- [x] serialize_property_value 函数存在并被 format_properties_list 正确调用
- [x] 6 种高级类型序列化测试通过
- [x] 原生类型透传测试通过
- [x] 递归深度保护测试通过
- [x] 全部测试 397 passed, 71 skipped, 0 failed
