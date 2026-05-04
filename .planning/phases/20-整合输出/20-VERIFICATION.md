---
phase: 20-整合输出
status: passed
verified_at: "2026-05-04T18:00:00.000Z"
must_haves_verified: 9/9
---

# Phase 20 Verification: 整合输出

## Must-Haves 验证

### OUT-01: 节点输出结构规范化

| ID | Truth | Verification | Status |
|----|-------|--------------|--------|
| OUT-01-01 | 用户可以在JSON中看到每个节点的node_name（K2Node_CallFunction_1193格式） | format_node_dict() 输出 node_name 字段，使用 _derive_node_name() 派生 | ✓ Verified |
| OUT-01-02 | 用户可以在JSON中看到每个节点的node_type字段（而非class_name） | format_node_dict() 输出 node_type = class_name | ✓ Verified |
| OUT-01-03 | 用户可以在JSON中看到每个节点的position结构（而非node_pos_x/node_pos_y） | format_node_dict() 输出 position: {x, y} | ✓ Verified |
| OUT-01-04 | CallFunction节点用户可以在JSON顶层看到function_reference字段 | format_node_dict() 对 K2NodeCallFunction 提取 function_reference 到顶层 | ✓ Verified |
| OUT-01-05 | Event节点用户可以在JSON顶层看到event_reference字段 | format_node_dict() 对 K2NodeEvent 提取 event_reference 到顶层 | ✓ Verified |

### OUT-02: Graph类型语义化映射

| ID | Truth | Verification | Status |
|----|-------|--------------|--------|
| OUT-02-01 | 用户可以在JSON中看到每个Graph的graph_type字段（event/uber而非EdGraph/UberEdGraph） | GRAPH_TYPE_MAP: EdGraph→event, UberEdGraph→uber | ✓ Verified |

### OUT-03: Blueprint对象结构重组

| ID | Truth | Verification | Status |
|----|-------|--------------|--------|
| OUT-03-01 | 用户可以在JSON顶层看到单一blueprint对象 | format_json_full() 输出 blueprint 字段（替代 blueprint_metadata） | ✓ Verified |
| OUT-03-02 | 用户可以在blueprint对象内看到graphs数组 | blueprint.graphs 包含 format_graphs_json() 输出 | ✓ Verified |
| OUT-03-03 | 用户可以在blueprint对象内看到blueprint_name字段 | format_blueprint_dict() 输出 blueprint_name 参数 | ✓ Verified |

## Automated Checks

```bash
# 验证 format_node_dict 存在
python -c "from uasset_read import format_node_dict; print('OK')"
# OK

# 验证 GRAPH_TYPE_MAP
python -c "from uasset_read import GRAPH_TYPE_MAP; print(GRAPH_TYPE_MAP)"
# {'EdGraph': 'event', 'UberEdGraph': 'uber'}

# 验证 output_version
python -c "from uasset_read import format_json_full, ParseResult; r = ParseResult(is_success=True, summary=None, export_map=[]); j = format_json_full(r); print(j['output_version'])"
# 4.0

# 运行测试
python -m pytest tests/ -q
# 391 passed, 49 skipped
```

## Key Artifacts

| Artifact | File | Purpose |
|----------|------|---------|
| format_node_dict() | uasset_read.py:5144 | OUT-01 节点格式化 |
| GRAPH_TYPE_MAP | uasset_read.py:5149 | OUT-02 类型映射 |
| format_graphs_json() | uasset_read.py:5219 | OUT-02 使用新格式 |
| format_json_full() | uasset_read.py:5715 | OUT-03 blueprint 结构 |
| format_blueprint_dict() | uasset_read.py:6186 | OUT-03 blueprint_name |

## Summary

Phase 20 完成 OUT-01~03 规范实现：

- **OUT-01**: format_node_dict() 规范节点输出（node_name, node_type, position, function_reference/event_reference）
- **OUT-02**: graph_type 语义化映射（EdGraph→event, UberEdGraph→uber）
- **OUT-03**: blueprint 对象结构（graphs 移入 blueprint，output_version 4.0）

所有 9 个 must-haves 已验证通过。

---

*Verified: 2026-05-04 — 391 tests passed*