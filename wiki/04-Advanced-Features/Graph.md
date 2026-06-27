---
title: 图分析
section: graph
---

# 图分析

> **模块路径**: `graph/`
> **职责**: 提取和分析蓝图执行流、数据流和连接关系。

## 模块结构

| 文件 | 职责 |
|------|------|
| `__init__.py` | 模块入口，导出所有公共 API |
| `parser.py` | 图提取入口 — 从 ExportMap 发现 EdGraph/UberEdGraph |
| `flow_builder.py` | 执行流、数据流、连接映射构建（核心逻辑） |
| `chain_builder.py` | 执行流链式表达（N1→N2→N3 格式） |
| `macro_expander.py` | 宏实例展开处理 |

## 核心 API

### extract_blueprint_graphs

<!-- data-api="extract_blueprint_graphs" -->
```python
extract_blueprint_graphs(
    archive: FArchive,
    summary: PackageFileSummary,
    name_map: List[str],
    import_map: List[ObjectImport],
    export_map: List[ObjectExport],
    linker: Optional[PackageLinker] = None,
) -> List[UEdGraph]
```

从 ExportMap 提取所有蓝图图（EdGraph/UberEdGraph）。遍历导出表，对每个图调用 `read_ue_graph` 完整解析 Graph→Node→Pin 三层结构。

**安全检查**: `PKG_Cooked` 检查 — 烘焙资产的图数据已被剥离，提前返回空列表。

### build_execution_flow_entries

<!-- data-api="build_execution_flow_entries" -->
```python
build_execution_flow_entries(graph: UEdGraph) -> List[Dict]
```

从 `START_EVENT_TYPES` 节点（K2Node_Event、K2Node_EnhancedInputAction、K2Node_VariableSet、K2Node_CustomEvent、K2Node_FunctionEntry）开始，沿 exec pin 连接追踪执行流。

返回每个 entry 包含：
- `start_event`: 起始事件名称
- `nodes`: 执行流节点列表（含参数提取、纯函数标注、控制流终止标记）

### build_data_flows

<!-- data-api="build_data_flows" -->
```python
build_data_flows(graph: UEdGraph, mode: str = "name") -> List[Dict]
```

从非 exec pins 提取数据传递关系，构建 `data_flows` 数组。每个 entry 包含 `source` 和 `target` 的节点+pin 引用。

支持合成数据流补充（FirstPerson 模板中错位缺失的函数图参数边）。

### build_connections_map

<!-- data-api="build_connections_map" -->
```python
build_connections_map(graph: UEdGraph) -> Tuple[List[Dict], List[str]]
```

将 `linked_to_raw`（PinId GUID hex）转换为用户友好的节点引用格式。返回连接列表和警告信息。

使用归一化边迭代器 `_iter_normalized_edges` 统一处理 output→input 方向，覆盖 UE 文本导出中 Input/Output 两端都可能出现 LinkedTo 的情况。

### build_execution_chains

<!-- data-api="build_execution_chains" -->
```python
build_execution_chains(
    graph: UEdGraph,
    execution_flows: Optional[List[Dict]] = None,
) -> List[Dict]
```

将逐对执行流转换为链式字符串格式（Phase 71）：
- 线性流: `["N1->N2->N3"]`
- 分支流: `["N1->N2", "N1->N3"]`
- 环检测: `has_cycle=True` 时 chains 可能不完整

## 执行流追踪流程

```
1. 找到 START_EVENT_TYPES 节点（K2Node_Event 等）
2. 对每个 start_node -> _trace_execution_from_event()
   |--- 迭代：输出执行引脚 -> 链接输入引脚 -> 下一个节点
   |--- CallFunction：提取参数 + 追踪数据源
   |--- CONTROL_FLOW_NODES：标记分支类型（Branch/Sequence/Switch）
   |--- 纯节点：标记 data_providers（正向追踪输出目标）
   └── 循环检测：visited GUID 集合
3. 返回执行流条目列表
```

### 增强输入动作追踪

`K2Node_EnhancedInputAction` 多触发时机（Started/Triggered/Completed）从每个 exec output pin 独立追踪，使用 `_trace_execution_from_pin` 分别处理。

### Knot 穿透

数据流追踪中遇到 `K2Node_Knot` 节点时，使用 `_resolve_knot_chain` 递归穿透直到到达非 Knot 终端节点（最大深度 20）。

### 数据源反向追踪

`_trace_data_source` 从 CallFunction input pin 开始，穿透 Knot 链，找到数据源：
- `function_parameter` — FunctionEntry 参数 pin
- `pure_function` — 纯函数输出
- `self_reference` — self/Target 引用
- `default_value` — pin 默认值
- `boundary` — 数据流边界节点

## 关键设计

- **PKG_Cooked 检查**: 烘焙资产图数据已剥离，提前返回空
- **链格式**: 配对格式 -> 链字符串 "N1->N2->N3"，跳过 Knot 和无 GUID 节点
- **循环检测**: DFS 三色标记法（WHITE/GRAY/BLACK）
- **归一化边迭代**: 统一 output->input 方向，覆盖 input pin 上记录连接的资产
- **合成边补充**: 为错位导致缺失的参数 pin 补充语义数据边（Move/Aim 函数）
- **字符串清理**: `_sanitize_string` 移除 null 和控制字符，确保 JSON 安全
- **循环引用防护**: `_sanitize_recursive` 使用 visited 集合防止无限递归

## 图格式化

### format_graphs_json

<!-- data-api="format_graphs_json" -->
```python
format_graphs_json(graphs: List[UEdGraph]) -> List[Dict]
```

完整格式化蓝图图数据为 JSON 输出。包含节点 DTO（含 Pins 连接引用）、connections、execution_chains、data_flows。

### build_function_graphs

<!-- data-api="build_function_graphs" -->
```python
build_function_graphs(
    graphs: List[UEdGraph],
    blueprint_functions: Optional[List] = None,
) -> List[Dict]
```

构建顶层 `function_graphs` 数组。每个 FunctionEntry 节点对应一个条目，包含签名（从 blueprint_functions 或 Pin fallback 提取）、执行流和数据流内嵌标注。

## 辅助函数

| 函数 | 说明 |
|------|------|
| `is_boundary_node` | 判断是否为数据流边界节点（DATA_BOUNDARY_NODES + self/Target） |
| `_derive_node_name` | 从节点派生用户友好的节点名（`class_name_idx` 格式） |
| `format_pin_ref` | 格式化 Pin 引用（name 或 guid 模式） |
| `_get_start_event_name` | 获取起点节点的事件名称（支持 5 种起点类型） |
| `_find_next_exec_node` | 查找 exec output pin 连接的下一个节点 |
| `_iter_normalized_edges` | 归一化边迭代器（统一 output→input 方向） |
| `_resolve_knot_chain` | 递归穿透 Knot 链找终端节点 |
| `_trace_data_source` | 反向追踪参数数据来源 |

## 相关章节

- [[Blueprint]] - 蓝图解析
- [[Kismet]] - Kismet 反编译
- [[Linker]] - 对象链接器
