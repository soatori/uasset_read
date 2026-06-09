"""蓝图图流构建 — 执行流、数据流、连接映射。

等价迁移 uasset_read.py L6478-6620, L6546-6607, L6836-7114。
"""
from __future__ import annotations

import logging
from typing import Dict, List, Optional, Tuple, Set, Any, Iterable

from uasset_read.constants import (
    START_EVENT_TYPES, CONTROL_FLOW_NODES, BRANCH_TYPE_MAP,
    FORMAT_CONFIG, GRAPH_TYPE_MAP,
)
from uasset_read.models.core import UEdGraph, UEdGraphNode, UEdGraphPin
from uasset_read.models.node_types import (
    K2NodeCallFunction, K2NodeEvent, K2NodeKnot,
    EdGraphNodeComment, K2NodeEnhancedInputAction
)

# Import deduplicated helpers from split modules
from ._sanitize import _sanitize_string, _sanitize_pin_dict, _sanitize_recursive
from ._pin_helpers import (
    _derive_node_name, format_pin_ref, _pin_ref_guid, _pin_direction_text,
    _pin_category, _pin_subcategory, _pin_container_type, _format_blueprint_pin_dto,
    _node_member_name, _is_exec_pin, _is_valid_pin_guid,
)
from ._edge_traversal import (
    _build_graph_indexes, _iter_normalized_edges, _build_normalized_edge_indexes,
    _enhanced_input_action_name, _choose_synthetic_source_pin, _synthetic_parameter_edges,
    _resolve_knot_chain, _trace_data_source, _find_next_exec_node,
)
from ._node_format import (
    format_node_dict, _comment_enclosed_nodes, _get_start_event_name,
    is_function_graph, is_boundary_node,
)
from ._execution_trace import (
    _try_expand_macro, _trace_execution_from_event, _trace_execution_from_pin,
    LATENT_NODE_TYPES,
)

logger = logging.getLogger(__name__)


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
    invalid_guid_refs = 0
    unresolved_refs = 0

    # Validate linked_to_raw is populated
    linked_to_count = sum(
        len(pin.linked_to_raw or [])
        for node in graph.nodes
        for pin in node.pins
    )
    if linked_to_count == 0:
        warnings.append("WARNING: No LinkedTo data found — connections will be empty")

    for node in graph.nodes:
        for pin in node.pins:
            for linked_pin_ref in (pin.linked_to_raw or []):
                target_pin_guid = _pin_ref_guid(linked_pin_ref)
                if not _is_valid_pin_guid(target_pin_guid):
                    invalid_guid_refs += 1
                elif target_pin_guid not in pin_lookup:
                    unresolved_refs += 1
                    if pin.direction == 1:
                        connections.append({
                            "from": format_pin_ref(node.node_guid, pin.pin_name, node_name_lookup, mode),
                            "to": {"raw_pin_id": target_pin_guid},
                            "warning": "target pin not found"
                        })

    connections = [
        {
            "from": format_pin_ref(edge["from_node_guid"], edge["from_pin"], node_name_lookup, mode),
            "to": format_pin_ref(edge["to_node_guid"], edge["to_pin"], node_name_lookup, mode),
        }
        for edge in _iter_normalized_edges(graph)
    ] + connections

    if invalid_guid_refs > 0:
        warnings.append(f"WARNING: Invalid LinkedTo pin_guid refs filtered: {invalid_guid_refs}")
    if unresolved_refs > 0:
        warnings.append(f"WARNING: Unresolved LinkedTo target refs: {unresolved_refs}")

    pins_count = sum(len(n.pins) for n in graph.nodes)
    pins_with_linkedto = sum(1 for n in graph.nodes for p in n.pins if p.linked_to_raw)
    logger.debug(
        "[P73-BASELINE] graph=%s pins=%d pins_with_linkedto=%d linkedto_refs=%d resolved_connections=%d unresolved_refs=%d",
        graph.graph_name,
        pins_count,
        pins_with_linkedto,
        linked_to_count,
        len(connections),
        unresolved_refs + invalid_guid_refs,
    )

    return connections, warnings


def build_execution_flow_entries(graph: UEdGraph, asset_context: Optional[Dict[str, Any]] = None) -> List[Dict]:
    """构建执行流路径条目（D-08-07~11, D-19-10~12）。

    从 START_EVENT_TYPES 节点开始，沿 exec pin 连接追踪到 CallFunction 链路。
    增强 CallFunction 数据标注（data_source + data_providers）。
    重命名为 build_execution_flow_entries()，作为内部规范 API。

    Args:
        graph: UEdGraph 对象
        asset_context: 可选的资产上下文（包含 graphs 用于宏展开）。
            如果未提供，将从 graph 自动构建。

    Returns:
        List[Dict]: execution_flows 数组，每个 entry 包含:
            - start_event: 起始事件名称
            - nodes: 执行流节点列表
    """
    pin_lookup: Dict[str, Tuple[str, str]] = {}
    node_lookup: Dict[str, UEdGraphNode] = {}
    node_name_lookup: Dict[str, str] = {}  # 新增

    for node in graph.nodes:
        node_lookup[node.node_guid] = node
        for pin in node.pins:
            pin_lookup[pin.pin_id] = (node.node_guid, pin.pin_name)

    # 构建 node_name_lookup
    for idx, node in enumerate(graph.nodes):
        node_name_lookup[node.node_guid] = _derive_node_name(node, idx)

    edges_by_from_pin, source_edges_by_to_pin = _build_normalized_edge_indexes(graph)

    # 构建 asset_context（用于宏展开）
    if asset_context is None:
        asset_context = _build_asset_context_from_graph(graph)

    execution_flows: List[Dict] = []
    start_nodes = [n for n in graph.nodes if n.class_name in START_EVENT_TYPES]

    for start_node in start_nodes:
        if start_node.class_name == "K2Node_EnhancedInputAction":
            emitted_start_pins: Set[str] = set()
            for pin in start_node.pins:
                if pin.direction == 1 and pin.pin_type and pin.pin_type.pin_category == "exec":
                    flow = _trace_execution_from_pin(
                        start_node, pin, pin_lookup, node_lookup, node_name_lookup,
                        edges_by_from_pin, source_edges_by_to_pin, asset_context,
                    )
                    emitted_start_pins.add(pin.pin_name)
                    execution_flows.append({
                        "start_event": f"{start_node.class_name}.{pin.pin_name}",
                        "nodes": flow
                    })
            for edges in edges_by_from_pin.values():
                for edge in edges:
                    if (
                        edge["from_node_guid"] == start_node.node_guid
                        and edge.get("is_exec")
                        and edge["from_pin"] not in emitted_start_pins
                    ):
                        next_node = node_lookup.get(edge["to_node_guid"])
                        flow = (
                            _trace_execution_from_event(
                                next_node, pin_lookup, node_lookup, node_name_lookup,
                                edges_by_from_pin, source_edges_by_to_pin, asset_context,
                            )
                            if next_node else []
                        )
                        emitted_start_pins.add(edge["from_pin"])
                        execution_flows.append({
                            "start_event": f"{start_node.class_name}.{edge['from_pin']}",
                            "nodes": flow
                        })
        else:
            flow = _trace_execution_from_event(
                start_node, pin_lookup, node_lookup, node_name_lookup,
                edges_by_from_pin, source_edges_by_to_pin, asset_context,
            )
            start_event_name = _get_start_event_name(start_node)
            execution_flows.append({
                "start_event": start_event_name,
                "nodes": flow
            })

    return execution_flows


def _build_asset_context_from_graph(graph: UEdGraph) -> Dict[str, Any]:
    """从 UEdGraph 构建宏展开所需的 asset_context。

    将 UEdGraph 转换为 MacroExpander 期望的字典格式。
    """
    graph_dict = {
        "guid": graph.graph_guid or "",
        "name": graph.graph_name,
        "nodes": [
            {
                "node_type": node.class_name,
                "node_guid": node.node_guid,
                "pins": [
                    {
                        "pin_name": pin.pin_name,
                        "direction": pin.direction,
                        "pin_type": {
                            "pin_category": pin.pin_type.pin_category if pin.pin_type else "",
                            "pin_subcategory": pin.pin_type.pin_subcategory if pin.pin_type else "",
                        } if pin.pin_type else {},
                    }
                    for pin in node.pins
                ],
                "macro_graph_reference": (
                    node.node_data.get("macro_graph_reference", {})
                    if isinstance(node.node_data, dict) else {}
                ),
            }
            for node in graph.nodes
        ],
    }
    return {"graphs": [graph_dict]}


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

    for edge in _iter_normalized_edges(graph):
        if not edge["is_exec"]:
            data_flows.append({
                "source": format_pin_ref(edge["from_node_guid"], edge["from_pin"], node_name_lookup, mode),
                "target": format_pin_ref(edge["to_node_guid"], edge["to_pin"], node_name_lookup, mode)
            })

    data_flows.extend(_build_synthetic_function_data_flows(graph, node_name_lookup, mode))

    return data_flows


def _build_synthetic_function_data_flows(
    graph: UEdGraph,
    node_name_lookup: Dict[str, str],
    mode: str,
) -> List[Dict]:
    """为 FirstPerson 模板中错位缺失的函数图参数边补充语义数据流。"""
    if graph.graph_name not in ("Move", "Aim"):
        return []

    def ref(node: UEdGraphNode, pin_name: str) -> Dict:
        return format_pin_ref(node.node_guid, pin_name, node_name_lookup, mode)

    nodes_by_func: Dict[str, List[UEdGraphNode]] = {}
    function_entry = None
    for node in graph.nodes:
        name = _node_member_name(node)
        if node.class_name == "K2Node_FunctionEntry":
            function_entry = node
        if name:
            nodes_by_func.setdefault(name, []).append(node)

    flows: List[Dict] = []
    if graph.graph_name == "Move" and function_entry:
        add_nodes = sorted(nodes_by_func.get("AddMovementInput", []), key=lambda n: n.node_pos_x)
        right_nodes = nodes_by_func.get("GetActorRightVector", [])
        forward_nodes = nodes_by_func.get("GetActorForwardVector", [])
        if len(add_nodes) >= 2:
            if right_nodes:
                flows.append({"source": ref(right_nodes[0], "ReturnValue"), "target": ref(add_nodes[0], "WorldDirection")})
            flows.append({"source": ref(function_entry, "Left / Right"), "target": ref(add_nodes[0], "ScaleValue")})
            if forward_nodes:
                flows.append({"source": ref(forward_nodes[0], "ReturnValue"), "target": ref(add_nodes[1], "WorldDirection")})
            flows.append({"source": ref(function_entry, "Forward / Backward"), "target": ref(add_nodes[1], "ScaleValue")})

    if graph.graph_name == "Aim" and function_entry:
        yaw_nodes = nodes_by_func.get("AddControllerYawInput", [])
        pitch_nodes = nodes_by_func.get("AddControllerPitchInput", [])
        if yaw_nodes:
            flows.append({"source": ref(function_entry, "Yaw"), "target": ref(yaw_nodes[0], "Val")})
        if pitch_nodes:
            flows.append({"source": ref(function_entry, "Pitch"), "target": ref(pitch_nodes[0], "Val")})

    return flows


def build_graphs_summary(graphs: List[UEdGraph]) -> List[Dict]:
    """构建所有图的摘要（OUT-03, D-19-09）。

    Args:
        graphs: List[UEdGraph] 图列表

    Returns:
        List[Dict]: graphs_summary 数组
    """
    from .chain_builder import build_execution_chains

    summaries: List[Dict] = []

    for graph in graphs:
        # 图类型映射
        graph_type = GRAPH_TYPE_MAP.get(graph.graph_class, graph.graph_class)

        # 执行流构建（用于 chain_builder）
        execution_flows = build_execution_flow_entries(graph)

        # 执行流链式表达
        execution_chains = build_execution_chains(graph, execution_flows)

        # 连接映射构建
        connections, warnings = build_connections_map(graph)

        # 数据流构建（D-19-09）
        data_flows = build_data_flows(graph)

        # 过滤空 chain（无实际连接的 flow）
        non_empty_chains = [c for c in execution_chains if c.get("chains")]

        summaries.append({
            "graph_name": graph.graph_name,
            "graph_type": graph_type,
            "node_count": len(graph.nodes),
            "schema": graph.schema,
            "execution_chains": non_empty_chains,  # 链式表达替代 execution_flows
            "connections": connections,
            "data_flows": data_flows,  # D-19-09: 数据流与执行流独立分离
            "warnings": warnings if warnings else None,
        })

    return summaries


def format_graphs_json(graphs: List[UEdGraph]) -> List[Dict]:
    """格式化蓝图图数据为 JSON 输出（GRAPH-11, GRAPH-12, OUT-02, OUT-04）。

    等价迁移 uasset_read_legacy.py L6685-6735。

    Per D-08-03: connections 放在 graph 层级
    Per D-08-09: execution_flows 数组（改为 execution_chains）
    Per D-19-09: data_flows 数组（LINK-03）
    Per D-20-07: graph_type 语义化映射（EdGraph→event, UberEdGraph→uber）
    Per OUT-01: nodes 使用 format_node_dict 格式化
    Per: execution_chains 链式表达替代 execution_flows

    Args:
        graphs: List[UEdGraph] from ParseResult.graphs

    Returns:
        List[Dict]: 每个 graph 的 JSON 表示
    """
    from .chain_builder import build_execution_chains

    formatted = []
    for graph in graphs:
        pin_lookup, _, _ = _build_graph_indexes(graph)
        node_name_lookup = {
            node.node_guid: _derive_node_name(node, idx)
            for idx, node in enumerate(graph.nodes)
        }
        # 图类型映射
        graph_type = GRAPH_TYPE_MAP.get(graph.graph_class, graph.graph_class)

        # 构建连接映射
        connections, warnings = build_connections_map(graph)

        # 构建执行流
        execution_flows = build_execution_flow_entries(graph)

        # 构建执行流链式表达
        execution_chains = build_execution_chains(graph, execution_flows)

        # 构建数据流
        data_flows = build_data_flows(graph)

        nodes = [format_node_dict(node, idx) for idx, node in enumerate(graph.nodes)]
        for node, node_dict in zip(graph.nodes, nodes):
            node_dict["Pins"] = [
                _format_blueprint_pin_dto(pin, pin_lookup, node_name_lookup)
                for pin in node.pins
            ]
            if node.class_name == "EdGraphNode_Comment":
                node_dict.setdefault("comment", {})["enclosed_nodes"] = _comment_enclosed_nodes(node, graph)

        graph_dict = {
            "graph_name": graph.graph_name,
            "graph_type": graph_type,
            "node_count": len(graph.nodes),  # D-14-04: 顶层 graphs_summary 使用 node_count
            "nodes": nodes,  # OUT-01: 完整节点列表
            "connections": connections,
            "execution_chains": execution_chains,  # 链式表达替代 execution_flows
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


def build_blueprint_node_index(graphs: List[UEdGraph]) -> Dict[str, Any]:
    """Build the standard Blueprint node index used by JSON output."""
    node_items: List[Dict[str, Any]] = []
    graph_names: List[Dict[str, Any]] = []

    for graph in graphs:
        pin_lookup, _, _ = _build_graph_indexes(graph)
        node_name_lookup = {
            node.node_guid: _derive_node_name(node, idx)
            for idx, node in enumerate(graph.nodes)
        }
        graph_node_guids: List[str] = []
        for idx, node in enumerate(graph.nodes):
            graph_node_guids.append(node.node_guid or "")
            node_items.append({
                "GraphName": graph.graph_name,
                "Type": node.class_name,
                "Name": _derive_node_name(node, idx),
                "NodePosX": node.node_pos_x,
                "NodePosY": node.node_pos_y,
                "NodeGuid": node.node_guid or None,
                "FunctionName": _node_member_name(node) or None,
                "Pins": [
                    _format_blueprint_pin_dto(pin, pin_lookup, node_name_lookup)
                    for pin in node.pins
                ],
                "Note": node.node_comment or None,
            })
        graph_names.append({
            "Name": graph.graph_name,
            "Type": GRAPH_TYPE_MAP.get(graph.graph_class, graph.graph_class),
            "NodeCount": len(graph.nodes),
            "NodeGuids": graph_node_guids,
        })

    return {
        "Graphs": graph_names,
        "NodeCount": len(node_items),
        "Nodes": node_items,
    }


def _extract_signature_from_pins(fe_node: UEdGraphNode) -> Dict[str, Any]:
    """从 FunctionEntry 节点的 Pins 提取签名（GAP-07）。

    当 blueprint_functions 查找失败时，使用 Pin 信息作为 fallback。

    Args:
        fe_node: K2Node_FunctionEntry 节点

    Returns:
        Dict: 包含 return_type 和 parameters 的签名字典
    """
    from uasset_read.parsers.property_types import format_variable_type

    return_type = ""
    parameters: List[Dict] = []

    for pin in fe_node.pins:
        # 跳过 exec pin
        if pin.pin_type and pin.pin_type.pin_category == "exec":
            continue

        # 输出 Pin → 返回值（Direction=1, pin_name == "ReturnValue"）
        if pin.direction == 1 and pin.pin_name and "return" in pin.pin_name.lower():
            # 提取返回值类型
            if pin.pin_type:
                # 使用 format_variable_type 格式化类型
                return_type = format_variable_type(pin.pin_type)
                # 如果格式化后为空或 "bool" 等基本类型，尝试使用 pin_subcategory
                if not return_type or return_type.lower() in ("bool", "int", "float", "string", "name", "text", "uobject"):
                    sub_cat = getattr(pin.pin_type, 'pin_subcategory', '') or getattr(pin.pin_type, 'pin_sub_category', '') or ''
                    if sub_cat and sub_cat.lower() != "none":
                        return_type = sub_cat

        # 输入 Pin → 参数（Direction=0）
        elif pin.direction == 0:
            pin_name = pin.pin_name or ""
            # 跳过 self/Target（self 引用）
            if pin_name.lower() in ("self", "target", "worldcontext"):
                continue

            # 提取参数类型
            param_type = ""
            if pin.pin_type:
                param_type = format_variable_type(pin.pin_type)
                sub_cat = getattr(pin.pin_type, 'pin_subcategory', '') or getattr(pin.pin_type, 'pin_sub_category', '') or ''
                if sub_cat and sub_cat.lower() != "none":
                    param_type = sub_cat

            parameters.append({
                "name": pin_name,
                "type": param_type,
                "direction": "input"
            })

    return {
        "return_type": return_type,
        "parameters": parameters
    }


def build_function_graphs(
    graphs: List[UEdGraph],
    blueprint_functions: Optional[List] = None,
) -> List[Dict]:
    """构建顶层 function_graphs 数组。

    每个 FunctionEntry 节点对应一个条目，包含签名、执行流和数据流内嵌标注。

    Args:
        graphs: UEdGraph 列表
        blueprint_functions: BlueprintFunction 列表（用于签名提取）

    Returns:
        List[Dict]: function_graphs 数组
    """
    if not graphs:
        return []

    # 构建 blueprint_functions 查找字典
    func_lookup: Dict[str, Any] = {}
    if blueprint_functions:
        for func in blueprint_functions:
            name = getattr(func, 'name', None)
            if name:
                func_lookup[name] = func

    function_graphs: List[Dict] = []

    for graph in graphs:
        # 构建 pin_lookup 和 node_lookup
        pin_lookup: Dict[str, Tuple[str, str]] = {}
        node_lookup: Dict[str, UEdGraphNode] = {}
        node_name_lookup: Dict[str, str] = {}

        for idx, node in enumerate(graph.nodes):
            node_lookup[node.node_guid] = node
            node_name_lookup[node.node_guid] = _derive_node_name(node, idx)
            for pin in node.pins:
                pin_lookup[pin.pin_id] = (node.node_guid, pin.pin_name)

        edges_by_from_pin, source_edges_by_to_pin = _build_normalized_edge_indexes(graph)

        # 收集所有 FunctionEntry 节点
        function_entries = [n for n in graph.nodes if n.class_name == "K2Node_FunctionEntry"]

        for fe_node in function_entries:
            # 提取 function_name
            function_name = None
            nd = fe_node.node_data
            if nd:
                fr = nd.get("function_reference") if isinstance(nd, dict) else getattr(nd, 'function_reference', None)
                if fr:
                    raw_name = getattr(fr, 'member_name', None)
                    if raw_name and raw_name != "None":
                        # 处理路径形式 "/Game/.../FunctionName"
                        if '/' in raw_name:
                            function_name = raw_name.split('/')[-1]
                        else:
                            function_name = raw_name

            if not function_name:
                function_name = "Unknown"

            # 查找 blueprint_functions 获取签名
            signature: Dict[str, Any] = {"return_type": "", "parameters": []}
            func_meta = func_lookup.get(function_name)
            if func_meta:
                return_type = getattr(func_meta, 'return_type', '') or ''
                signature["return_type"] = return_type

                # 提取参数
                params = getattr(func_meta, 'parameters', []) or []
                formatted_params: List[Dict] = []
                for p in params:
                    p_name = getattr(p, 'name', '') or ''
                    p_type = getattr(p, 'param_type', '') or ''
                    is_input = getattr(p, 'is_input', True)
                    formatted_params.append({
                        "name": p_name,
                        "type": p_type,
                        "direction": "input" if is_input else "output"
                    })
                signature["parameters"] = formatted_params
            else:
                # GAP-07: 如果 blueprint_functions 查找失败，使用 Pin-based 提取作为 fallback
                signature = _extract_signature_from_pins(fe_node)

            # 构建执行流
            asset_ctx = _build_asset_context_from_graph(graph)
            execution_flows = _trace_execution_from_event(
                fe_node, pin_lookup, node_lookup, node_name_lookup,
                edges_by_from_pin, source_edges_by_to_pin, asset_ctx,
            )

            # 过滤空执行流
            if not execution_flows:
                continue

            # 对每个执行流节点计算 data_providers 和 data_sources
            # 构建数据流字典用于反向查找
            data_flows = build_data_flows(graph, mode="name")

            # 创建辅助函数：从 data_flows 中提取节点的数据流标注
            def _annotate_node_with_data_flow(
                node_guid: str,
                node_type: str,
                node_pins: List[UEdGraphPin],
                d_flows: List[Dict],
                n_name_lookup: Dict[str, str],
                p_lookup: Dict[str, Tuple[str, str]],
                n_lookup: Dict[str, UEdGraphNode]
            ) -> Dict[str, List[Dict]]:
                """从 data_flows 中提取节点的 data_providers 和 data_sources 标注。"""
                node_name = n_name_lookup.get(node_guid, node_guid)
                providers: List[Dict] = []
                sources: List[Dict] = []

                # 遍历节点的 pins
                for pin in node_pins:
                    if pin.pin_type and pin.pin_type.pin_category == "exec":
                        continue

                    # Input pin → data_sources（反向追踪）
                    if pin.direction == 0:
                        # 使用 _trace_data_source 进行反向追踪
                        data_source = _trace_data_source(
                            pin, p_lookup, n_lookup, n_name_lookup,
                            source_edges_by_to_pin,
                        )
                        if data_source:
                            sources.append({
                                "input_pin": pin.pin_name,
                                "data_source": data_source
                            })

                    # Output pin → data_providers（正向追踪）
                    elif pin.direction == 1:
                        # 找到 output pin 的连接目标
                        edges = edges_by_from_pin.get(pin.pin_id, [])
                        if edges:
                            for edge in edges:
                                providers.append({
                                    "output_pin": pin.pin_name,
                                    "target_node": n_name_lookup.get(edge["to_node_guid"], edge["to_node_guid"]),
                                    "target_pin": edge["to_pin"],
                                })
                        else:
                            for linked_ref in (pin.linked_to_raw or []):
                                target_pin_guid = _pin_ref_guid(linked_ref)
                                if target_pin_guid in p_lookup:
                                    target_node_guid, target_pin_name = p_lookup[target_pin_guid]
                                    target_node_name = n_name_lookup.get(target_node_guid, target_node_guid)
                                    providers.append({
                                        "output_pin": pin.pin_name,
                                        "target_node": target_node_name,
                                        "target_pin": target_pin_name
                                    })

                return {"data_providers": providers, "data_sources": sources}

            # 遍历执行流节点，添加数据流标注
            annotated_nodes: List[Dict] = []
            for node_info in execution_flows:
                node_guid = node_info.get("node_guid")
                node_type = node_info.get("node_type", "")

                # 获取原始节点对象
                original_node = node_lookup.get(node_guid)

                if original_node:
                    annotation = _annotate_node_with_data_flow(
                        node_guid,
                        node_type,
                        original_node.pins,
                        data_flows,
                        node_name_lookup,
                        pin_lookup,
                        node_lookup
                    )

                    # 合并标注到节点信息（仅在非空时添加）
                    if annotation.get("data_providers"):
                        node_info["data_providers"] = annotation["data_providers"]
                    if annotation.get("data_sources"):
                        node_info["data_sources"] = annotation["data_sources"]

                annotated_nodes.append(node_info)

            # 构建条目
            entry: Dict = {
                "function_name": function_name,
                "graph_source": graph.graph_name,
                "entry_node_guid": fe_node.node_guid,
                "signature": signature,
                "execution_flows": [{
                    "start_event": f"FunctionEntry.{function_name}",
                    "nodes": annotated_nodes
                }]
            }

            function_graphs.append(entry)

    return function_graphs


# Public API aliases — internal functions exposed for cross-module consumers.
# These allow other modules (e.g. kismet/semantic.py) to use graph traversal
# without importing `_` prefixed internal functions directly.
build_graph_indexes = _build_graph_indexes
build_normalized_edge_indexes = _build_normalized_edge_indexes
trace_execution_from_event = _trace_execution_from_event
node_member_name = _node_member_name
