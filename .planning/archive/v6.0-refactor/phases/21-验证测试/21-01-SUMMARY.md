---
phase: 21-验证测试
plan: 01
status: partial
subsystem: verification
tags: [integration-test, graph-parsing, bug-fix]
requires: [Phase 18, Phase 19, Phase 20]
provides: [test_phase21_verification.py, graph detection fix]
tech-stack:
  added: [outer_index node collection, get_asset_class bug fix]
  patterns: [fallback node creation]
key-files:
  created:
    - path: tests/test_phase21_verification.py
      changes: Phase 21 验证测试文件（11 测试用例）
  modified:
    - path: uasset_read.py
      changes: 修复 get_asset_class bug + outer_index 节点收集逻辑
decisions:
  - D-21-01: 修复 get_asset_class 返回 object_name 而非 class_name
  - D-21-02: 当 nodes_count=0 时通过 outer_index 收集节点
  - D-21-03: Fallback 节点创建（node_guid="", pins=[]）
  - D-21-04: 扩展节点类型检测（K2Node + EdGraphNode）
metrics:
  tests_passed: 4
  tests_failed: 6
  tests_skipped: 1
  core_tests_passed: 394
  duration: "30 minutes"
issues_found:
  - id: ISSUE-01
    description: 节点序列化解析未正确工作（read_ue_graph_node 跳过 UObject 基类数据）
    severity: critical
    impact: execution_flows/data_flows/function_reference 无法正确构建
    recommendation: 需要修复 Phase 18 的节点序列化逻辑，正确跳过 UObject 基类数据
---

# Phase 21 Plan 01: 验证测试 Summary

创建 Phase 21 验证测试文件并发现图解析的关键 bug。

## Completed Tasks

| Task | Name | Status | Notes |
|------|------|--------|-------|
| 1 | 创建测试文件结构 | ✓ 完成 | tests/test_phase21_verification.py |
| 2 | TEST-01 节点数量验证 | ✓ 通过 | 修复后 30 K2Node 匹配 |
| 3 | TEST-02 执行流程验证 | ✗ 失败 | execution_flows 为空 |
| 4 | TEST-03 数据流验证 | ✗ 失败 | data_flows 缺少连接信息 |
| 5 | TEST-04 节点属性验证 | ✗ 部分 | node_guid 存在但为空，function_reference 缺失 |

## Key Fixes

### Fix 1: get_asset_class Bug

**问题**: `get_asset_class` 函数返回 `import_map[].class_name`（对于 Class 导入固定为 "Class"），而非 `object_name`（实际类名如 "EdGraph"）。

**修复**: 改为返回 `import_map[].object_name`。

**影响**: 图检测逻辑无法识别 EdGraph 类型，导致 graphs = None。

### Fix 2: outer_index 节点收集

**问题**: UE 5.x 中 EdGraph 的 nodes_count = 0，节点通过 outer_index 关联到图。

**修复**: 当 nodes_count = 0 时，遍历 export_map 收集 outer_index 指向该图的节点。

**影响**: 图现在正确包含节点（EventGraph: 18 nodes）。

## Test Results

| Test Class | Passed | Failed | Skipped |
|------------|--------|--------|---------|
| TestNodeCount | 2 | 0 | 0 |
| TestExecutionFlow | 0 | 3 | 0 |
| TestDataFlow | 1 | 2 | 0 |
| TestNodeProperties | 1 | 1 | 1 |

**Core Tests**: 394 passed, 8 failed (6 Phase 21 + 2 skill_integration)

## Issues Found

### ISSUE-01: 节点序列化解析问题

**描述**: `read_ue_graph_node` 函数假设节点序列化数据直接从 pins 数组开始，但实际上 UObject 基类序列化数据在前。

**根因分析**:
- UObject::Serialize() 先执行，序列化基类属性
- UEdGraphPin::SerializeAsOwningNode(Ar, Pins) 在 Super::Serialize() 之后执行
- 当前代码直接定位到 `node_export.serial_offset`，读取的是 UObject 基类数据而非 pins 数组

**影响**:
- pins_count 读取为错误值（如 41984）
- 节点解析触发 ParseError 或返回空数据
- Fallback 节点 node_guid="" 和 pins=[]
- execution_flows 无法追踪（无 pin 连接信息）
- function_reference 缺失（节点数据未解析）

**建议修复**:
1. 研究 UObject 序列化格式（属性数量、引用数组等）
2. 找到 UObject 基类数据的结束位置
3. 从正确位置开始读取 pins 数组
4. 或使用属性迭代器跳过 UObject 数据

## Recommendations

1. **创建 Phase 22**: 修复节点序列化解析（read_ue_graph_node）
2. **更新 Phase 18 RESEARCH.md**: 补充 UObject 基类序列化结构研究
3. **考虑使用 UE 源码**: UObject::Serialize() 实现来确定跳过字节数

## Files Modified

```
tests/test_phase21_verification.py  (新建，273 行)
uasset_read.py:
  - get_asset_class(): 返回 object_name
  - read_ue_graph(): 添加 graph_export_idx 参数，outer_index 节点收集
  - format_node_dict(): 处理 dict 类型 node_data
```

---
*Completed: 2026-05-04*