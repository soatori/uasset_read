---
phase: 06-export-table-fix
plan: 01
status: complete
completed: 2026-05-02
commit: 79e21c3
---

# Phase 6 Plan 01: 导出表修复 - 实现完成

## Summary

成功修复 v1.0 导出表解析的 FObjectExport 结构缺失字段问题，实现完整的导出表解析。

## What Was Built

### 1. ErrorContext 结构扩展（D-12/D-13/D-14）

新增导出表解析阶段信息字段：
- `export_index: Optional[int]` — 当前导出索引（0-based）
- `expected_offset: Optional[int]` — 期望偏移
- `actual_offset: Optional[int]` — 实际偏移
- `field_name: str` — 字段名（如 "TemplateIndex"）
- `version_info: Dict[str, int]` — 版本检查失败信息

### 2. ObjectExport dataclass 扩展（D-16/D-17）

新增缺失字段：
- `template_index: PackageIndex` — TemplateIndex（UE4 >= 506）
- `b_forced_export: bool` — 强制导出标志
- `b_not_for_client: bool` — 非客户端标志
- `b_not_for_server: bool` — 非服务器标志
- `b_is_inherited_instance: Optional[bool]` — 继承实例标志（UE5 >= 1011）
- `package_flags: int` — 包标志
- 其他条件 bool flags

### 3. FArchive 方法扩展

新增 `read_bytes(n: int) -> bytes` 方法，用于读取原始字节（无字节序交换）。

### 4. read_export_map 函数重构（D-05）

严格按 ObjectResource.cpp 第 130-217 行顺序：
1. ClassIndex → 2. SuperIndex → 3. TemplateIndex(条件) → 4. OuterIndex →
5. ObjectName → 6. ObjectFlags → 7-8. SerialSize/Offset →
9-11. bool flags → 12. PackageGuid(条件) → 13. bIsInheritedInstance(条件) →
14. PackageFlags → 15-17. 其他 bool flags → 19-20. ScriptSerialization

### 5. UE5 版本处理修复

UE5 文件（legacy <= -8）自动满足所有 UE4 版本条件，使用 `effective_ue4_version = 1000`。

### 6. 版本常量定义

新增：
- `VER_UE4_TemplateIndex_IN_COOKED_EXPORTS = 506`
- `VER_UE4_64BIT_EXPORTOFFSETS = 508`
- `UE5_REMOVE_OBJECT_EXPORT_PACKAGE_GUID = 1010`
- `UE5_TRACK_OBJECT_EXPORT_IS_INHERITED = 1011`
- `UE5_GENERATE_PUBLIC_HASH = 1015`

## Key Decisions

- **D-01:** 统一版本检查 file_version_ue4 >= 506（UE5 文件自动满足）
- **D-05:** 严格按 UE 源码顺序序列化，避免偏移错位
- **D-06:** 依赖数组推迟到 Phase 10（依赖分析阶段）
- **D-07:** bool flags 各读取 1 byte（UE bool 序列化格式）
- **D-10/D-11:** PackageGuid 条件读取但不存储（保持偏移正确）

## Deviations

None — 实现完全按计划执行。

## Test Results

```
tests/test_uasset_read.py: 27 passed, 1 skipped
```

所有现有测试通过，无回归。

## Files Modified

- `uasset_read.py` — 核心修复实现（+190 行，-46 行）
- `tests/test_uasset_read.py` — 测试数据生成更新（+28 行）

## Commit

```
79e21c3 fix(export-map): complete FObjectExport structure parsing (Phase 6 BUG-01/BUG-02)
```

---

*Completed: 2026-05-02*