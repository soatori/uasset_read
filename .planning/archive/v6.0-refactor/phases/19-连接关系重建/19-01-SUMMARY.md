---
phase: 19-连接关系重建
plan: 01
subsystem: output_formatting
tags: [LINK-01, connections, name-mode, TDD]
dependency_graph:
  requires: []
  provides: [format_pin_ref, _derive_node_name, FORMAT_CONFIG, build_connections_map-name-mode]
  affects: [format_graphs_json]
tech_stack:
  added:
    - FORMAT_CONFIG全局配置
    - _derive_node_name节点名派生函数
    - format_pin_ref格式转换函数
  patterns:
    - TDD开发流程
    - name/guid双模式输出
key_files:
  created: []
  modified:
    - uasset_read.py (第4987-5075行: FORMAT_CONFIG + _derive_node_name + format_pin_ref)
    - uasset_read.py (第5077-5111行: build_connections_map重构)
    - tests/test_output_formatting.py (Phase 19 LINK-01测试)
decisions:
  - D-19-02: name模式使用class_name_idx格式避免同名节点冲突
  - D-19-04: 默认pin_reference_mode="name"，用户友好输出
  - D-19-05: 查找失败时保留guid fallback并添加warning字段
metrics:
  duration: "5m 27s"
  completed_date: "2026-05-04T08:11:27Z"
  task_count: 3
  file_count: 2
---

# Phase 19 Plan 01: 连接输出 name 模式实现 Summary

实现 LINK-01 需求：构建 connections 数组，支持 name 模式输出（默认）和 guid 模式输出（可选）。

## 一句话概述

实现 name 模式连接输出，使用 class_name_idx 格式的节点名替代 GUID，提升用户友好性。

## 完成的任务

### Task 1: 定义 FORMAT_CONFIG 全局配置和节点名派生逻辑

**实现内容：**
- `FORMAT_CONFIG` 全局配置字典，默认 `pin_reference_mode: "name"`
- `_derive_node_name()` 函数：从节点派生用户友好的节点名

**代码位置：**
- `uasset_read.py` 第 4989-5008 行

### Task 2: 创建 format_pin_ref() 格式转换函数

**实现内容：**
- `format_pin_ref()` 函数支持 name 和 guid 模式切换
- name 模式输出：`{"node": "K2Node_CallFunction_10", "pin": "execute"}`
- guid 模式输出：`{"node_guid": "...", "pin_name": "execute"}`
- 查找失败 fallback：保留原始 guid 并添加 warning

**代码位置：**
- `uasset_read.py` 第 5010-5048 行

### Task 3: 修改 build_connections_map() 支持 name 模式

**实现内容：**
- 构建 `node_name_lookup` 查找表（node_guid → node_name）
- 使用 `format_pin_ref()` 转换连接格式
- 正确处理 Phase 18 的 `linked_to_raw` dict 格式（提取 `pin_guid` 字段）

**代码位置：**
- `uasset_read.py` 第 5050-5111 行

## 测试覆盖

新增测试类：
- `TestFormatConfig` (2 tests): FORMAT_CONFIG 默认值和字段验证
- `TestDeriveNodeName` (3 tests): 节点名派生和同名冲突处理
- `TestFormatPinRef` (5 tests): name/guid 模式转换和查找失败处理
- `TestBuildConnectionsMapNameMode` (5 tests): name/guid 模式输出验证

测试结果：**374 passed, 49 skipped**

## 输出格式对比

### name 模式（默认）

```json
{
  "connections": [
    {
      "from": {"node": "K2Node_EnhancedInputAction_0", "pin": "Started"},
      "to": {"node": "K2Node_CallFunction_1", "pin": "execute"}
    }
  ]
}
```

### guid 模式（可选）

```json
{
  "connections": [
    {
      "from": {"node_guid": "guid-1", "pin_name": "Started"},
      "to": {"node_guid": "guid-2", "pin_name": "execute"}
    }
  ]
}
```

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] 修复 test_build_connections_map_basic 测试断言**
- **Found during:** Task 3 完成后运行整体测试
- **Issue:** 旧测试期望 guid 格式（`node_guid`），但默认模式现在是 name 格式（`node`）
- **Fix:** 更新测试断言以验证新的 name 格式默认输出
- **Files modified:** tests/test_output_formatting.py
- **Commit:** f514819

None other - plan executed exactly as written.

## Key Decisions

| Decision | Rationale |
|----------|-----------|
| D-19-02: 使用 class_name_idx 格式 | 避免同名节点冲突，用户可读性强 |
| D-19-04: 默认 name 模式 | 用户友好输出优先，隐藏内部 GUID |
| D-19-05: fallback 保留 guid + warning | 查找失败时不丢失数据，提供诊断信息 |

## Threat Flags

无新增安全相关 surface。Phase 19 为纯数据结构转换逻辑，无外部输入或安全敏感操作。

## Known Stubs

无。所有功能已完整实现并测试。

## Self-Check: PASSED

**1. 文件存在验证：**
- `uasset_read.py`: FOUND
- `tests/test_output_formatting.py`: FOUND

**2. Commit 存在验证：**
- `f514819`: FOUND

**3. 功能验证：**
- `grep -c "FORMAT_CONFIG" uasset_read.py`: 3 (>= 1)
- `grep -c "def format_pin_ref" uasset_read.py`: 1
- `grep -c "def _derive_node_name" uasset_read.py`: 1
- `grep -c "node_name_lookup" uasset_read.py`: 10 (>= 1)

---

*Created: 2026-05-04T08:11:27Z*
*Duration: 5m 27s*
*Commits: f514819*