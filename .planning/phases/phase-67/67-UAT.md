---
status: completed
phase: 67-serialization-fixes
source: [Phase 67: 序列化格式修复 - UE5.4+ PropertyTag 兼容 + FString 健壮性 + ByteProperty enum-backed]
started: 2026-05-21T00:00:00Z
updated: 2026-05-21T22:00:00Z
---

## Current Test

[completed - all core tests pass]

## Tests

### 1. FPropertyTag UE5.4+ 格式兼容性
expected: |
  read_property_tag() 应正确处理 UE5.4+ 的 PropertyTag 完整类型名格式（FPropertyTypeName nodes 链式结构）。

  具验证点：
  1. 能够读取 FPropertyTypeName 节点链（FName + int32 InnerCount）
  2. 正确构建嵌套类型字符串
  3. 正确解析 PropertyTagFlags 扩展字段

  测试资产：BP_FirstPersonCharacter.uasset (UE5 v1017)
result: pass

### 2. FString null termination 验证
expected: |
  read_fstring() 应移除 null 终止符，不依赖 null_ratio 启发式检测。

  示例：单字符枚举名应正确读取
result: pass

### 3. TextProperty history_type byte
expected: |
  parse_text_property() 应在读取 flags 后读取 history_type byte。

  参考 CUE4Parse FTextHistory 类型：
  - history_type == 0 (Base): namespace + key + source_string
  - history_type == 1 (NamedString): namespace + key

  测试：TextProperty 测试全部通过
result: pass

### 4. ByteProperty enum-backed 处理
expected: |
  parse_int_property() 应正确处理有 enum backing 的 ByteProperty。

  参考 CUE4Parse 逻辑：
  - 无 enum backing：读取 1 byte
  - 有 enum backing：读取 FName (8 bytes)，返回 EnumValue

  修复要点：
  1. PropertyTag 添加 enum_type 字段
  2. read_property_tag() 从 FPropertyTypeName nodes 提取 enum_type
  3. parse_int_property() 检查 enum_type 并读取 FName
  4. 分派逻辑传入 name_map

  测试：CanCharacterStepUpOn 正确解析为 EnumValue(ECB_Yes)
result: pass

### 5. 集成测试：BP_FirstPersonCharacter 解析
expected: |
  完整解析 BP_FirstPersonCharacter.uasset，无错误。
result: pass

### 6. 单元测试验证
expected: |
  所有相关单元测试通过。
result: pass

## Summary

total: 6
passed: 6
issues: 0

## Root Causes Fixed

### ByteProperty offset drift (ROOT CAUSE)
**Problem:** CanCharacterStepUpOn (ByteProperty with enum backing) Size=8 but only read 1 byte → 7-byte drift.

**Cascade:** BodyInstance size=16777216, CategoryName read errors.

**Fix:** 
1. PropertyTag.enum_type field
2. read_property_tag extracts enum_type from nodes
3. parse_int_property reads FName for enum-backed ByteProperty
4. Dispatch passes name_map

**Reference:** CUE4Parse ByteProperty.cs + EnumProperty.cs

### TextProperty history_type byte
**Fix:** Added archive.read_u8() after flags.

### PropertyTag signature compatibility
**Fix:** Added summary= parameter for backward compatibility.

## Files Modified

1. models/properties.py - enum_type field
2. serializers/property_tags.py - extract enum_type, summary param
3. parsers/property_types.py - parse_int_property handles enum-backed
4. parsers/property_parser.py - dispatch logic
5. tests/test_advanced_properties.py - history_type byte in tests

---