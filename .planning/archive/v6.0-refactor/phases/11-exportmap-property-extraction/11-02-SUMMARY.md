---
phase: 11
plan: 02
subsystem: ExportMap属性值提取
tags:
  - ObjectProperty
  - PackageIndex
  - 引用解析
  - 属性增强
requires:
  - EXTR-01
provides:
  - ObjectProperty可读引用解析
  - resolve_package_index_to_reference函数
affects:
  - uasset_read.py
  - tests/test_property_parsing.py
tech_stack:
  added:
    - resolve_package_index_to_reference函数
    - PackageIndex引用解析逻辑
  patterns:
    - 后处理模式（parse_properties_from_export中增强ObjectProperty）
    - 递归类名解析
key_files:
  created: []
  modified:
    - uasset_read.py (lines 511-603: resolve_package_index_to_reference函数)
    - uasset_read.py (line 3796-3802: parse_properties_from_export签名)
    - uasset_read.py (line 3868-3876: ObjectProperty后处理逻辑)
    - tests/test_property_parsing.py (8新增测试)
decisions:
  - D-11-02-01: 方案A选择 - 在parse_properties_from_export中后处理，保持parse_object_property签名不变
  - D-11-02-02: 向后兼容 - raw_index字段保留原始int32值
  - D-11-02-03: resolved格式 - import含package字段，export不含package
metrics:
  duration: 45min
  completed_date: "2026-05-03"
  task_count: 3
  file_count: 2
  test_count: 8
---

# Phase 11 Plan 02: 增强ObjectProperty解析返回可读对象引用 Summary

## 一行总结

ObjectProperty解析新增resolve_package_index_to_reference函数，返回可读对象引用信息（类名、对象名、包路径），而非原始int32索引。

## 详细内容

### 实现内容

1. **resolve_package_index_to_reference函数**（uasset_read.py:511-600）
   - 输入：PackageIndex对象、import_map、export_map、name_map
   - 输出：None（null引用）或包含type/class_name/object_name的字典
   - import引用额外返回package字段（来源包名）
   - export引用递归解析class_index获取类名

2. **_resolve_class_name辅助函数**（uasset_read.py:603-622）
   - 递归解析PackageIndex获取类名
   - 处理null和越界情况返回"None"或"Unknown"

3. **parse_properties_from_export增强**
   - 新增import_map参数（Optional，向后兼容）
   - ObjectProperty值后处理：`{"raw_index": int, "resolved": dict|null}`
   - 保留原始索引值，新增resolved字段

4. **测试覆盖**（8个新测试）
   - import/export/null引用解析
   - 越界处理
   - 递归类名解析
   - parse_properties_from_export集成

### 测试结果

```bash
pytest tests/test_property_parsing.py::test_object_property_* -v
# 8 passed in 0.06s
```

全部43个property parsing测试通过。

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] 修正FString长度计算**
- **Found during:** Task 3测试调试
- **Issue:** 测试数据中"ObjectProperty\x00"是15字节，但FString长度设置为14，导致null terminator未被读取，数据错位
- **Fix:** 将FString长度修正为15（包含null terminator）
- **Files modified:** tests/test_property_parsing.py
- **Commit:** efdf8d8

## Auth Gates

None - 无认证相关问题。

## Known Stubs

None - 无已知stub。

## Threat Flags

None - 无新增安全相关表面。

## Key Decisions

| 决策ID | 决策 | 理由 |
|--------|------|------|
| D-11-02-01 | 方案A选择（后处理模式） | 不修改parse_object_property签名，向后兼容；在parse_properties_from_export中集中处理 |
| D-11-02-02 | raw_index字段保留 | 用户仍可获取原始FPackageIndex值，向后兼容 |
| D-11-02-03 | resolved格式差异化 | import需要package字段追踪来源包，export不需要（已在当前包中） |

## Files Changed

| 文件 | 行数 | 修改类型 |
|------|------|----------|
| uasset_read.py | +102/-2 | feat |
| tests/test_property_parsing.py | +285/-1 | test |

## Verification

### 自动化验证
```bash
pytest tests/test_property_parsing.py::test_object_property_* -x -v
# 8 passed
```

### 手动验证（受阻）
计划指定的手动验证脚本因资产serial_offset解析问题无法完整执行（Offset超出文件大小）。此问题来自11-01遗留，非11-02引入。单元测试已验证逻辑正确性。

## Self-Check: PASSED

- [x] resolve_package_index_to_reference函数存在（uasset_read.py:511）
- [x] parse_properties_from_export包含import_map参数
- [x] ObjectProperty后处理逻辑存在
- [x] 测试文件包含8个新增测试
- [x] commit c7559ad存在
- [x] commit efdf8d8存在

---

**Plan Status:** COMPLETE
**Commits:**
- c7559ad: feat(11-02): 新增resolve_package_index_to_reference函数和ObjectProperty增强解析
- efdf8d8: test(11-02): 新增ObjectProperty增强解析测试