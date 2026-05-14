---
phase: "35"
plan: 04
type: execute
wave: 1
subsystem: blueprint/variable_extractor
tags: [bug-fix, metadata-filtering, p2]
dependency_graph:
  requires: []
  provides:
    - "extract_blueprint_variables 过滤 Blueprint 元数据属性"
  affects:
    - "BlueprintMetadata.variables 列表内容"
    - "所有调用 extract_blueprint_variables 的代码路径"
tech-stack:
  added: []
  patterns: ["blacklist filtering", "frozenset constant"]
key-files:
  created: []
  modified:
    - "src/uasset_read/blueprint/variable_extractor.py"
decisions:
  - "使用黑名单而非白名单过滤元数据属性，避免误过滤合法用户变量"
  - "BLUEPRINT_METADATA_PROPERTY_NAMES 包含 None/NoneProperty 终止标记（替代原有的内联检查）"
metrics:
  duration: "< 5 min"
  completed: "2026-05-12"
---

# Phase 35 Plan 04: Blueprint 变量元数据过滤 Summary

## One-liner

为 `extract_blueprint_variables` 添加 Blueprint 元数据属性黑名单过滤，使变量列表只包含用户定义的变量。

## Completed Tasks

| # | Task | Commit | Files Modified |
|---|------|--------|----------------|
| 1 | 添加元数据属性过滤 | fd871f2 | `src/uasset_read/blueprint/variable_extractor.py` |

## Deviations from Plan

None - plan executed exactly as written.

## Verification Results

### Unit Test

```
Variable names: ['MyVar']
OK
```
- ParentClass 被正确过滤
- BlueprintGuid 被正确过滤
- MyVar（用户变量）保留

### Real Asset Test (BP_FirstPersonCharacter.uasset)

- **Variable count: 11** (修复前 14)
- **Variables**: BlueprintSystemVersion, SimpleConstructionScript, UbergraphPages, FunctionGraphs, NewVariables, CategorySorting, ImplementedInterfaces, LastEditedDocuments, ThumbnailInfo, GeneratedClass, bLegacyNeedToPurgeSkelRefs
- 无 ParentClass、BlueprintGuid、BlueprintDescription 等元数据属性
- 满足 `< 14` 的验收标准

### Test Suite

- 394 passed, 71 skipped, 3 failed
- 3 个失败为 `test_dependency_analysis.py` 中的循环依赖检测测试（Phase 35 问题 #5），与本次修改无关

## Key Decisions

1. **黑名单策略**: 使用 `frozenset` 常量存储已知 UE 元数据属性名称，包含 17 个条目（含 None/NoneProperty 终止标记）
2. **保留独立性**: 不修改 `extract_blueprint_metadata` 或 `parse_component_transform`，过滤仅在变量提取层面进行

## Threat Flags

| Flag | File | Description |
|------|------|-------------|
| threat_flag: integrity | variable_extractor.py | 黑名单可能遗漏新的元数据属性名称（T-35-07），可通过后续发现补充 |
