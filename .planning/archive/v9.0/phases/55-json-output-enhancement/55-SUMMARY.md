---
phase: 55
plan: 01
subsystem: output
tags: [json, function_graphs, cli, output_version]
dependency_graph:
  requires: [53-function-execution-flow, 54-data-flow-tracking]
  provides: [OUT-01, OUT-02, OUT-03]
  affects: [json_formatter, cli, flow_builder]
tech_stack:
  added: [build_function_graphs, include_function_graphs flag]
  patterns: [top-level array, conditional output_version]
key_files:
  created: []
  modified:
    - src/uasset_read/graph/flow_builder.py
    - src/uasset_read/graph/__init__.py
    - src/uasset_read/formatters/json_formatter.py
    - src/uasset_read/cli.py
    - tests/test_output_formatting.py
decisions:
  - D-01: function_graphs 作为顶层数组（与 graphs_summary 同级）
  - D-02: 每个 FunctionEntry 对应一个 function_graph 条目
  - D-03: 数据流以内嵌标注方式集成（data_providers + data_sources）
  - D-04: output_version 条件化（4.0/5.0）
metrics:
  duration: 15 min
  tasks_completed: 4
  tests_added: 7
  tests_passed: 7
  completed_date: "2026-05-17"
---

# Phase 55 Plan 01: JSON 输出增强 Summary

**One-liner:** 在 format_json_full() 中新增顶层 function_graphs 数组，按 FunctionEntry 粒度组织函数图数据，包含执行流链路和数据流内嵌标注。

## Completed Tasks

| Task | Name | Commit | Files Modified |
|------|------|--------|----------------|
| 1 | build_function_graphs() 核心函数 | 38191c2 | flow_builder.py, __init__.py |
| 2 | JSON 输出注入 | 731c96f | json_formatter.py |
| 3 | CLI --function-graphs flag | 86831f8 | cli.py |
| 4 | 单元测试 | f1a1130 | test_output_formatting.py |

## Implementation Details

### Task 1: build_function_graphs() 核心函数

在 `flow_builder.py` 末尾添加 `build_function_graphs()` 函数：
- 遍历所有图，收集所有 K2Node_FunctionEntry 节点
- 通过 `function_reference.member_name` 匹配 `blueprint_functions` 获取签名元数据
- 为每个 FunctionEntry 构建 `execution_flows`（复用 `_trace_execution_from_event`)
- 对每个执行流节点计算 `data_providers` 和 `data_sources` 内嵌标注
- 过滤空 execution_flows 的条目

### Task 2: JSON 输出注入

修改 `format_json_full()` 函数：
- 增加 `include_function_graphs: bool = False` 参数
- `output_version` 条件化：`"5.0"` when True, `"4.0"` when False
- 当 `include_function_graphs=True` 且 `result.graphs` 非空时，注入顶层 `function_graphs` 数组

### Task 3: CLI --function-graphs flag

修改 `cli.py`：
- 添加 `--function-graphs` flag（非互斥组，可选 flag）
- 当 `--function-graphs` 单独指定时，隐含 `--json`
- 在调用 `format_json_full()` 时传递 `include_function_graphs=args.function_graphs`

### Task 4: 单元测试

添加 7 个 function_graphs 测试：
- `test_function_graphs_top_level` — 验证顶层位置
- `test_function_graphs_per_entry` — 验证 FunctionEntry 粒度
- `test_function_graphs_signature` — 验证签名提取
- `test_function_graphs_data_providers` — 验证数据流标注
- `test_output_version_4_without_flag` — 无 flag 时 version 4.0
- `test_output_version_5_with_flag` — 有 flag 时 version 5.0
- `test_function_graphs_empty_filtered` — 空流过滤

## Deviations from Plan

None — plan executed exactly as written.

## Verification Results

```bash
# Task 1 verification
python -c "from uasset_read.graph.flow_builder import build_function_graphs; print('OK')"
# OK

# Task 2 verification
python -c "from uasset_read.formatters.json_formatter import format_json_full; import inspect; sig = inspect.signature(format_json_full); assert 'include_function_graphs' in sig.parameters; print('OK')"
# OK

# Task 3 verification
python -m uasset_read --help | grep "function-graphs"
# --function-graphs  Include top-level function_graphs array in JSON output

# Task 4 verification
python -m pytest tests/test_output_formatting.py -k "function_graphs or output_version" --collect-only | grep -c "test_"
# 11 tests collected (including existing output_version tests)

# All Phase 55 tests passed
python -m pytest tests/test_output_formatting.py -k "function_graphs or output_version_4 or output_version_5" -v
# 7 passed
```

## Output Structure Example

```json
{
  "status": {...},
  "output_version": "5.0",
  "summary": {...},
  "exports": [...],
  "blueprint": {...},
  "graphs_summary": [...],
  "function_graphs": [
    {
      "function_name": "Move",
      "graph_source": "Move",
      "entry_node_guid": "0A89B7514654265DD7C4A0BC3D2433F9",
      "signature": {
        "return_type": "void",
        "parameters": [
          {"name": "Left / Right", "type": "float", "direction": "input"},
          {"name": "Forward / Backward", "type": "float", "direction": "input"}
        ]
      },
      "execution_flows": [
        {
          "start_event": "FunctionEntry.Move",
          "nodes": [
            {
              "node_guid": "...",
              "node_type": "K2Node_CallFunction",
              "function_name": "AddMovementInput",
              "parameters": {...},
              "data_providers": [...],
              "data_sources": [...]
            }
          ]
        }
      ]
    }
  ],
  "errors": []
}
```

## Threat Surface

No new threat surface introduced:
- CLI flag → format_json_full: 用户输入控制仅布尔值，无注入风险
- blueprint.functions → signature: 内部数据，已由 Phase 26 解析验证

## Self-Check: PASSED

- [x] build_function_graphs 可导入
- [x] format_json_full 接受 include_function_graphs 参数
- [x] CLI --function-graphs flag 存在
- [x] 7 个测试通过
- [x] 所有 4 个任务已提交

---

*Phase: 55-JSON 输出增强*
*Completed: 2026-05-17*