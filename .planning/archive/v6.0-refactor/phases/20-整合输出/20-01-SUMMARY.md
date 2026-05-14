---
phase: 20-整合输出
plan: 01
status: complete
completed: "2026-05-04T17:30:00.000Z"
requirements: [OUT-01, OUT-02]
files_modified:
  created: []
  modified: [uasset_read.py, tests/test_output_formatting.py]
key_changes:
  - "Add format_node_dict() function (OUT-01 node output structure)"
  - "Add GRAPH_TYPE_MAP constant (D-20-07 semantic mapping)"
  - "Modify format_graphs_json() to use format_node_dict and graph_type"
deviations: []
---

# Plan 20-01 Summary: 节点和Graph输出结构重组

## 完成内容

### Task 1: 创建 format_node_dict() 函数

在 `uasset_read.py` 第5144行位置创建新函数：

```python
def format_node_dict(node: UEdGraphNode, idx: int) -> Dict:
    """
    格式化单个节点为 OUT-01 规范 JSON 结构。
    """
```

功能实现：
- **D-20-01**: node_name 使用 `_derive_node_name()` 派生
- **D-20-02**: 字段名规范化（node_type, position:{x,y})
- **D-20-03**: function_reference/event_reference 提升到顶层

输出结构示例：
```json
{
  "node_name": "K2Node_CallFunction_0",
  "node_type": "K2Node_CallFunction",
  "node_guid": "...",
  "position": {"x": 100, "y": 200},
  "node_comment": "...",
  "pins": [...],
  "function_reference": {"member_name": "Jump", ...}
}
```

### Task 2: 修改 format_graphs_json()

修改内容：
- 添加 `GRAPH_TYPE_MAP` 常量（EdGraph→event, UberEdGraph→uber）
- 使用 `format_node_dict()` 替代 `asdict(node)`
- 输出 `graph_type` 替代 `graph_class`

测试更新：
- `test_format_graphs_json_structure` 更新为检查 `graph_type` 字段

## 验证结果

### 自动化验证
```bash
python -c "from uasset_read import format_node_dict, GRAPH_TYPE_MAP"
# OK: 函数可导入
# GRAPH_TYPE_MAP: {'EdGraph': 'event', 'UberEdGraph': 'uber'}

python -m pytest tests/test_output_formatting.py -v
# 95 passed, 11 skipped
```

### 手动验证
```python
from uasset_read import format_node_dict, K2NodeCallFunction, FMemberReference
# 输出包含：node_name, node_type, position, function_reference
# function_reference 顶层字段包含 member_name, member_parent, self_context
```

## 成功标准验证

| 标准 | 状态 |
|------|------|
| format_node_dict函数存在，可导入 | ✓ |
| 函数签名正确 | ✓ |
| 输出包含node_name字段 | ✓ |
| 输出包含node_type字段 | ✓ |
| 输出包含position结构 | ✓ |
| CallFunction节点输出包含function_reference | ✓ |
| Event节点输出包含event_reference | ✓ |
| format_graphs_json输出包含graph_type字段 | ✓ |
| 测试全部通过 | ✓ (95 passed) |

## 下一步

Wave 2: Plan 20-02 将依赖本计划的输出格式实现 blueprint 对象结构重组。