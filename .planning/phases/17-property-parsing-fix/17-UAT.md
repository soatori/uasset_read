---
status: complete
phase: 17-property-parsing-fix
source: [17-01-SUMMARY.md, 17-02-SUMMARY.md, 17-03-SUMMARY.md]
started: 2026-05-04T03:20:00Z
updated: 2026-05-04T03:25:00Z
---

## Current Test

[testing complete]

## Tests

### 1. UE 5.7 资产解析状态
expected: 解析 UE 5.7 资产返回 success 状态，无三类错误（negative_size、exceeds_remaining、cannot_read）
result: pass
details: is_success=True, errors=[], 69 exports, 56 properties parsed successfully

### 2. 单元测试通过
expected: 运行 pytest tests/ 全部测试通过（359 passed）
result: pass
details: 359 passed, 49 skipped in 0.88s

### 3. 偏移计算正确性
expected: 属性解析日志中 serial_offset + script_serial_offset 偏移计算正确，属性数据在有效范围内
result: pass
details: D-01 fix confirmed at line 4366, file_version_ue5=1017 > threshold 1010

### 4. SerializationControlExtensions 头部处理
expected: UE 5.11+ 资产解析时头部字节正确跳过，PropertyTag 位置正确
result: pass
details: D-02 fix confirmed at lines 4370-4383, threshold UE5_PROPERTY_TAG_EXTENSION=1011

### 5. PropertyTag Extensions 字段
expected: PropertyTag 结构包含扩展字段（override_operation、experimental_overridable_logic），解析无错误
result: pass
details: D-03 fix confirmed, PROP_TAG_HAS_EXTENSIONS=0x04, fields at lines 826-827, logic at lines 3576-3585

## Summary

total: 5
passed: 5
issues: 0
pending: 0
skipped: 0

## Gaps

[none yet]