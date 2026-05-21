---
status: testing
phase: 67-serialization-fixes
source: [phase-67 description from ROADMAP.md]
started: 2026-05-21T00:00:00Z
updated: 2026-05-21T16:00:00Z
---

## Current Test

number: 1
name: FPropertyTag UE5.4+ 格式兼容性
expected: |
  read_property_tag() 应正确处理 UE5.4+ 的 PropertyTag 完整类型名格式（FPropertyTypeName nodes 链式结构）。
  
  具体验证点：
  1. 能够读取 FPropertyTypeName 节点链（FName + int32 InnerCount）
  2. 正确构建嵌套类型字符串（如 "ArrayProperty(StructProperty(/Script/CoreUObject.Vector))"）
  3. 正确解析 PropertyTagFlags 扩展字段（HasArrayIndex, HasPropertyGuid, HasExtensions）
  
  测试资产：BP_FirstPersonCharacter.uasset
awaiting: user response

## Tests

### 1. FPropertyTag UE5.4+ 格式兼容性
expected: |
  read_property_tag() 应正确处理 UE5.4+ 的 PropertyTag 完整类型名格式（FPropertyTypeName nodes 链式结构）。
  
  具体验证点：
  1. 能够读取 FPropertyTypeName 节点链（FName + int32 InnerCount）
  2. 正确构建嵌套类型字符串（如 "ArrayProperty(StructProperty(/Script/CoreUObject.Vector))"）
  3. 正确解析 PropertyTagFlags 扩展字段（HasArrayIndex, HasPropertyGuid, HasExtensions）
  
  测试资产：BP_FirstPersonCharacter.uasset
result: [pending]

### 2. FString null termination 验证
expected: |
  read_fstring() 应移除 null 终止符，不依赖 null_ratio 启发式检测。
  
  具体验证点：
  1. UTF-8 FString 末尾的 b'\x00' 被正确移除
  2. UTF-16 FString 末尾的 b'\x00\x00' 被正确移除
  3. 非 null 终止字符串仍可读取（tolerant 模式下记录 warning）
  
  示例：单字符枚举名（如 "R"）应正确读取为 "R" 而不是 empty string
result: [pending]

### 3. StructProperty 解析容错性
expected: |
  parse_struct_property() 应在解析失败时跳过错误字节，不导致偏移错位。
  
  具体验证点：
  1. 未知 Struct 类型时，seek 到 pos + tag.size
  2. 不因单个属性解析失败影响后续属性
  3. 容错模式下记录警告而非抛出异常
  
  测试资产：BP_FirstPersonCharacter.uasset 的 BodyInstance 属性
result: [pending]

### 4. 集成测试：BP_FirstPersonCharacter 解析
expected: |
  完整解析 BP_FirstPersonCharacter.uasset，所有已知错误清零（或降级为 warning）。
  
  已知问题清单（应全部修复或降级为 warning）：
  1. ❌ FString 读到二进制数据（35处）→ ✅ null termination 验证
  2. ❌ LastEditedDocuments: Size 16777216 → ✅ UE5.4+ PropertyTag 格式
  3. ❌ SCSS_Node CategoryName: Cannot read 3328 bytes → ✅ 修复 #2 后自动修复
  4. ❌ BodyInstance: Size 524288 → ✅ 修复 #2 后自动修复
  5. ❌ RelativeLocation: Invalid size -1067974656 → ✅ 修复 #2 后自动修复
  6. ❌ RelativeRotation 字段错位 → ✅ 修复 #2 后自动修复
  
  测试命令：python -m uasset_read --parse BP_FirstPersonCharacter.uasset
result: [pending]

### 5. 单元测试：null_ratio 启发式移除
expected: |
  read_fstring() 不再依赖 null_ratio > 0.3 的启发式检测。
  
  边界测试：
  1. 纯二进制数据（null_ratio = 1.0）→ 应记录 warning 但仍返回 empty string
  2. 短字符串 "R"（null_ratio = 0.5，因为 1 字符 + 1 null）→ 应返回 "R"
  3. UTF-16 短字符串 "A\0\0\0" → 应返回 "A"
  
  验证方式：检查日志中无 "null_ratio" 警告（除了真正的二进制数据）
result: [pending]

## Summary

total: 5
passed: 0
issues: 0
pending: 5
skipped: 0
blocked: 0

## Gaps

[none yet]
