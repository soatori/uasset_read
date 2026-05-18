---
plan_id: "01"
phase: 49
status: complete
---

# Phase 49 Plan 01: 函数调用引脚解析 — SUMMARY

## 目标

让 `K2Node_CallFunction` 节点在 JSON 输出中提供 `parameters` 数组，包含函数签名（参数名+类型+默认值+方向）。

## 实现

最小侵入方案 — 不修改序列化层，只在 formatter 和 flow_builder 层从 `node.pins` 提取参数结构。

### 变更文件

| 文件 | 变更 |
|------|------|
| `src/uasset_read/formatters/json_formatter.py` | 新增 `_extract_call_function_parameters()` 辅助函数 |
| `src/uasset_read/graph/flow_builder.py` | `format_node_dict()` 添加 parameters 字段；`_trace_execution_from_event()` 添加简化 params 数组 |
| `src/uasset_read/models/core.py` | 同步 FEdGraphPinType 字段与主分支 |
| `tests/test_phase49_callfunction_params.py` | 7 个单元测试 |

### 验证

- 7/7 Phase 49 tests passed
- 0 new regressions (3 test_ue5_pin_integration failures are pre-existing on main branch)

### 输出示例

```json
{
  "node_type": "K2Node_CallFunction",
  "parameters": {
    "input_params": [
      {"name": "Target", "pin_category": "Object", "pin_subcategory": "Character"}
    ],
    "output_params": [
      {"name": "ReturnValue", "pin_category": "Struct", "pin_subcategory": "Rotator"}
    ]
  }
}
```

## Self-Check: PASSED
