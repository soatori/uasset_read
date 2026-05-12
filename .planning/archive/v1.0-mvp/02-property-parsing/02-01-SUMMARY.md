---
phase: 02-property-parsing
plan: 01
subsystem: parsing
tags: [propertytag, uasset, binary-parsing, ue5, ue4]

requires:
  - phase: 01-core-parsing
    provides: FArchive, PackageFileSummary, NameMap, ExportMap
provides:
  - PropertyTag dataclass 和解析
  - PropertyValue 容器
  - 类型特定解析器 (Bool, Int, Float, Str, Name)
  - 版本检测 (UE4/UE5 格式切换)
  - PropertyTag 标志常量
affects: [02-02, 02-03, blueprint-extraction]

tech-stack:
  added: []
  patterns: [function-dispatch, version-aware-parsing]

key-files:
  created:
    - tests/test_property_parsing.py
  modified:
    - uasset_read.py

key-decisions:
  - "PropertyTag 对于版本 >= 1000 使用 UE5 完整 TypeName 格式"
  - "BoolProperty 值来自 tag.bool_val 标志，无额外数据"
  - "UE4 格式总是有 ArrayIndex 字段，UE5 使用 HasArrayIndex 标志"
  - "FArchive 添加 read_f64() 以支持 DoubleProperty"

patterns-established:
  - "通过 type_dispatch 字典进行属性解析的函数分派"
  - "通过 use_complete_type_name 辅助函数进行版本感知格式选择"

requirements-completed: [PROP-01, PROP-02, PROP-03, PROP-04, PROP-05, PROP-06, PROP-09]

duration: inline
completed: 2026-05-01
---

# Phase 2 Plan 01: PropertyTag 解析总结

**PropertyTag dataclass, 带 UE4/UE5 版本感知格式的 read_property_tag, 以及 Bool, Int, Float, Str, Name 属性的类型特定解析器**

## 性能

- **时长:** 内联执行（无子代理）
- **任务:** 8 个已完成
- **测试:** 21 个新测试，48 个总计通过

## 成果
- PropertyTag 和 PropertyValue dataclasses 已添加到 uasset_read.py
- 带 UE4/UE5 格式切换的 read_property_tag 函数
- use_complete_type_name 版本阈值辅助函数
- PropertyTag 标志常量 (PROP_TAG_HAS_ARRAY_INDEX, PROP_TAG_HAS_PROPERTY_GUID, PROP_TAG_BOOL_TRUE 等)
- 类型特定解析器: parse_bool_property, parse_int_property, parse_float_property, parse_str_property, parse_name_property
- parse_property_value 分派函数
- FArchive 添加 read_f64() 方法以支持 DoubleProperty
- 完整测试文件 tests/test_property_parsing.py (21 个测试)

## 创建/修改的文件
- `uasset_read.py` - 添加 PropertyTag/PropertyValue dataclasses, 标志常量, read_property_tag, 类型解析器, read_f64()
- `tests/test_property_parsing.py` - 新测试文件，包含 21 个属性解析测试

## 做出的决策
- UE5 格式使用完整 TypeName 字符串（通过 FString），UE4 使用短 FName
- BoolProperty 值存储在 tag.bool_val 标志位，无序列化数据
- UE4 格式总是包含 ArrayIndex，UE5 仅当 HasArrayIndex 标志设置时
- FArchive 添加 read_f64() 以支持 DoubleProperty（之前缺失）
- 未知属性类型返回 None（跳过策略）

## 与计划的偏差

### 自动修复的问题

**1. 测试中的 FString 长度不匹配**
- **发现时机:** T-08 测试执行
- **问题:** 测试 FString 长度不正确（如 "FloatProperty" = 13 字符 + null = 14 字节，不是 12）
- **修复:** 更正 test_property_parsing.py 中所有 FString 长度值
- **修改文件:** tests/test_property_parsing.py
- **验证:** 所有 21 个测试通过

**2. FArchive 缺失 read_f64()**
- **发现时机:** T-08 测试执行
- **问题:** parse_float_property 对 DoubleProperty 调用 read_f64()，但 FArchive 缺失该方法
- **修复:** 添加 read_f64() 方法到 FArchive 类
- **修改文件:** uasset_read.py
- **验证:** DoubleProperty 测试通过

---
**总偏差数:** 2 个自动修复
**对计划的影响:** 小型测试/实现修正。无范围蔓延。

## 遇到的问题
- 测试 FString 长度计算需要修正（次要）
- FArchive 缺失 read_f64() 方法（已添加）

## 下阶段准备
- PropertyTag 解析基础设施已准备好用于 Wave 2 (ObjectProperty, ArrayProperty)
- 版本感知格式选择对 UE4/UE5 正常工作
- 所有 48 个测试通过（21 新增 + 27 现有）

---
*Phase: 02-property-parsing*
*Plan: 01*
*完成: 2026-05-01*