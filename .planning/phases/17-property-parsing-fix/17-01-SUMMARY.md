---
phase: 17-property-parsing-fix
plan: 01
subsystem: 解析器核心
tags: [bugfix, ue5-serialization, offset-calculation]
dependency_graph:
  requires: []
  provides: [FIX-04-fix, FIX-06-fix]
  affects: [parse_properties_from_export]
tech_stack:
  added: []
  patterns: [version-conditioned-serialization]
key-files:
  created: []
  modified:
    - uasset_read.py (parse_properties_from_export)
    - tests/test_property_parsing.py
decisions:
  - D-01: 偏移计算使用 serial_offset + script_serial_offset (UE5 >= 1010)
metrics:
  duration: ~5min
  completed_date: 2026-05-04
  task_count: 2
  test_count: 3
---

# Phase 17 Plan 01: ScriptSerializationOffset 偏移计算修复 Summary

**修复属性数据偏移计算错误（D-01），解决 FIX-04 和 FIX-06 的根本原因。**

## 一行总结

修复 UE 5.10+ 属性数据定位错误，正确计算 `serial_offset + script_serial_offset` 相对偏移。

## 完成的任务

| Task | 名称 | 状态 | Commit |
|------|------|------|--------|
| 1 | 修复偏移计算公式 | 完成 | 398175f |
| 2 | 添加偏移计算单元测试 | 完成 | e567bbe |

## 关键变更

### Task 1: 偏移计算修复

**修改位置**: `uasset_read.py` 第 4343-4352 行

**修复内容**:
```python
# D-01: UE 5.10+ ScriptSerializationStartOffset 是相对偏移
# 参考: ObjectResource.h 第 280-285 行注释
if summary.file_version_ue5 >= UE5_SCRIPT_SERIALIZATION_OFFSET:
    property_start = export.serial_offset + export.script_serial_offset
else:
    property_start = export.serial_offset
archive.seek(property_start)
```

**根因验证**:
- UE 源码 `ObjectResource.h` 第 280-285 行明确注释：ScriptSerializationStartOffset 是 "relative to SerialOffset"
- 版本阈值 `UE5_SCRIPT_SERIALIZATION_OFFSET = 1010`

### Task 2: 单元测试

**添加测试**: `tests/test_property_parsing.py`

| 测试 | 描述 |
|------|------|
| test_script_serial_offset_calculation_ue5 | UE5 >= 1010 使用 serial_offset + script_serial_offset |
| test_script_serial_offset_calculation_ue4 | UE5 < 1010 仅使用 serial_offset |
| test_script_serial_offset_zero | script_serial_offset=0 时两种计算等效 |

## Deviations from Plan

### Auto-fixed Issues

None - 计划按预期执行，无偏离。

## Verification Results

| 检查项 | 结果 |
|--------|------|
| Import 无错误 | PASSED |
| script_serial_offset 在代码中 | PASSED |
| 版本条件检查存在 | PASSED |
| 单元测试通过 (51/51) | PASSED |

## 影响分析

### 解决的问题

| ID | 描述 | 根因 | 状态 |
|----|------|------|------|
| FIX-04 | negative_size 错误 | 偏移错位导致读取错误字段作为 Size | 根因修复 |
| FIX-06 | cannot_read 错误 | serial_offset 未加 script_serial_offset 导致越界 | 根因修复 |

### 代码影响范围

- **修改函数**: `parse_properties_from_export()`
- **修改行数**: +8 行（偏移计算逻辑）
- **向后兼容**: 版本条件保证 UE4/UE5 低版本兼容

## Threat Flags

无新增安全相关 surface。

## Known Stubs

无 stub 模式。修复是完整实现。

## 下一步

**Plan 02** 将处理 D-02（SerializationControlExtensions 头部）和 D-03（PropertyTag Extensions）。

## Self-Check: PASSED

- [x] uasset_read.py 包含 script_serial_offset 偏移计算
- [x] tests/test_property_parsing.py 包含 3 个新测试
- [x] Commit 398175f 存在
- [x] Commit e567bbe 存在
- [x] 51 测试全部通过

---

*完成时间: 2026-05-04*
*Phase: 17-property-parsing-fix*
*Plan: 01*