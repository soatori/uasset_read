---
phase: 02-property-parsing
plan: 03
subsystem: parsing
tags: [version-aware, ue4-ue5, propertyguid, arrayindex, flags]

requires:
  - phase: 02-property-parsing
    plan: 01
    provides: PropertyTag, read_property_tag, type parsers
  - phase: 02-property-parsing
    plan: 02
    provides: parse_properties_from_export, dispatch table
provides:
  - use_complete_type_name 版本辅助函数（增强）
  - UE5 PropertyTag 格式（通过 FString 的完整 TypeName）
  - UE4 PropertyTag 格式（短 FName + 字段）
  - 标志处理 (HasPropertyGuid, HasArrayIndex, BoolTrue)
  - __all__ 公共 API 导出
affects: [blueprint-extraction, output-cli]

tech-stack:
  added: []
  patterns: [version-threshold, conditional-field-reading]

key-files:
  created: []
  modified:
    - uasset_read.py
    - tests/test_property_parsing.py

key-decisions:
  - "UE5 >= 1000 使用通过 FString 的完整 TypeName 字符串"
  - "UE4 总是使用短 FName 作为类型"
  - "HasPropertyGuid 读取 16 字节 GUID"
  - "HasArrayIndex 读取 int32 ArrayIndex"
  - "BoolTrue 标志设置 tag.bool_val = 1"

patterns-established:
  - "通过 use_complete_type_name 辅助函数进行版本感知格式选择"
  - "基于 EPropertyTagFlags 的条件字段读取"

requirements-completed: [PROP-09]

duration: inline
completed: 2026-05-01
---

# Phase 2 Plan 03: 版本感知格式总结

**带版本阈值的 UE4/UE5 PropertyTag 格式处理，基于标志的条件字段 (HasPropertyGuid, HasArrayIndex)，公共 API 导出 (__all__)**

## 性能

- **时长:** 内联执行
- **任务:** 6 个已完成
- **测试:** 7 个新集成测试，62 个总计通过

## 成果
- use_complete_type_name 版本辅助函数（UE5 >= 1000 阈值）
- UE5 PropertyTag 格式: 通过 FString 的完整 TypeName + 基于标志的条件字段
- UE4 PropertyTag 格式: 短 FName + 总是存在的 ArrayIndex + 类型特定额外字段
- 标志处理: HasPropertyGuid (16 字节), HasArrayIndex (int32), BoolTrue (bool_val)
- __all__ 公共 API 导出已添加（20+ 导出）
- 7 个版本格式和标志的新集成测试

## 创建/修改的文件
- `uasset_read.py` - 添加 __all__ 导出，增强测试中的标志处理
- `tests/test_property_parsing.py` - 添加 7 个版本感知格式的集成测试

## 做出的决策
- UE5 格式: Type 作为 FString 读取（完整路径），UE4 格式: Type 作为 FName 读取（短名称）
- 版本阈值: legacy <= -8 且 ue5_version >= 1000 为 UE5 格式
- 条件字段: 仅当对应标志位设置时读取
- BoolTrue 标志: 设置 tag.bool_val = 1（值存储在 tag 中，不是数据）

## 与计划的偏差

### 自动修复的问题

**1. 测试中的 FString 长度不匹配**
- **发现时机:** T-18 测试执行
- **问题:** FString 长度值与实际字节计数不匹配（null 终止符处理）
- **修复:** 使用 len(type_bytes) 为 FString 测试计算正确长度
- **修改文件:** tests/test_property_parsing.py
- **验证:** 所有 35 个属性测试通过

---
**总偏差数:** 1 个自动修复
**对计划的影响:** 小型测试修正。无范围蔓延。

## 遇到的问题
- 测试中 null 终止符的 FString 长度计算（已修复）

## 下阶段准备
- 所有 Phase 2 属性解析完成（3 个 wave）
- UE4/UE5 的版本感知格式处理正常工作
- 62 个测试通过（35 属性 + 27 核心）
- 准备阶段验证

---
*Phase: 02-property-parsing*
*Plan: 03*
*完成: 2026-05-01*