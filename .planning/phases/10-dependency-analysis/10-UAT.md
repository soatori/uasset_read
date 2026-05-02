---
status: partial
phase: 10-dependency-analysis
source: [10-01-SUMMARY.md, 10-02-SUMMARY.md, 10-03-SUMMARY.md, 10-04-SUMMARY.md]
started: "2026-05-02T22:30:00Z"
updated: "2026-05-02T23:30:00Z"
---

## Current Test

[testing complete — 1 blocker found]

## Tests

### 1. ParseResult 依赖字段存在
expected: ParseResult 包含 imports/soft_references/circular_deps 字段，默认值为空数组
result: pass

### 2. build_imports_list 函数
expected: 将 ObjectImport 列表转换为 {class, package, object} dict 列表，合并重复三元组
result: pass

### 3. read_soft_object_paths 版本判断
expected: UE4 文件返回空数组，UE5 < 1008 返回空数组，UE5 >= 1008 尝试解析
result: pass

### 4. detect_circular_deps 高密度依赖检测
expected: 同一 class_package 被多次引用时返回 [pkg, pkg] 格式的高密度依赖警告
result: pass

### 5. JSON 输出包含依赖字段
expected: format_json_full() 返回的字典包含 imports, soft_references, circular_deps 键
result: pass

### 6. parse_uasset 集成验证
expected: parse_uasset() 解析文件后，ParseResult 的 imports/soft_references/circular_deps 字段被正确填充
result: issue
reported: "imports[0] 正确（AnimBlueprintGeneratedClass /Script/Engine ABP_Unarmed_C），但 imports[1-72] 全部乱码（class_name 变成路径片段如 BP_FirstPersonCharacter_2）；soft_references 为空（0 条，预期有 blueprint 引用）；circular_deps 为空（imports 数据损坏导致）。错误信息：'Cannot read 1711306240 bytes at position 38257'"
severity: blocker

## Summary

total: 6
passed: 5
issues: 1
pending: 0
skipped: 0

## Gaps

- truth: "parse_uasset() 解析文件后，imports/soft_references/circular_deps 字段应正确填充"
  status: failed
  reason: "User reported: imports[0] 正确（AnimBlueprintGeneratedClass /Script/Engine ABP_Unarmed_C），但 imports[1-72] 全部乱码；soft_references 为空（0 条）；circular_deps 为空。错误信息：'Cannot read 1711306240 bytes at position 38257'"
  severity: blocker
  test: 6
  root_cause: "UE 5.x 未烘焙文件中 FObjectImport 使用 FStructuredArchive 序列化（标签+值记录格式），而 read_import_map() 读取原始顺序 FName 字段。仅第一个导入碰巧正确，后续全部错位。UE 源码 ObjectResource.cpp 第 347-380 行确认 FObjectImport 使用 FStructuredArchive::FRecord 格式，包含 ClassPackage/ClassName/OuterIndex/ObjectName 等命名标签字段。"
  artifacts:
    - path: "uasset_read.py L1531-1570"
      issue: "read_import_map() 使用原始顺序 FName 读取，不支持 FStructuredArchive 格式"
    - path: "UnrealEngine/Engine/Source/Runtime/CoreUObject/Private/UObject/ObjectResource.cpp L347-380"
      issue: "UE 5.x FObjectImport 的 FStructuredArchive 序列化定义"
  missing:
    - "FStructuredArchive 记录解析器（或 UE5 未烘焙文件专用的导入表读取逻辑）"
  debug_session: ""
