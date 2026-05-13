"""蓝图图流构建 — 执行流、数据流、连接映射。

等价迁移 uasset_read.py L6478-6620, L6546-6607, L6836-7114。
Phase 31: 蓝图图解析模块。
"""
from __future__ import annotations

from typing import Dict, List, Optional, Tuple, Set, Any

from uasset_read.constants import (
    START_EVENT_TYPES, CONTROL_FLOW_NODES, BRANCH_TYPE_MAP,
    FORMAT_CONFIG, GRAPH_TYPE_MAP,
)
from uasset_read.models.core import UEdGraph, UEdGraphNode, UEdGraphPin
from uasset_read.models.node_types import (
    K2NodeCallFunction, K2NodeEvent, K2NodeKnot,
    EdGraphNodeComment, K2NodeEnhancedInputAction
)


# ============================================================================
# 辅助函数
# ============================================================================

def _derive_node_name(node: UEdGraphNode, idx: int) -> str:
    """从节点派生用户友好的节点名（D-19-02）。

    策略：使用 f"{class_name}_{idx}" 格式，避免同名节点冲突。
    """
    return f"{node.class_name}_{idx}"


def format_pin_ref(
    node_guid: str,
    pin_name: str,
    node_name_lookup: Dict[str, str],
    mode: str = "name"
) -> Dict:
    """格式化 Pin 引用（D-19-02, D-19-05）。

    Args:
        node_guid: 节点 GUID
        pin_name: Pin 名称
        node_name_lookup: node_guid → node_name 查找表
        mode: "name" 或 "guid" 模式（默认 name）

    Returns:
        Dict: 格式化后的 Pin 引用对象
    """
    if mode == "name":
        if node_guid in node_name_lookup:
            return {
                "node": node_name_lookup[node_guid],
                "pin": pin_name
            }
        else:
            return {
                "node_guid": node_guid,
                "pin": pin_name,
                "warning": "node_name lookup failed"
            }
    else:
        return {
            "node_guid": node_guid,
            "pin_name": pin_name
        }


def format_node_dict(node: UEdGraphNode, idx: int) -> Dict:
    """格式化单个节点为 OUT-01 规范 JSON 结构（Phase 31 等价迁移）。

    Per D-20-01: node_name 使用 _derive_node_name() 派生
    Per D-20-02: 字段名规范化（node_type, position:{x,y})
    Per D-20-03: function_reference/event_reference 提升到顶层

    Args:
        node: UEdGraphNode 节点对象
        idx: 节点在图中的索引

    Returns:
        Dict: OUT-01 规范节点结构
    """
    from dataclasses import asdict

    # D-20-01: 派生 node_name
    node_name = _derive_node_name(node, idx)

    # D-20-02: 字段名规范化
    result = {
        "node_name": node_name,
        "node_type": node.class_name,
        "node_guid": node.node_guid,
        "position": {"x": node.node_pos_x, "y": node.node_pos_y},
        "node_comment": node.node_comment,
        "pins": [asdict(pin) for pin in node.pins]  # Pin格式保持Phase 18规范
    }

    # D-20-03: 嵌套结构展开（兼容 dict 和 dataclass node_data）
    if node.node_data is not None:
        nd = node.node_data
        # Helper: get value from dict key or object attribute
        def _get(key):
            if isinstance(nd, dict):
                return nd.get(key)
            return getattr(nd, key, None)

        fr = _get('function_reference')
        if fr is not None:
            result["function_reference"] = {
                "member_name": getattr(fr, 'member_name', None),
                "member_parent": getattr(fr, 'member_parent', None),
                "self_context": getattr(fr, 'b_self_context', None)
            }
        elif _get('event_reference') is not None:
            er = _get('event_reference')
            result["event_reference"] = {
                "member_name": getattr(er, 'member_name', None),
                "member_parent": getattr(er, 'member_parent', None),
                "member_guid": getattr(er, 'member_guid', None)
            }
        elif _get('input_action_path') is not None:
            result["input_action_path"] = _get('input_action_path')
        # Knot/Comment 无额外顶层字段

    return result


def _get_start_event_name(node: UEdGraphNode) -> str:
    """获取起点节点的事件名称（D-19-11）。

    支持4种起点类型：
    - K2Node_Event: event_reference.member_name（dict或dataclass）
    - K2Node_EnhancedInputAction: input_action_path或class_name
    - K2Node_VariableSet: "VariableSet"
    - K2Node_CustomEvent: "CustomEvent"

    Fallback: 如果无法提取具体名称，返回 node.class_name 而非 "Unknown"。
    """
    nd = node.node_data

    if node.class_name == "K2Node_Event":
        if not nd:
            return node.class_name
        # node_data is a dict from read_k2node_event(), or a K2NodeEvent dataclass
        if isinstance(nd, dict):
            er = nd.get("event_reference")
        else:
            er = getattr(nd, 'event_reference', None)

        if er is None:
            return node.class_name

        # er is FMemberReference object
        if hasattr(er, 'member_name'):
            mn = er.member_name
        elif isinstance(er, dict):
            mn = er.get("member_name")
        else:
            mn = None

        if not mn or mn == "None":
            return node.class_name

        # member_name can be a path like "/Game/.../BP_X_37120"
        if '/' in mn:
            return mn.split('/')[-1]
        return mn

    elif node.class_name == "K2Node_EnhancedInputAction":
        if nd:
            if isinstance(nd, dict):
                path = nd.get("input_action_path", "")
            else:
                path = getattr(nd, 'input_action_path', "")
            if path:
                return path.split('/')[-1] if '/' in path else path
        return node.class_name
    elif node.class_name == "K2Node_VariableSet":
        return "VariableSet"
    elif node.class_name == "K2Node_CustomEvent":
        return "CustomEvent"

    return node.class_name


def _find_next_exec_node(
    node: UEdGraphNode,
    pin_lookup: Dict[str, Tuple[str, str]],
    node_lookup: Dict[str, UEdGraphNode]
) -> Optional[UEdGraphNode]:
    """查找 exec output pin 连接的下一个节点。

    Args:
        node: 当前节点
        pin_lookup: pin_id → (node_guid, pin_name) 查找表
        node_lookup: node_guid → node 查找表

    Returns:
        Optional[UEdGraphNode]: 下一个节点，或 None
    """
    for pin in node.pins:
        if pin.direction == 1:  # Output
            if pin.pin_type and pin.pin_type.pin_category == "exec":
                for linked_pin_id in (pin.linked_to_raw or []):
                    target_pin_guid = linked_pin_id.get("pin_guid") if isinstance(linked_pin_id, dict) else linked_pin_id
                    if target_pin_guid in pin_lookup:
                        target_node_guid, _ = pin_lookup[target_pin_guid]
                        return node_lookup.get(target_node_guid)
    return None


def _trace_execution_from_event(
    start_node: UEdGraphNode,
    pin_lookup: Dict[str, Tuple[str, str]],
    node_lookup: Dict[str, UEdGraphNode]
) -> List[Dict]:
    """追踪单条执行流（D-08-07~11, D-19-13~14）。

    Args:
        start_node: K2Node_Event 起点（或其他START_EVENT_TYPES起点）
        pin_lookup: pin_id → (node_guid, pin_name) 查找表
        node_lookup: node_guid → node 查找表

    Returns:
        List[Dict]: 节点信息序列
    """
    visited: Set[str] = set()
    flow: List[Dict] = []
    current_node = start_node

    while current_node:
        if current_node.node_guid in visited:
            flow.append({
                "node_guid": current_node.node_guid,
                "node_type": current_node.class_name,
                "cycle_detected": True
            })
            break

        visited.add(current_node.node_guid)

        node_info = {
            "node_guid": current_node.node_guid,
            "node_type": current_node.class_name,
        }

        if current_node.class_name == "K2Node_CallFunction":
            nd = current_node.node_data
            if nd:
                fr = nd.get("function_reference") if isinstance(nd, dict) else getattr(nd, 'function_reference', None)
                if fr:
                    node_info["function_name"] = getattr(fr, 'member_name', None)

        if current_node.class_name == "K2Node_Event":
            nd = current_node.node_data
            if nd:
                er = nd.get("event_reference") if isinstance(nd, dict) else getattr(nd, 'event_reference', None)
                if er:
                    node_info["event_name"] = getattr(er, 'member_name', None)

        if current_node.class_name in CONTROL_FLOW_NODES:
            branch_type = BRANCH_TYPE_MAP.get(current_node.class_name, "unknown")
            node_info["branch_type"] = branch_type
            node_info["stopped_at"] = "control_flow_node"
            flow.append(node_info)
            break

        flow.append(node_info)
        current_node = _find_next_exec_node(current_node, pin_lookup, node_lookup)

    return flow


def _trace_execution_from_pin(
    start_node: UEdGraphNode,
    start_pin: UEdGraphPin,
    pin_lookup: Dict[str, Tuple[str, str]],
    node_lookup: Dict[str, UEdGraphNode]
) -> List[Dict]:
    """从特定Pin开始追踪执行流（D-19-12）。

    用于EnhancedInputAction多触发时机追踪。
    """
    for linked_pin_id in (start_pin.linked_to_raw or []):
        target_pin_guid = linked_pin_id.get("pin_guid") if isinstance(linked_pin_id, dict) else linked_pin_id
        if target_pin_guid in pin_lookup:
            target_node_guid, _ = pin_lookup[target_pin_guid]
            next_node = node_lookup.get(target_node_guid)
            if next_node:
                return _trace_execution_from_event(next_node, pin_lookup, node_lookup)

    return []


# ============================================================================
# 主函数
# ============================================================================

def build_connections_map(graph: UEdGraph) -> Tuple[List[Dict], List[str]]:
    """构建引脚连接映射（D-08-01~06, LINK-01, D-19-01~05）。

    将 linked_to_raw（PinId GUID hex）转换为用户友好的节点引用格式。

    Args:
        graph: UEdGraph 对象

    Returns:
        Tuple[List[Dict], List[str]]: (connections 列表, warnings 列表)
    """
    node_name_lookup: Dict[str, str] = {}
    for idx, node in enumerate(graph.nodes):
        node_name_lookup[node.node_guid] = _derive_node_name(node, idx)

    pin_lookup: Dict[str, Tuple[str, str]] = {}
    for node in graph.nodes:
        for pin in node.pins:
            pin_lookup[pin.pin_id] = (node.node_guid, pin.pin_name)

    mode = FORMAT_CONFIG["pin_reference_mode"]
    connections: List[Dict] = []
    warnings: List[str] = []

    for node in graph.nodes:
        for pin in node.pins:
            if pin.direction == 1:  # Output
                for linked_pin_ref in (pin.linked_to_raw or []):
                    target_pin_guid = linked_pin_ref.get("pin_guid") if isinstance(linked_pin_ref, dict) else linked_pin_ref

                    if target_pin_guid in pin_lookup:
                        target_node_guid, target_pin_name = pin_lookup[target_pin_guid]
                        connections.append({
                            "from": format_pin_ref(node.node_guid, pin.pin_name, node_name_lookup, mode),
                            "to": format_pin_ref(target_node_guid, target_pin_name, node_name_lookup, mode)
                        })
                    else:
                        warnings.append(f"PinId {target_pin_guid} not found in graph")
                        connections.append({
                            "from": format_pin_ref(node.node_guid, pin.pin_name, node_name_lookup, mode),
                            "to": {"raw_pin_id": target_pin_guid},
                            "warning": "target pin not found"
                        })

    return connections, warnings


def build_execution_flows(graph: UEdGraph) -> List[Dict]:
    """构建执行流路径（D-08-07~11, D-19-10~12）。

    从 START_EVENT_TYPES 节点开始，沿 exec pin 连接追踪到 CallFunction 链路。

    Args:
        graph: UEdGraph 对象

    Returns:
        List[Dict]: execution_flows 数组
    """
    pin_lookup: Dict[str, Tuple[str, str]] = {}
    node_lookup: Dict[str, UEdGraphNode] = {}

    for node in graph.nodes:
        node_lookup[node.node_guid] = node
        for pin in node.pins:
            pin_lookup[pin.pin_id] = (node.node_guid, pin.pin_name)

    execution_flows: List[Dict] = []
    start_nodes = [n for n in graph.nodes if n.class_name in START_EVENT_TYPES]

    for start_node in start_nodes:
        if start_node.class_name == "K2Node_EnhancedInputAction":
            for pin in start_node.pins:
                if pin.direction == 1 and pin.pin_type and pin.pin_type.pin_category == "exec":
                    flow = _trace_execution_from_pin(start_node, pin, pin_lookup, node_lookup)
                    execution_flows.append({
                        "start_event": f"{start_node.class_name}.{pin.pin_name}",
                        "nodes": flow
                    })
        else:
            flow = _trace_execution_from_event(start_node, pin_lookup, node_lookup)
            start_event_name = _get_start_event_name(start_node)
            execution_flows.append({
                "start_event": start_event_name,
                "nodes": flow
            })

    return execution_flows


def build_data_flows(graph: UEdGraph, mode: str = "name") -> List[Dict]:
    """构建数据流图（D-19-06~09, LINK-03）。

    从非exec pins提取数据传递关系，构建data_flows数组。

    Args:
        graph: UEdGraph对象
        mode: 输出格式模式（"name"或"guid"，默认"name"）

    Returns:
        List[Dict]: data_flows数组
    """
    pin_lookup: Dict[str, Tuple[str, str]] = {}
    for node in graph.nodes:
        for pin in node.pins:
            pin_lookup[pin.pin_id] = (node.node_guid, pin.pin_name)

    node_name_lookup: Dict[str, str] = {}
    for idx, node in enumerate(graph.nodes):
        node_name_lookup[node.node_guid] = _derive_node_name(node, idx)

    data_flows: List[Dict] = []

    for node in graph.nodes:
        for pin in node.pins:
            if pin.direction == 1 and pin.pin_type and pin.pin_type.pin_category != "exec":
                for linked_pin_ref in (pin.linked_to_raw or []):
                    target_pin_guid = linked_pin_ref.get("pin_guid") if isinstance(linked_pin_ref, dict) else linked_pin_ref
                    if target_pin_guid in pin_lookup:
                        target_node_guid, target_pin_name = pin_lookup[target_pin_guid]
                        data_flows.append({
                            "source": format_pin_ref(node.node_guid, pin.pin_name, node_name_lookup, mode),
                            "target": format_pin_ref(target_node_guid, target_pin_name, node_name_lookup, mode)
                        })

    return data_flows


def build_graphs_summary(graphs: List[UEdGraph]) -> List[Dict]:
    """构建所有图的摘要（OUT-03, D-19-09）。

    Args:
        graphs: List[UEdGraph] 图列表

    Returns:
        List[Dict]: graphs_summary 数组
    """
    summaries: List[Dict] = []

    for graph in graphs:
        # 图类型映射
        graph_type = GRAPH_TYPE_MAP.get(graph.graph_class, graph.graph_class)

        # 执行流构建
        execution_flows = build_execution_flows(graph)

        # 连接映射构建
        connections, warnings = build_connections_map(graph)

        # 数据流构建（D-19-09）
        data_flows = build_data_flows(graph)

        # 过滤空 flow（EnhancedInputAction Started/Ongoing 可能无实际连接）
        non_empty_flows = [f for f in execution_flows if f.get("nodes")]

        summaries.append({
            "graph_name": graph.graph_name,
            "graph_type": graph_type,
            "node_count": len(graph.nodes),
            "schema": graph.schema,
            "execution_flows": non_empty_flows,
            "connections": connections,
            "data_flows": data_flows,  # D-19-09: 数据流与执行流独立分离
            "warnings": warnings if warnings else None,
        })

    return summaries


def format_graphs_json(graphs: List[UEdGraph]) -> List[Dict]:
    """格式化蓝图图数据为 JSON 输出（GRAPH-11, GRAPH-12, OUT-02, OUT-04）。

    等价迁移 uasset_read_legacy.py L6685-6735。

    Per D-08-03: connections 放在 graph 层级
    Per D-08-09: execution_flows 数组
    Per D-19-09: data_flows 数组（LINK-03）
    Per D-20-07: graph_type 语义化映射（EdGraph→event, UberEdGraph→uber）
    Per OUT-01: nodes 使用 format_node_dict 格式化

    Args:
        graphs: List[UEdGraph] from ParseResult.graphs

    Returns:
        List[Dict]: 每个 graph 的 JSON 表示
    """
    formatted = []
    for graph in graphs:
        # 图类型映射
        graph_type = GRAPH_TYPE_MAP.get(graph.graph_class, graph.graph_class)

        # 构建连接映射
        connections, warnings = build_connections_map(graph)

        # 构建执行流
        execution_flows = build_execution_flows(graph)

        # 构建数据流
        data_flows = build_data_flows(graph)

        graph_dict = {
            "graph_name": graph.graph_name,
            "graph_type": graph_type,
            "node_count": len(graph.nodes),  # D-14-04: 顶层 graphs_summary 使用 node_count
            "nodes": [format_node_dict(node, idx) for idx, node in enumerate(graph.nodes)],  # OUT-01: 完整节点列表
            "connections": connections,
            "execution_flows": execution_flows,
            "data_flows": data_flows,
        }

        # D-08-04: 添加 warnings（如果有）
        if warnings:
            graph_dict["warnings"] = warnings

        # 可选字段
        if graph.graph_guid:
            graph_dict["graph_guid"] = graph.graph_guid
        if graph.schema:
            graph_dict["schema"] = graph.schema

        formatted.append(graph_dict)

    return formatted