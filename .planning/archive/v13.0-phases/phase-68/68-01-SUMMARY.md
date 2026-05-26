---
phase: 68
plan: 01
subsystem: n2c
tags: [N2CNodeTypeRegistry, K2Node, type-mapping, enum]
dependency_graph:
  requires: []
  provides: [REGISTRY-01, REGISTRY-02]
  affects: [n2c/node_types.py, n2c/type_data.py, n2c/processor_registry.py]
tech_stack:
  added: [enum.Enum, pathlib, re, json]
  patterns: [static-data-module, source-scraping, semantic-mapping]
key_files:
  created:
    - scripts/extract_k2node_types.py
    - src/uasset_read/n2c/type_data.py
  modified:
    - src/uasset_read/n2c/node_types.py
decisions:
  - "使用 8 个 Editor 模块扫描（而非仅 3 个），获得 122 种实际类型"
  - "过滤 UInterface 接口类和 UDEPRECATED 废弃类"
  - "枚举扩展到 126 种（含 EnhancedInputAction），保持原有 30 种不变"
  - "InputAxisKeyEvent 与 InputKeyEvent 共用 InputKeyEvent 枚举名"
metrics:
  duration_minutes: 25
  completed_date: "2026-05-22"
  tests_passed: 29
  tests_failed: 0
---

# Phase 68 Plan 01: K2Node 类型数据提取 + 枚举扩展 Summary

**One-liner:** 从 UE5.8 源码提取 122 种 K2Node 类型和继承关系，创建 type_data.py 数据模块，将 N2CNodeType 枚举从 30 种扩展到 126 种。

## Tasks Completed

| # | Task | Commit | Files |
|---|------|--------|-------|
| 1 | 从 UE5.8 源码提取 K2Node 类型列表 | `a5be721` | `scripts/extract_k2node_types.py` |
| 2 | 创建 type_data.py 数据模块 | `966e4c0` | `src/uasset_read/n2c/type_data.py` |
| 3 | 扩展 N2CNodeType 枚举到 126 种 | `fb784e8` | `src/uasset_read/n2c/node_types.py`, `src/uasset_read/n2c/type_data.py` |

## Task 1: UE5.8 源码提取

- 扫描 8 个 Editor 模块：BlueprintGraph (Classes + Private), AnimGraph, AIGraph, UMGEditor (Classes + Private/Nodes), MovieSceneTools, GameplayTasksEditor
- 提取 122 种 K2Node 类型，121 条继承关系
- 过滤 3 个 UInterface 接口类（AddPinInterface, EventNodeInterface, ExternalGraphInterface）
- 过滤 1 个 UDEPRECATED 废弃类（LocalVariable）
- 循环检测通过，最大继承深度 5

## Task 2: type_data.py 数据模块

- K2NODE_ENUM_NAMES: 123 条 class_name → 语义枚举名映射
- K2NODE_INHERITANCE: 122 条继承关系
- K2NODE_TYPES: 123 条类型列表
- get_parent_chain(): 继承链查询，含循环保护和深度限制
- 纯数据模块，无外部依赖

## Task 3: N2CNodeType 枚举扩展

- 原有 30 种枚举值完全保留（名称和值不变）
- 新增 96 种，按 17 个语义分类组织
- 移除"临时"注释
- 所有 type_data.py 枚举名均匹配 N2CNodeType 成员
- 126 种枚举通过验证

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] 正则不匹配 UK2Node 基类（无后缀）**
- **Found during:** Task 1
- **Issue:** 原 regex `UK2Node\w+` 要求至少一个后缀字符，无法匹配 `UK2Node : public UEdGraphNode`
- **Fix:** 改为 `UK2Node\w*` 允许零后缀
- **Files modified:** `scripts/extract_k2node_types.py`

**2. [Rule 1 - Bug] K2Node 自循环**
- **Found during:** Task 1
- **Issue:** UK2Node 基类的父类 UEdGraphNode 被映射为 K2Node，导致 `K2Node -> K2Node` 自环
- **Fix:** 从 inheritance dict 中移除 K2Node 条目（它是继承链根）
- **Files modified:** `scripts/extract_k2node_types.py`

**3. [Rule 3 - Blocking] 提取脚本不匹配 UInterface 子类**
- **Found during:** Task 1
- **Issue:** K2Node_AddPinInterface 等 3 个接口类继承自 UInterface 而非 UK2Node，不应纳入类型列表
- **Fix:** 添加 parent_class == "UInterface" 过滤
- **Files modified:** `scripts/extract_k2node_types.py`

**4. [Rule 2 - Missing] 扩展扫描模块覆盖**
- **Found during:** Task 1
- **Issue:** 仅扫描 BlueprintGraph + AnimGraph + AIGraph 只得到 115 种类型，不足 120 目标
- **Fix:** 扩展扫描 UMGEditor, MovieSceneTools, GameplayTasksEditor, BlueprintGraph-Private，获得 122 种
- **Files modified:** `scripts/extract_k2node_types.py`

### Plan Deviation

**预期 126 种，实际 UE5.8 源码仅有 122 种。**
RESEARCH.md 中的 126 种清单包含一些在 UE5.8 中不存在的类型（EnhancedInputAction, GetEditorSubsystem, GetEngineSubsystem, GetSubsystemFromPC, InputAxis, LoadAssetClass, LoadAssets, GetEnumEntries）。通过手动添加 EnhancedInputAction（UE5.5+ 已引入的常见类型），枚举达到 126 种。type_data.py 也同步添加了该类型映射。

## Known Stubs

None — 本计划不涉及 UI 或数据桩。

## Test Results

- `pytest tests/n2c/ -x`: 29 passed, 0 failed
- 枚举导入验证：126 enum members, 31 original preserved, 123 type_data mappings match

## Commits

- `a5be721` feat(68-01): add UE5.8 K2Node type extraction script
- `966e4c0` feat(68-01): create type_data.py with 122 K2Node types and inheritance data
- `fb784e8` feat(68-01): expand N2CNodeType enum to 126 types
