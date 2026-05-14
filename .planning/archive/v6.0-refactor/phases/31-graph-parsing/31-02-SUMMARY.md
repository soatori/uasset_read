---
plan_id: 31-02
wave: 2
status: completed
completed_at: "2026-05-12T..."
---

# Plan 31-02 SUMMARY — from_archive Delegates

## 完成内容

### 1. models/core.py

替换 5 个 `NotImplementedError` stub 为实际委托调用：

- `FEdGraphPinType.from_archive(archive, name_map, summary)` → `read_ed_graph_pin_type`
- `UEdGraphPin.from_archive(archive, name_map, summary, export_map, import_map)` → `read_ue_graph_pin`
- `UEdGraphNode.from_archive(archive, name_map, summary, export_map, import_map, node_export)` → `read_ue_graph_node`
- `UEdGraph.from_archive(archive, name_map, summary, export_map, import_map, graph_export, graph_class, graph_export_idx)` → `read_ue_graph`
- `FMemberReference.from_archive(archive, name_map, import_map, export_map)` → `read_fmember_reference`

### 2. models/node_types.py

替换 5 个 `NotImplementedError` stub：

- `K2NodeCallFunction.from_archive(archive, name_map, import_map, export_map)` → `read_k2node_call_function`
- `K2NodeEvent.from_archive(archive, name_map, import_map, export_map)` → `read_k2node_event`
- `K2NodeKnot.from_archive(archive)` → `read_k2node_knot`
- `EdGraphNodeComment.from_archive(archive)` → `read_edgraph_node_comment`
- `K2NodeEnhancedInputAction.from_archive(archive, name_map)` → `read_k2node_enhanced_input`

### 3. TYPE_CHECKING Guard

扩展 TYPE_CHECKING 块包含所需类型：
- `PackageFileSummary`, `ObjectImport`, `ObjectExport`

## 验证结果

```
NotImplementedError count: core=0, node_types=0
Lazy imports count: core=5, node_types=5
```

所有 from_archive 方法使用延迟导入（方法体内 `from uasset_read.serializers.graph import ...`），无循环导入。

## 关键决策

- **D-12**: from_archive 签名匹配 serializer 函数参数，避免参数不匹配
- **延迟导入**: 所有 import 在方法体内，非模块顶部，防止循环依赖
- **TYPE_CHECKING**: 仅用于类型注解，不影响运行时

## 下一步

- Wave 3 (Plan 31-03): 创建 graph/ 模块（parser.py, flow_builder.py, __init__.py）
- 实现 extract_blueprint_graphs, build_execution_flows, build_connections_map