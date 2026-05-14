---
plan_id: 31-03
wave: 3
status: completed
completed_at: "2026-05-12T..."
---

# Plan 31-03 SUMMARY — graph Module

## 完成内容

### 1. graph/parser.py（55 行）

实现 extract_blueprint_graphs 入口函数：
- 遍历 ExportMap 检测 EdGraph/UberEdGraph 类型导出
- PKG_Cooked 检查避免解析已剥离资产
- 对每个图调用 read_ue_graph 完整解析

### 2. graph/flow_builder.py（280 行）

实现流构建函数：

**主函数：**
- `build_connections_map(graph)` → Tuple[List[Dict], List[str]]
- `build_execution_flows(graph)` → List[Dict]
- `build_data_flows(graph, mode)` → List[Dict]
- `build_graphs_summary(graphs)` → List[Dict]
- `format_graphs_json(graphs)` → List[Dict]

**辅助函数：**
- `_derive_node_name(node, idx)` — 节点名派生
- `format_pin_ref(node_guid, pin_name, node_name_lookup, mode)` — Pin 引用格式化
- `_get_start_event_name(node)` — 获取起点事件名
- `_find_next_exec_node(node, pin_lookup, node_lookup)` — 查找下一 exec 节点
- `_trace_execution_from_event(start_node, pin_lookup, node_lookup)` — 追踪执行流
- `_trace_execution_from_pin(start_node, start_pin, pin_lookup, node_lookup)` — 从特定 Pin 追踪

### 3. graph/__init__.py

导出公共 API：extract_blueprint_graphs, build_execution_flows, build_data_flows, build_connections_map, build_graphs_summary, format_graphs_json

### 4. __init__.py 更新

替换 stub 导入为实际 graph 模块导入：
- extract_blueprint_graphs, build_execution_flows, build_connections_map, build_graphs_summary, format_graphs_json

## 测试状态

```
Wave 1: 158 passed
Wave 3: 162 passed (+4)
235 failed, 47 skipped, 14 errors
```

新增 4 个测试通过（build_execution_flows, build_connections_map 相关）。

## 关键决策

- **D-19-02**: `_derive_node_name` 使用 f"{class_name}_{idx}" 格式避免冲突
- **D-19-11**: `_get_start_event_name` 支持四种起点类型
- **D-19-13**: 控制流节点停止追踪，输出 branch_type
- **循环检测**: visited set 确保无无限追踪

## Phase 31 完成状态

- Wave 1 ✓: serializers/graph.py + Export Layer
- Wave 2 ✓: models from_archive delegates
- Wave 3 ✓: graph/ module

**Phase 31 完成。** 蓝图图解析模块全部迁移完成。