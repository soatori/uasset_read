---
plan_id: 31-01
wave: 1
status: completed
completed_at: "2026-05-12T..."
---

# Plan 31-01 SUMMARY — serializers/graph.py + Export Layer

## 完成内容

### 1. serializers/graph.py（756 行）

迁移 uasset_read.py L3191-4679 的 11+2 个图二进制读取函数：

- `read_ed_graph_pin_type()` — FEdGraphPinType 双模式解析
- `read_ue_graph_pin()` — 18 字段序列化（EdGraphPin.cpp L1838-1964）
- `read_fmember_reference()` — 函数引用结构
- `read_ue_graph_node()` — 节点基类 + script_serial PropertyTag
- `read_ue_graph()` — 图容器解析
- `read_k2node_call_function()` ~ `read_k2node_enhanced_input()` — 5 个节点类型读取器
- `create_node_from_archive()` — 类型分发工厂（D-07/D-08）
- `read_pin_reference()`, `read_pin_array()` — 辅助函数

### 2. Export Layer（__init__.py 扩展）

添加 100+ 导出项：

- 常量：MAX_PINS_PER_NODE, CONTROL_FLOW_NODES, PROP_TAG_*, UE5_* 版本常量
- 序列化函数：read_ue_graph, read_ue_graph_node, read_ue_graph_pin, create_node_from_archive
- 兼容 shim：parse_uasset, format_json_full 等（stub，等待 Wave 2-3）

### 3. serializers/__init__.py

导出 graph 模块：`read_ue_graph`, `read_ue_graph_node`, `read_ue_graph_pin`, `read_ed_graph_pin_type`, `read_fmember_reference`, `create_node_from_archive`

## 测试状态

```
451 items collected
158 passed, 47 skipped
239 failed (stub 函数), 14 errors
```

Wave 1 仅提供 stub 导出，失败为预期行为。Wave 2-3 实现后测试将通过。

## 关键决策

- **D-07**: 节点工厂使用 `node_class_name` 字段分发，避免硬编码类型枚举
- **D-08**: 每个节点类型有专用读取器，继承 UEdGraphNode 基类字段
- **Stub 策略**: 动态加载旧版失败（dataclass 上下文），改用 None stub 确保导入可用

## 遗留问题

- parse_uasset, format_json_full 等 40+ stub 函数等待 Phase 32-33 实现
- VectorValue, RotatorValue 等 dataclass 等待 Phase 30 扩展

## 下一步

- Wave 2 (Plan 31-02): 实现 models/core.py, node_types.py 的 from_archive 委托
- Wave 3 (Plan 31-03): 创建 graph/ 模块（parser.py, flow_builder.py）