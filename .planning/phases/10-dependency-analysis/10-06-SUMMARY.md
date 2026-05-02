---
phase: 10-dependency-analysis
plan: 06
subsystem: import_map
tags: [gap-closure, ue5, conditional-fields, bug-fix]
dependency_graph:
  requires: [10-05]
  provides: [ObjectImport-package_name, ObjectImport-b_import_optional]
  affects: [read_import_map, blueprint-extraction]
tech_stack:
  added: [PKG_FilterEditorOnly constant]
  patterns: [Optional fields with None default]
key_files:
  created: []
  modified:
    - uasset_read.py (ObjectImport dataclass, read_import_map, PKG_FilterEditorOnly)
    - tests/test_uasset_read.py (test_import_map_ue5_condition_fields)
decisions:
  - D-10-06-01: Use Optional[str] and Optional[bool] for conditional fields with None default
metrics:
  duration: 5 minutes
  tasks_completed: 8
  test_results: 45 passed, 1 skipped
  completed_date: "2026-05-02T14:35:00Z"
---

# Phase 10 Plan 06: ImportMap UE5 条件字段修复 Summary

**修复 read_import_map() UE5 条件字段缺失问题，解决蓝图 parent_class=null 和 variables_count=0 的根因。**

## 问题诊断

**根因：** `read_import_map()` 函数已经读取了 UE5 条件字段（PackageName 和 bImportOptional），但在构造 ObjectImport 时没有传递这些值，导致数据没有被存储。虽然读取了额外数据，但 dataclass 缺少对应字段，造成后续条目偏移错位。

**影响：** import_map 数据错位导致蓝图提取失败（parent_class=null，variables_count=0）。

## 修改内容

### 1. ObjectImport dataclass 扩展

添加 UE5 条件字段：

```python
@dataclass
class ObjectImport:
    class_package: str
    class_name: str
    outer_index: PackageIndex
    object_name: str
    # UE5 条件字段（Phase 10 Gap #2 修复）
    package_name: Optional[str] = None   # PackageName（UEVer >= 518）
    b_import_optional: Optional[bool] = None  # bImportOptional（UEVer >= 1003）
```

### 2. read_import_map() 构造更新

修改 ObjectImport 构造传递新字段：

```python
import_map.append(ObjectImport(
    class_package=class_package,
    class_name=class_name,
    outer_index=outer_index,
    object_name=object_name,
    package_name=package_name,
    b_import_optional=b_import_optional
))
```

### 3. PKG_FilterEditorOnly 常量

添加 Package flags 常量：

```python
PKG_FilterEditorOnly = 0x00000080  # Filter editor-only objects
```

### 4. 默认值修正

将条件字段默认值从空字符串/False 改为 None，符合 Optional 类型语义。

## 测试验证

新增测试 `test_import_map_ue5_condition_fields`：
- 验证 UE5 >= 1003 时 PackageName 和 bImportOptional 正确读取
- 验证字段存储在 ObjectImport dataclass

测试结果：**45 passed, 1 skipped**（无回归）

## 提交记录

| Task | Commit | Files Modified |
|------|--------|----------------|
| Task 2-5 (合并) | 89e4082 | uasset_read.py |
| Task 7 | 608d1e9 | tests/test_uasset_read.py |

## Deviations from Plan

### 简化提交

将 Task 2, 3, 4, 5 合并为单一提交，因为修改紧密相关：
- Task 2: ObjectImport dataclass 扩展
- Task 3: UE 版本常量已存在（无需添加）
- Task 4: read_import_map() 构造更新
- Task 5: PKG_FilterEditorOnly 常量

**原因：** 分开提交会导致中间状态无法工作（dataclass 缺少字段但构造函数尝试传递）。

## Self-Check: PASSED

- [x] ObjectImport dataclass 包含 package_name 和 b_import_optional 字段
- [x] read_import_map() 传递新字段到 ObjectImport 构造
- [x] PKG_FilterEditorOnly 常量添加
- [x] 测试 test_import_map_ue5_condition_fields 通过
- [x] 所有现有测试通过（无回归）

---

*Phase 10 Plan 06 完成 - 2026-05-02*