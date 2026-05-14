---
phase: 08-blueprint-graph-output
plan: 01
subsystem: graph_output
tags: [GRAPH-11, OUT2-01, connections-map, json-output]
key-files:
  created: []
  modified:
    - path: uasset_read.py
      line_range: 3174-3271
      description: build_connections_map() 和 format_graphs_json() 函数
    - path: tests/test_output_formatting.py
      line_range: 175-276, 539-630
      description: Phase 8 fixtures 和测试函数
metrics:
  tests_added: 5
  tests_passed: 5
  tests_total: 105
  regression_tests_passed: 105
---

## Plan 08-01: 连接映射构建

**Objective:** 实现连接映射构建和 JSON 输出扩展，将 linked_to_raw 原始数据转换为可读的 {node_guid, pin_name} 连接表示。

**Status:** ✓ Complete

### Commits

| Task | Commit | Description |
|------|--------|-------------|
| Task 1: build_connections_map() | 80104bd | 实现引脚连接映射函数 |
| Task 2: format_graphs_json() | 80104bd | 实现图数据 JSON 格式化函数 |
| Task 3: format_json_full() 扩展 | 80104bd | 添加 graphs 字段到 JSON 输出 |
| Task 3: 单元测试 | 80104bd | 创建测试 fixtures 和测试函数 |

### Implementation Details

#### build_connections_map() 函数

位置: uasset_read.py L3178-3227

实现 D-08-01~06 决策：
- 构建 PinId → (node_guid, pin_name) 查找表
- 仅从 Output pins (direction=1) 出发构建连接（D-08-05 单向表示）
- 连接结构使用 {from: {...}, to: {...}} 格式（D-08-06）
- 查找失败时包含 warning 字段和 raw_pin_id（D-08-04）

返回值: Tuple[List[Dict], List[str]] - (connections, warnings)

#### format_graphs_json() 函数

位置: uasset_read.py L3230-3258

实现：
- 为每个 graph 构建连接映射
- 使用 asdict() 转换 nodes
- 添加 optional 字段 (graph_guid, schema)
- 添加 warnings（如果存在）

#### format_json_full() 扩展

位置: uasset_read.py L3260-3266

添加 `"graphs": format_graphs_json(result.graphs)` 到返回字典

### Tests Added

5 个新增测试：
- test_format_json_full_contains_graphs: 验证 JSON 输出包含 graphs 字段
- test_graphs_field_top_level: 验证 graphs 与 blueprint_metadata 同级
- test_format_graphs_json_structure: 验证 graph 结构正确性
- test_build_connections_map_basic: 验证连接映射构建
- test_build_connections_map_warning: 验证查找失败处理

### Deviations

None - 实现完全遵循 PLAN.md 规范。

### Self-Check

- [x] build_connections_map() 函数实现完成，导入验证通过
- [x] format_graphs_json() 函数实现完成，导入验证通过
- [x] format_json_full() 扩展包含 graphs 字段
- [x] Phase 8 Wave 1 单元测试创建并通过
- [x] 无回归：105 tests pass

## Self-Check: PASSED