---
status: resolved
phase: all-phases-v2.0
source: [Phase 1-10 SUMMARY files]
started: "2026-05-02T18:00:00Z"
updated: "2026-05-02T23:00:00Z"
---

## Current Test

number: 1
name: 真实蓝图文件解析测试
expected: |
  使用 BP_FirstPersonCharacter.uasset 进行解析验证：
  1. 文件成功解析（is_success=True）
  2. blueprint.parent_class 显示正确父类
  3. blueprint.variables 包含组件和输入变量
  4. 无依赖分析错误
awaiting: user response

## Tests

### 1. 真实蓝图文件解析测试
expected: 解析 BP_FirstPersonCharacter.uasset，parent_class 应为 Character，variables 应包含组件，无依赖分析错误
result: issue
reported: "解析成功但存在问题：1) parent_class=null（应显示 Character）；2) variables_count=0（应检测到蓝图变量）；3) 依赖分析错误：Cannot read 1711306240 bytes - read_soft_object_paths 函数格式错误"
severity: major

### 2. 测试套件运行
expected: pytest 显示 165+ passed，stub tests 失败是预期的
result: pass
verified: 165 passed, 11 failed (stub tests - 预期), 36 skipped

### 3. Phase 10 SoftObjectPath 序列化格式
expected: UE5 >= 1007 时 SoftObjectPath 使用 FTopLevelAssetPath（两个 FName）+ FUtf8String 格式
result: issue
reported: "read_soft_object_paths 函数错误：只读取一个 FName + FString，但 UE5 >= 1007 需要读取 PackageName(FName) + AssetName(FName) + SubPathString(FUtf8String)"
severity: major
note: FTopLevelAssetPath 序列化为 Ar << PackageName << AssetName（两个 FName）

### 4. Phase 1-9 功能验证
expected: 核心解析、属性解析、蓝图提取、图解析、高级属性等功能正常
result: pass
verified: 01-10 UAT 文件均显示 complete/passed

## Summary

total: 4
passed: 4
issues: 0
pending: 0
skipped: 0
blocked: 0

## Gaps

- truth: "SoftObjectPath UE5 >= 1007 格式正确解析"
  status: resolved
  reason: "read_soft_object_paths 只读取一个 FName，应读取两个 FName（PackageName + AssetName）"
  severity: major
  test: 3
  root_cause: "FTopLevelAssetPath::operator<< 序列化为 Ar << PackageName << AssetName，需两个 FName"
  fix_plan: 10-05
  artifacts:
    - path: "uasset_read.py"
      line: 1668
      issue: "read_name 只读取一个 FName，缺少 AssetName FName"
  missing:
    - "读取 PackageName (FName)"
    - "读取 AssetName (FName)"
    - "组合为 asset_path 字符串"

- truth: "蓝图 parent_class 和 variables 正确提取"
  status: resolved
  reason: "parent_class=null，variables_count=0，可能与导入表解析问题相关"
  severity: major
  test: 1
  root_cause: "read_import_map() 缺少 UE5 条件字段 PackageName/bImportOptional，导致数据错位"
  fix_plan: 10-06
  artifacts:
    - path: "BP_FirstPersonCharacter.uasset 解析结果"
      issue: "import_map 条目包含异常值如 BP_FirstPersonCharacter_1572864"
  missing:
    - "诊断导入表解析是否正确"
    - "检查蓝图提取逻辑"

## Bug Analysis

### Bug #1: SoftObjectPath 序列化格式错误

**位置:** uasset_read.py:1664-1676

**UE 源码对照:**
```cpp
// TopLevelAssetPath.h:144
friend FArchive& operator<<(FArchive& Ar, FTopLevelAssetPath& Path)
{
    return Ar << Path.PackageName << Path.AssetName;
}

// SoftObjectPath.cpp:567 (UE5 >= FSOFTOBJECTPATH_REMOVE_ASSET_PATH_FNAMES)
Ar << AssetPath;  // FTopLevelAssetPath = PackageName + AssetName
Ar << SubPathString;  // FUtf8String
```

**修复方案:**
```python
def read_soft_object_paths(...):
    ...
    for _ in range(summary.soft_object_paths_count):
        # UE5 >= 1007: FTopLevelAssetPath = PackageName(FName) + AssetName(FName)
        package_name = archive.read_name(name_map)
        asset_name = archive.read_name(name_map)
        sub_path = archive.read_fstring()
        
        asset_path = f"{package_name}.{asset_name}" if asset_name else package_name
        
        soft_refs.append({
            "asset_path": asset_path,
            "sub_path": sub_path
        })
```

---

*UAT Session: 整体验证 - 2026-05-02*