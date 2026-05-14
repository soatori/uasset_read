# Phase 8: 蓝图图输出增强 - Research

**Researched:** 2026-05-02
**Domain:** 蓝图图数据输出格式化、连接映射构建、执行流追踪
**Confidence:** HIGH

## Summary

Phase 8 交付蓝图图数据的输出格式化，不包含新的图解析逻辑（Phase 7 已完成）。核心任务是构建连接映射（linked_to_raw → {node_guid, pin_name} 表示）和实现执行流追踪（Event → CallFunction 链路）。

**Primary recommendation:** 使用纯 Python 算法实现连接映射和执行流追踪，无外部依赖；输出格式遵循 Phase 4 已建立的 JSON/YAML 模式。

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| 连接映射构建 | Output Formatter | — | 纯数据转换逻辑，无需 I/O |
| 执行流追踪 | Output Formatter | — | 图遍历算法，无外部依赖 |
| CLI --graph 标志 | CLI Layer | Output Formatter | argparse 配置 + formatter 选择 |
| JSON graphs 字段 | Output Formatter | — | 扩展 format_json_full() |
| 文本图摘要 | Output Formatter | — | 扩展 format_text_full() |

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

#### 连接映射构建
- **D-08-01:** PinName 全图匹配 —— LinkedTo 原始数据通过搜索所有节点的引脚，找到 PinName 匹配的引脚，返回其 PinId
- **D-08-02:** NodeGuid + PinName 表示 —— 连接使用 `{node_guid, pin_name}` 组合表示，而非 PinId GUID hex
- **D-08-03:** Graph.connections 位置 —— 连接映射放在图层级 `Graph.connections` 数组，而非引脚层级
- **D-08-04:** 警告 + 原始数据 —— 匹配失败时输出 warning 字段和原始 LinkedTo 数据
- **D-08-05:** 单向表示 —— 每个连接仅出现一次（Output Pin → Input Pin 方向）
- **D-08-06:** `{from, to}` 对象结构 —— 每个连接元素为 `{from: {node_guid, pin_name}, to: {node_guid, pin_name}}`

#### 执行流路径
- **D-08-07:** Event → CallFunction 链路 —— 从 Event 节点（K2Node_Event）开始，沿连接追踪到 CallFunction 节点
- **D-08-08:** 节点详细信息序列 —— 每条执行流为节点对象序列 `[{node_guid, node_type, function_name}, ...]`
- **D-08-09:** execution_flows 数组 —— 每个 Graph 对象包含 `execution_flows` 数组组织多条执行流
- **D-08-10:** 分支处停止 —— 遇到控制流节点（If、Switch）时停止追踪
- **D-08-11:** 循环检测并停止 —— 追踪时检测已访问节点，遇到循环时停止并标记

#### CLI --graph 标志
- **D-08-12:** 独立可组合标志 —— --graph 不与 --json/--text/--summary 互斥，可组合使用
- **D-08-13:** 输出范围取决于 --verbose —— 默认仅输出 graphs 字段，与 --verbose 组合时输出完整结构 + graphs

### Claude's Discretion
- Graph 对象的具体字段列表（graph_name, graph_class, nodes, connections, execution_flows 的完整结构）
- 文本输出图结构摘要的具体格式（节点数、连接数、执行流概览的 YAML 风格）
- 连接映射的验证机制（同名引脚冲突处理）
- 执行流节点详细信息的具体字段（node_guid, node_type, function_name之外是否包含更多）
- 单元测试组织

### Deferred Ideas (OUT OF SCOPE)
- OUT2-02 高级属性解析结果输出（推迟到 Phase 9，需先实现属性解析）
- 完整控制流图（考虑所有控制流节点分支）
- 连接验证机制（同名引脚冲突处理）
- 更多节点类型的执行流追踪（K2Node_Variable、K2Node_DynamicCast 等）
- 图可视化输出（SVG/DOT 格式）
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| GRAPH-11 | JSON 输出包含蓝图图层级结构（Graph → Nodes → Pins） | § Architecture Patterns: graphs JSON 结构设计 |
| GRAPH-12 | JSON 输出包含执行流路径（从 Event → CallFunction 链路） | § Execution Flow Tracing Algorithm |
| OUT2-01 | JSON 输出包含完整的蓝图图数据（与 blueprint 字段同级） | § JSON Output Extension: format_json_full() 扩展点 |
| OUT2-03 | 文本输出包含图结构摘要（节点数、连接数、执行流概览） | § Text Output Extension: format_text_full() 扩展点 |
| OUT2-04 | CLI 支持 --graph 标志仅输出蓝图图数据 | § CLI Design: argparse 可组合标志实现 |

**注意:** OUT2-02 已在 CONTEXT.md deferred 中标记为推迟到 Phase 9，不在本阶段研究范围内。
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Python dataclasses | 3.10+ | 数据结构 | Phase 1 D-06 已确定，asdict() → JSON |
| json (stdlib) | 3.10+ | JSON 输出 | Phase 4 D-28 已确定，UTF-8 编码 |
| argparse (stdlib) | 3.10+ | CLI | Phase 4 D-23 已确定，零依赖 |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| dataclasses.asdict() | 3.10+ | dataclass → dict | 所有 dataclass JSON 序列化 |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| 自定义连接映射算法 | 图遍历库（networkx） | networkx 引入外部依赖，违反 PROJECT.md 约束 |

**Installation:**
无安装需求 —— 仅使用 Python 标准库。

**Version verification:**
Python 3.10+ 已由 Phase 1 确定。

## Architecture Patterns

### System Architecture Diagram

```
ParseResult.graphs (List[UEdGraph])
    ↓
format_graphs_json() ← 新增函数
    ├─ build_connections_map() — 构建连接映射
    │   └─ linked_to_raw (GUID hex) → 搜索全图 → {node_guid, pin_name}
    └─ build_execution_flows() — 构建执行流
    │   └─ 遍历 K2Node_Event → 沿 exec pins 追踪 → 停止条件检测
    ↓
JSON output:
{
  "graphs": [
    {
      "graph_name": "EventGraph",
      "nodes": [...],
      "connections": [{from: {...}, to: {...}}],
      "execution_flows": [{node_guid, node_type, function_name}]
    }
  ]
}
```

### Recommended Project Structure

```
uasset_read.py
├── 数据类（第 783-900 行）
│   ├── UEdGraphPin, UEdGraphNode, UEdGraph — Phase 7 已实现
│   └── 无需新增数据类
├── 输出函数（第 3178-3465 行）
│   ├── format_json_full() — 需扩展，添加 graphs 字段
│   ├── format_graphs_json() — 新增，图数据格式化
│   ├── build_connections_map() — 新增，连接映射构建
│   ├── build_execution_flows() — 新增，执行流追踪
│   └── format_text_full() — 需扩展，添加图结构摘要
├── CLI（第 3530-3625 行）
│   └── create_parser() — 需扩展，添加 --graph 标志
└── main() — 需扩展，添加 --graph 分支逻辑
```

### Pattern 1: 连接映射构建算法

**What:** 将 linked_to_raw（PinId GUID hex）转换为 {node_guid, pin_name} 表示

**When to use:** 输出格式化阶段（format_graphs_json 内调用）

**Algorithm:**

```python
def build_connections_map(graph: UEdGraph) -> Tuple[List[Dict], List[str]]:
    """
    构建连接映射（D-08-01~06）。
    
    算法：
    1. 构建 PinId → (node_guid, pin_name) 查找表
    2. 遍历所有 Output pins (direction=1)
    3. 对每个 linked_to_raw 中的 PinId，查找目标 pin
    4. 构建 {from, to} 连接对象
    5. 处理查找失败（warning + 原始数据）
    
    Returns:
        Tuple[List[Dict], List[str]]: (connections, warnings)
    """
    # Step 1: Build lookup table
    pin_lookup: Dict[str, Tuple[str, str]] = {}  # pin_id → (node_guid, pin_name)
    for node in graph.nodes:
        for pin in node.pins:
            pin_lookup[pin.pin_id] = (node.node_guid, pin.pin_name)
    
    # Step 2-4: Build connections (only from Output pins)
    connections: List[Dict] = []
    warnings: List[str] = []
    
    for node in graph.nodes:
        for pin in node.pins:
            if pin.direction == 1:  # EGPD_Output
                for linked_pin_id in pin.linked_to_raw:
                    if linked_pin_id in pin_lookup:
                        target_node_guid, target_pin_name = pin_lookup[linked_pin_id]
                        connections.append({
                            "from": {"node_guid": node.node_guid, "pin_name": pin.pin_name},
                            "to": {"node_guid": target_node_guid, "pin_name": target_pin_name}
                        })
                    else:
                        # D-08-04: Warning + raw data
                        warnings.append(f"PinId {linked_pin_id} not found in graph")
                        connections.append({
                            "from": {"node_guid": node.node_guid, "pin_name": pin.pin_name},
                            "to": {"raw_pin_id": linked_pin_id},
                            "warning": "target pin not found"
                        })
    
    return connections, warnings
```

**Source:** [VERIFIED: uasset_read.py L797, L1945-1950] - linked_to_raw 存储为 PinId GUID hex 列表

### Pattern 2: 执行流追踪算法

**What:** 从 K2Node_Event 开始，追踪执行流到 CallFunction 链路

**When to use:** 输出格式化阶段（format_graphs_json 内调用）

**Algorithm:**

```python
# 控制流节点类型（D-08-10）
CONTROL_FLOW_NODES = {
    "K2Node_IfThenElse",
    "K2Node_Switch",
    "K2Node_SwitchString",
    "K2Node_SwitchEnum",
    "K2Node_SwitchInteger",
}

def build_execution_flows(graph: UEdGraph) -> List[Dict]:
    """
    构建执行流路径（D-08-07~11）。
    
    算法：
    1. 找到所有 K2Node_Event 节点（执行流起点）
    2. 对每个 Event，沿 exec pin 连接追踪
    3. 记录节点信息：{node_guid, node_type, function_name}
    4. 检测控制流节点 → 停止
    5. 检测已访问节点 → 停止并标记循环
    
    Returns:
        List[Dict]: execution_flows 数组
    """
    # Step 0: Build pin lookup for connection resolution
    pin_lookup = _build_pin_lookup(graph)
    node_lookup = {n.node_guid: n for n in graph.nodes}
    
    execution_flows: List[Dict] = []
    
    # Step 1: Find Event nodes
    event_nodes = [n for n in graph.nodes if n.class_name == "K2Node_Event"]
    
    for event_node in event_nodes:
        flow = _trace_execution_from_event(
            event_node, graph, pin_lookup, node_lookup
        )
        execution_flows.append({
            "start_event": _get_event_name(event_node),
            "nodes": flow
        })
    
    return execution_flows

def _trace_execution_from_event(
    start_node: UEdGraphNode,
    graph: UEdGraph,
    pin_lookup: Dict,
    node_lookup: Dict
) -> List[Dict]:
    """追踪单条执行流。"""
    visited: Set[str] = set()  # D-08-11: 循环检测
    flow: List[Dict] = []
    current_node = start_node
    
    while current_node:
        # 循环检测
        if current_node.node_guid in visited:
            flow.append({
                "node_guid": current_node.node_guid,
                "node_type": current_node.class_name,
                "cycle_detected": True
            })
            break
        visited.add(current_node.node_guid)
        
        # 记录节点信息
        node_info = {
            "node_guid": current_node.node_guid,
            "node_type": current_node.class_name,
        }
        if current_node.class_name == "K2Node_CallFunction":
            # D-08-08: 添加 function_name
            if current_node.node_data and hasattr(current_node.node_data, 'function_reference'):
                node_info["function_name"] = current_node.node_data.function_reference.member_name
        elif current_node.class_name == "K2Node_Event":
            if current_node.node_data and hasattr(current_node.node_data, 'event_reference'):
                node_info["event_name"] = current_node.node_data.event_reference.member_name
        flow.append(node_info)
        
        # D-08-10: 控制流节点停止
        if current_node.class_name in CONTROL_FLOW_NODES:
            flow.append({"stopped_at": "control_flow_node"})
            break
        
        # 查找下一个节点（沿 exec output pin）
        next_node = _find_next_exec_node(current_node, pin_lookup, node_lookup)
        current_node = next_node
    
    return flow

def _find_next_exec_node(
    node: UEdGraphNode,
    pin_lookup: Dict,
    node_lookup: Dict
) -> Optional[UEdGraphNode]:
    """查找 exec output pin 连接的下一个节点。"""
    # 找到 exec 类型 output pin
    for pin in node.pins:
        if pin.direction == 1 and pin.pin_type.pin_category == "exec":
            # 查找连接的目标 pin
            for linked_pin_id in pin.linked_to_raw:
                if linked_pin_id in pin_lookup:
                    target_node_guid, _ = pin_lookup[linked_pin_id]
                    return node_lookup.get(target_node_guid)
    return None
```

**Source:** [VERIFIED: uasset_read.py L874-884] - K2NodeEvent 数据结构

### Anti-Patterns to Avoid

- **遍历所有 pins 构建 connections:** 应只从 Output pins 出发（D-08-05），避免双向重复
- **使用 PinId GUID hex 作为连接表示:** D-08-02 明确要求使用 {node_guid, pin_name}，更可读
- **在 parse 阶段构建连接映射:** D-01 明确延迟到输出阶段，Phase 7 仅存储原始数据

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| 图遍历算法 | networkx 依赖 | 纯 Python dict + set | PROJECT.md 约束零运行时依赖 |
| JSON 序列化 | 自定义 serializer | dataclasses.asdict() + json.dumps | Phase 1 D-06 已确定 |

**Key insight:** 蓝图图结构简单（树状层级），无需复杂图算法库。

## Runtime State Inventory

> Phase 8 不涉及 rename/refactor/migration，此部分省略。

**Nothing found in category:** Phase 8 为纯代码添加（新增输出函数和 CLI 标志），不修改现有数据结构名称或运行时状态。

## Common Pitfalls

### Pitfall 1: linked_to_raw 格式误解

**What goes wrong:** 误认为 linked_to_raw 存储的是 PinName 字符串，实际是 PinId GUID hex

**Why it happens:** CONTEXT.md D-08-01 描述"PinName 全图匹配"，易误解为原始数据格式

**How to avoid:** 阅读 uasset_read.py L1945-1950 实现，确认 linked_to_raw 存储的是 16 字节 GUID hex

**Warning signs:** 连接映射测试失败，查找 PinName 找不到匹配

### Pitfall 2: 双向连接重复

**What goes wrong:** 同时遍历 Input 和 Output pins，导致连接重复记录

**Why it happens:** 未理解 D-08-05"单向表示"决策

**How to avoid:** 仅从 Output pins (direction=1) 出发构建连接

**Warning signs:** connections 数量约为预期的 2 倍

### Pitfall 3: 执行流无限循环

**What goes wrong:** 蓝图中有回环（如 Loop 节点），追踪不停止

**Why it happens:** 未实现 D-08-11 循环检测

**How to avoid:** 使用 visited: Set[str] 记录已访问节点

**Warning signs:** 执行流测试超时或节点数量异常

### Pitfall 4: CLI --graph 与现有标志互斥

**What goes wrong:** 将 --graph 加入互斥组，导致无法组合使用

**Why it happens:** 未理解 D-08-12"独立可组合"决策

**How to avoid:** --graph 不加入 parser.add_mutually_exclusive_group()

**Warning signs:** `--json --graph` 组合报错

## Code Examples

### JSON Output Extension (format_json_full)

```python
# Source: [VERIFIED: uasset_read.py L3178-3212]
def format_json_full(result: ParseResult) -> Dict:
    """Phase 8 扩展：添加 graphs 字段"""
    # ... existing code ...
    
    return {
        "summary": summary_dict,
        "exports": format_exports_list(result),
        "blueprint_metadata": format_blueprint_dict(result.blueprint) if result.blueprint else None,
        "graphs": format_graphs_json(result.graphs),  # Phase 8: 新增
        "errors": result.errors
    }

def format_graphs_json(graphs: List[UEdGraph]) -> List[Dict]:
    """Phase 8: 格式化图数据"""
    from dataclasses import asdict
    
    formatted = []
    for graph in graphs:
        # 构建连接映射
        connections, warnings = build_connections_map(graph)
        
        # 构建执行流
        execution_flows = build_execution_flows(graph)
        
        graph_dict = {
            "graph_name": graph.graph_name,
            "graph_class": graph.graph_class,
            "schema": graph.schema,
            "graph_guid": graph.graph_guid,
            "nodes": [asdict(node) for node in graph.nodes],
            "connections": connections,
            "execution_flows": execution_flows,
        }
        
        if warnings:
            graph_dict["warnings"] = warnings
        
        formatted.append(graph_dict)
    
    return formatted
```

### Text Output Extension (format_text_full)

```python
# Source: [VERIFIED: uasset_read.py L3366-3444]
def format_text_full(result: ParseResult) -> str:
    """Phase 8 扩展：添加图结构摘要"""
    lines = []
    
    # ... existing package/exports/blueprint sections ...
    
    # Phase 8: Graphs section
    if result.graphs:
        lines.append("Graphs:")
        for graph in result.graphs:
            connections, _ = build_connections_map(graph)
            execution_flows = build_execution_flows(graph)
            
            lines.append(f"  - Name: {graph.graph_name}")
            lines.append(f"    Class: {graph.graph_class}")
            lines.append(f"    Nodes: {len(graph.nodes)}")
            lines.append(f"    Connections: {len(connections)}")
            
            # 执行流概览
            lines.append(f"    ExecutionFlows: {len(execution_flows)}")
            for flow in execution_flows:
                start = flow.get("start_event", "Unknown")
                lines.append(f"      - {start}: {len(flow['nodes'])} nodes")
    
    # ERRORS block (existing)
    # ...
    
    return "\n".join(lines)
```

### CLI --graph Flag

```python
# Source: [VERIFIED: uasset_read.py L3530-3560]
def create_parser() -> argparse.ArgumentParser:
    """Phase 8 扩展：添加 --graph 标志"""
    parser = argparse.ArgumentParser(
        prog='uasset_read',
        description='Parse Unreal Engine .uasset files and output structured data'
    )
    
    # Positional: file path
    parser.add_argument('file', help='Path to .uasset file to parse')
    
    # Mutually exclusive output flags (existing)
    group = parser.add_mutually_exclusive_group(required=False)
    group.add_argument('--json', action='store_true', help='Output full JSON structure')
    group.add_argument('--text', action='store_true', help='Output YAML-style text (default)')
    group.add_argument('--summary', action='store_true', help='Output compact summary format')
    
    # Phase 8: --graph flag (NOT in mutually_exclusive_group per D-08-12)
    parser.add_argument('--graph', action='store_true',
                        help='Output blueprint graph data (composable with --json/--text)')
    
    # Optional flags (existing)
    parser.add_argument('--verbose', action='store_true', help='Include extra detail fields')
    parser.add_argument('--output', metavar='FILE', help='Write output to file')
    parser.add_argument('--export', metavar='INDEX', type=int, help='Output specific export')
    
    return parser

def main():
    """Phase 8 扩展：--graph 分支逻辑"""
    # ... existing parsing code ...
    
    # Output selection with --graph composable
    if args.graph:
        # D-08-13: --graph alone outputs only graphs, --verbose adds full context
        if args.json or args.verbose:
            output_str = json.dumps(format_json_full(result), indent=2, ensure_ascii=False)
        else:
            # Default: only graphs in JSON format
            output_str = json.dumps({"graphs": format_graphs_json(result.graphs)}, indent=2, ensure_ascii=False)
    elif args.json:
        output_str = json.dumps(format_json_full(result), indent=2, ensure_ascii=False)
    elif args.summary:
        output_str = json.dumps(format_json_summary(result), indent=2, ensure_ascii=False)
    else:
        output_str = format_text_full(result)
    
    # ... existing output routing ...
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| linked_to_raw 存储为名称列表 | linked_to_raw 存储为 PinId GUID hex | Phase 7 D-01a | 连接映射需要 GUID → node/pin 查找 |
| CLI 标志互斥设计 | --graph 可组合设计 | Phase 8 D-08-12 | 用户可组合 --json --graph |

**Deprecated/outdated:**
- ROADMAP.md L257-260 描述的 UEdGraphPinRef 结构：实际实现为 linked_to_raw (List[str])

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | linked_to_raw 存储 PinId GUID hex 格式正确 | Standard Stack | 连接映射算法失效 |

**Assumption A1 已验证:** [VERIFIED: uasset_read.py L1945-1950] - read_bytes(16).hex() 确认格式

## Open Questions

1. **同名引脚冲突处理**
   - What we know: D-08-04 要求 warning + 原始数据
   - What's unclear: 同一节点内多个同名引脚如何区分（罕见情况）
   - Recommendation: 使用 pin_id 作为 fallback，在 warning 中说明

2. **K2Node_Event 的 event_name 提取**
   - What we know: K2NodeEvent.node_data.event_reference.member_name 包含事件名
   - What's unclear: node_data 可能为 None（解析失败时）
   - Recommendation: 使用 hasattr 检查 + 默认值 "Unknown"

## Environment Availability

> Step 2.6: SKIPPED (无外部依赖 - 仅使用 Python 标准库)

**Phase 8 无外部依赖:** 所有实现基于 Python 3.10+ 标准库（dataclasses, json, argparse）

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 9.0.3 [VERIFIED: pytest --collect-only] |
| Config file | None (默认 pytest.ini detection) |
| Quick run command | `python -m pytest tests/test_output_formatting.py -x -v` |
| Full suite command | `python -m pytest tests/ -v` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| GRAPH-11 | JSON 输出包含 graphs 层级结构 | unit | `pytest tests/test_output_formatting.py::test_format_json_full_contains_graphs -v` | ❌ Wave 0 |
| GRAPH-12 | JSON 输出包含 execution_flows | unit | `pytest tests/test_output_formatting.py::test_format_json_full_contains_execution_flows -v` | ❌ Wave 0 |
| OUT2-01 | graphs 与 blueprint 同级 | unit | `pytest tests/test_output_formatting.py::test_graphs_field_top_level -v` | ❌ Wave 0 |
| OUT2-03 | 文本输出图摘要 | unit | `pytest tests/test_output_formatting.py::test_format_text_full_contains_graph_summary -v` | ❌ Wave 0 |
| OUT2-04 | CLI --graph 标志 | unit | `pytest tests/test_output_formatting.py::test_cli_graph_flag -v` | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** `python -m pytest tests/test_output_formatting.py -x`
- **Per wave merge:** `python -m pytest tests/ -v`
- **Phase gate:** Full suite green (152 tests) before `/gsd-verify-work`

### Wave 0 Gaps
- [ ] `tests/test_output_formatting.py` — 新增测试文件，覆盖 Phase 8 所有需求
- [ ] `build_connections_map()` — 新增函数，需单元测试
- [ ] `build_execution_flows()` — 新增函数，需单元测试
- [ ] `format_graphs_json()` — 新增函数，需单元测试
- [ ] CLI `--graph` 标志测试 — 需模拟 argparse 测试

## Security Domain

> Phase 8 无安全敏感操作（纯数据格式化），security_domain 简化。

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V5 Input Validation | yes | 内置边界检查（MAX_NODES_PER_GRAPH, MAX_PINS_PER_NODE） |

### Known Threat Patterns for Python Data Processing

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| 无限循环（执行流追踪） | Denial of Service | visited set 循环检测（D-08-11） |
| 内存溢出（大图遍历） | Denial of Service | Phase 7 安全边界常量已限制 |

**Security Note:** Phase 7 已实现 MAX_NODES_PER_GRAPH=5000, MAX_LINKEDTO_PER_PIN=100 边界，Phase 8 继承这些限制。

## Sources

### Primary (HIGH confidence)
- [uasset_read.py L783-838] - UEdGraphPin/UEdGraphNode/UEdGraph 数据类定义
- [uasset_read.py L1945-1950] - linked_to_raw 存储实现（GUID hex）
- [uasset_read.py L3178-3212] - format_json_full() 现有实现
- [uasset_read.py L3530-3560] - create_parser() 现有实现
- [08-CONTEXT.md] - Phase 8 用户决策

### Secondary (MEDIUM confidence)
- [07-CONTEXT.md] - Phase 7 决策（linked_to_raw 原始数据）
- [04-CONTEXT.md] - Phase 4 决策（JSON 结构、CLI 标志）

### Tertiary (LOW confidence)
- None - 所有关键实现已通过代码验证

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - 零外部依赖，纯 Python 标准库
- Architecture: HIGH - Phase 7/4 已建立模式，Phase 8 扩展
- Pitfalls: HIGH - 基于代码验证和用户决策分析

**Research date:** 2026-05-02
**Valid until:** 30 days (稳定阶段，无外部依赖变更风险)

---

*Phase: 08-blueprint-graph-output*
*Research completed: 2026-05-02*