# Phase 49: 函数调用引脚解析 — 参数化 CallFunction 输出

## 目标

让 `K2Node_CallFunction` 节点在 JSON 输出中提供 `parameters` 数组，包含函数签名
（参数名+类型+默认值+方向），使 C++ 函数声明可从 JSON 中推断。

## 背景

当前 CallFunction 节点已有引脚被 `read_ue_graph_pin()` 完整解析，存储在 `node.pins` 中。
但在 `format_node_dict()` 的 JSON 输出中，引脚只通过 `asdict(pin)` 扁平输出到 `pins[]`，
没有按输入/输出参数组织成结构化的 `parameters` 数组。

每个 CallFunction 节点的引脚结构：
- exec input（pin_category="exec", direction=EGPD_Input）— 执行输入
- exec output（pin_category="exec", direction=EGPD_Output）— 执行输出
- 数据输入引脚（参数）— pin_category 为 Float/Object/Int/Bool/Name 等
- 数据输出引脚（返回值/out params）— direction=EGPD_Output

## 方案

**不修改序列化层**（graph.py 已正确读取引脚），只在 **JSON formatter** 层
从 `node.pins` 提取参数结构。最小侵入。

### 任务分解

#### T1: 添加 `_extract_call_function_parameters()` 辅助函数
- 文件: `src/uasset_read/formatters/json_formatter.py`
- 从 CallFunction 节点的 `node.pins` 中提取参数
- 过滤 exec pins（pin_category != "exec"）
- 输入参数（direction=0）和输出参数（direction=1）分离
- 每个参数提取: name, pin_category, pin_subcategory, default_value
- 返回 `{"input_params": [...], "output_params": [...]}`

#### T2: 在 `format_node_dict()` 中为 CallFunction 节点添加 parameters
- 文件: `src/uasset_read/formatters/json_formatter.py` → `format_node_dict()`
- 当 `node.class_name == "K2Node_CallFunction"` 时
- 调用 T1 辅助函数，将结果写入 `result["parameters"]`

#### T3: 在 `flow_builder.py` 的 `_trace_execution_from_event()` 中扩展节点信息
- 文件: `src/uasset_read/graph/flow_builder.py`
- 当前 CallFunction 节点只输出 `function_name`
- 增加输出 `params` 数组（仅参数名+类型，保持执行流摘要轻量）

#### T4: 单元测试
- 文件: `tests/test_phase49_callfunction_params.py`
- 用合成 UEdGraphNode + UEdGraphPin 数据测试参数提取
- 测试: 普通函数（有输入+输出参数）、Pure 函数（无 exec pins）、
  无参数函数、参数含默认值、exec pins 被正确过滤

#### T5: 全量回归测试
- 确认 0 新回归
- 验证现有 test_ue5_pin_integration 仍为 2 pre-existing failures

## 验证标准

`BP_FirstPersonCharacter.uasset` 的 JSON 输出中，每个 `K2Node_CallFunction` 节点包含：

```json
{
  "node_type": "K2Node_CallFunction",
  "function_reference": { "member_name": "GetControlRotation", ... },
  "parameters": {
    "input_params": [
      { "name": "Target", "pin_category": "Object", "default_value": "" },
      { "name": "Speed", "pin_category": "Float", "default_value": "1.0" }
    ],
    "output_params": [
      { "name": "ReturnValue", "pin_category": "Struct", "pin_subcategory": "Rotator" }
    ]
  }
}
```

execution_flows 中的 CallFunction 节点也应包含简化的 `params` 列表。

## 文件变更预测

| 文件 | 变更类型 | 预估行数 |
|------|----------|----------|
| `src/uasset_read/formatters/json_formatter.py` | 新增辅助函数 + 修改 format_node_dict | ~40 |
| `src/uasset_read/graph/flow_builder.py` | 扩展 _trace_execution_from_event | ~10 |
| `tests/test_phase49_callfunction_params.py` | 新测试文件 | ~100 |
