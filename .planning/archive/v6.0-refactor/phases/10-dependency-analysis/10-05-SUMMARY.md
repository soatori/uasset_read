---
phase: 10-dependency-analysis
plan: 05
subsystem: dependency-analysis
tags: [gap-closure, soft-object-path, ue5-version, ftop-level-asset-path]
dependency_graph:
  requires: [10-04]
  provides: [DEPS-02-fix]
  affects: [read_soft_object_paths, test_dependency_analysis]
tech_stack:
  added: [UE5_FSOFTOBJECTPATH_REMOVE_ASSET_PATH_FNAMES constant]
  patterns: [version-branch-serialization, ftop-level-asset-path]
key_files:
  created: []
  modified:
    - uasset_read.py (L74, L1635-1704)
    - tests/test_dependency_analysis.py (L201-349)
decisions:
  - D-10-05-01: UE5 >= 1007 使用 FTopLevelAssetPath 格式（双 FName）
  - D-10-05-02: asset_path 组合为 PackageName.AssetName 格式
metrics:
  duration: "15 minutes"
  completed_date: "2026-05-02T14:35:00Z"
  task_count: 4
  file_count: 2
  test_count: 3
---

# Phase 10 Plan 05: SoftObjectPath UE5 >= 1007 格式修复 Summary

## 一句话总结

修复 read_soft_object_paths() 函数，正确处理 UE5 >= 1007 的 FTopLevelAssetPath 格式（PackageName + AssetName 双 FName 序列化）。

## 完成的任务

| Task | 名称 | Commit | 文件 |
|------|------|--------|------|
| 1 | 添加版本常量 | 4a3d2ec | uasset_read.py (L74) |
| 2 | 重构 read_soft_object_paths | 4c3f1d8 | uasset_read.py (L1635-1704) |
| 3 | 添加单元测试 | e8ecc9b | tests/test_dependency_analysis.py (L201-349) |
| 4 | 测试套件验证 | - | 验证无回归 |

## 关键变更

### 1. UE5 版本常量添加

在 uasset_read.py L74 添加：
```python
UE5_FSOFTOBJECTPATH_REMOVE_ASSET_PATH_FNAMES = 1007  # FSOFTOBJECTPATH_REMOVE_ASSET_PATH_FNAMES
```

此常量对应 UE ObjectVersion.h 中的版本号，用于检测 FTopLevelAssetPath 格式。

### 2. read_soft_object_paths() 函数重构

添加版本分支逻辑：
- **UE5 >= 1007**: 读取 PackageName(FName) + AssetName(FName) + SubPathString(FString)
- **UE5 < 1007**: 读取 AssetPathName(FName) + SubPathWide(FString)

asset_path 组合逻辑：
```python
if asset_name:
    asset_path = f"{package_name}.{asset_name}"
else:
    asset_path = package_name
```

### 3. 单元测试覆盖

添加三个新测试：
- `test_read_soft_object_paths_ue5_1008_ftoplevelassetpath`: 验证双 FName 格式
- `test_read_soft_object_paths_ue5_1016_format`: 验证典型 UE5 版本
- `test_read_soft_object_paths_ue5_1008_empty_asset_name`: 验证空 AssetName 边缘情况

## UE 源码对照验证

**SoftObjectPath.cpp L555-591:**
```cpp
else if (Ar.UEVer() < FSOFTOBJECTPATH_REMOVE_ASSET_PATH_FNAMES)
{
    // UE5 < 1007: 单 FName + FWideString
    FName AssetPathName;
    Ar << AssetPathName;
    FWideString SubPathWide;
    Ar << SubPathWide;
}
else
{
    // UE5 >= 1007: FTopLevelAssetPath (双 FName)
    Ar << AssetPath;  // PackageName + AssetName
    Ar << SubPathString;
}
```

**TopLevelAssetPath.h L144:**
```cpp
friend FArchive& operator<<(FArchive& Ar, FTopLevelAssetPath& Path)
{
    return Ar << Path.PackageName << Path.AssetName;  // 两个 FName
}
```

实现与 UE 源码完全一致。

## 测试结果

| 测试套件 | 结果 | 状态 |
|----------|------|------|
| Phase 10 测试 | 17 passed | 全部通过 |
| 完整测试套件 | 168 passed, 11 failed (stub), 36 skipped | 无回归 |

11 个失败的测试是预期的 stub tests（TODO 测试），已在 ALL-V2-UAT.md 中记录。

## Deviations from Plan

None - plan executed exactly as written.

## Threat Flags

None - no new security surface introduced beyond existing read_name/read_fstring boundaries.

## Self-Check: PASSED

- uasset_read.py 包含 UE5_FSOFTOBJECTPATH_REMOVE_ASSET_PATH_FNAMES 常量 (L74)
- read_soft_object_paths() 包含版本分支 (L1674-1692)
- test_dependency_analysis.py 包含 3 个新测试 (L201, L255, L302)
- 所有测试通过
- Commits 存在于 git log (4a3d2ec, 4c3f1d8, e8ecc9b)

---

*Phase: 10-dependency-analysis*
*Plan: 05*
*Gap Closure: SoftObjectPath UE5 >= 1007 format fix*
*Completed: 2026-05-02T14:35:00Z*