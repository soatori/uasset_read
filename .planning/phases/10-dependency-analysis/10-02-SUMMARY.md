---
phase: 10-dependency-analysis
plan: 02
status: complete
date: "2026-05-02"
---

## 10-02: 依赖解析核心函数

**Objective:** 实现 build_imports_list() 和 read_soft_object_paths() 两个依赖解析核心函数。

**Completed:** 两个函数均实现并通过验证。build_imports_list() 位于 read_import_map() 之后（L1571），使用 set 去重。read_soft_object_paths() 位于 build_imports_list() 之后（L1602），包含版本条件检查（legacy_file_version <= -8 且 file_version_ue5 >= 1008）和边界检查。

### Key Files Created/Modified
- `uasset_read.py` L1571-1640: build_imports_list() 和 read_soft_object_paths()

### Self-Check: PASSED
- def build_imports_list ✓
- def read_soft_object_paths ✓
- "class": imp.class_name ✓
- "asset_path": asset_path ✓
- "sub_path": sub_path ✓
- UE5_ADD_SOFTOBJECTPATH_LIST version check ✓
