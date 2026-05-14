---
phase: 08-blueprint-graph-output
plan: 04
subsystem: cli
tags: [OUT2-04, cli-flags, graph-output, composability]
key-files:
  created: []
  modified:
    - path: uasset_read.py
      line_range: 4142-4145, 4503-4520
      description: create_parser() 添加 --graph 标志，main() 添加 --graph 分支逻辑
    - path: tests/test_output_formatting.py
      line_range: 992-1088
      description: CLI --graph 测试函数
metrics:
  tests_added: 7
  tests_passed: 7
  tests_total: 21
  regression_tests_passed: 105
---

## Plan 08-04: CLI --graph 标志

**Objective:** 扩展 CLI 支持 --graph 标志，允许用户仅输出蓝图图数据，满足 OUT2-04 需求。

**Status:** ✓ Complete

### Commits

| Task | Commit | Description |
|------|--------|-------------|
| Task 1: create_parser() 扩展 | ecc7d63 | 添加 --graph 标志（不加入互斥组） |
| Task 2: main() 扩展 | ecc7d63 | 添加 --graph 分支逻辑 |
| Task 3: 单元测试 | ecc7d63 | 创建 7 个 CLI --graph 测试 |

### Implementation Details

#### create_parser() 扩展

位置: uasset_read.py L4142-4145

在 Optional flags 部分添加 --graph 标志：
- 使用 action='store_true'（布尔标志）
- 不加入互斥组（D-08-12 独立可组合）
- help 文本说明可组合使用

#### main() 扩展

位置: uasset_read.py L4503-4520

添加 --graph 分支逻辑：
- --graph 分支在最前（优先级最高）
- --graph alone: 输出 {"graphs": format_graphs_json(result.graphs)}
- --graph --json/--verbose: 输出完整 JSON（format_json_full 已包含 graphs）
- --graph --text: 输出文本（format_text_full 已包含 Graphs 区块）

### Tests Added

7 个新增测试：
- test_cli_graph_flag: 验证 --graph 标志存在并可解析
- test_cli_graph_json_composable: 验证 --graph 不与 --json 互斥
- test_cli_graph_text_composable: 验证 --graph 不与 --text 互斥
- test_cli_graph_summary_composable: 验证 --graph 不与 --summary 互斥
- test_cli_graph_verbose_composable: 验证 --graph 与 --verbose 可组合
- test_cli_graph_output_alone: 验证 --graph alone 输出仅 graphs 字段
- test_cli_graph_json_output_full: 验证 --graph --json 输出完整 JSON

### Deviations

None - 实现完全遵循 PLAN.md 规范。

### Self-Check

- [x] create_parser() 包含 add_argument('--graph')
- [x] --graph 标志不在互斥组中
- [x] main() 包含 if args.graph: 分支
- [x] --graph alone 输出仅 graphs 字段
- [x] --graph --json/--verbose 输出完整 JSON
- [x] --graph --text 输出文本格式
- [x] CLI --graph 测试创建并通过
- [x] 无回归：105 tests pass

## Self-Check: PASSED