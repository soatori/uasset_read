"""节点格式化与分类 — format_node_dict、事件名提取、图类型判断。"""
from __future__ import annotations

import logging
from typing import Any, Dict, List

from uasset_read.constants import DATA_BOUNDARY_NODES
from uasset_read.models.core import UEdGraph, UEdGraphNode

from ._pin_helpers import _derive_node_name
from ._sanitize import _sanitize_pin_dict, _sanitize_recursive

logger = logging.getLogger(__name__)


def format_node_dict(node: UEdGraphNode, idx: int) -> Dict:
    """格式化单个节点为紧凑的 Blueprint DTO JSON 结构。

    图级语义（connections/execution_chains/data_flows）保留在 graph 对象上，
    节点自身输出使用稳定 DTO 字段，便于跨工具对比。

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
        "pins": [_sanitize_pin_dict(asdict(pin)) for pin in node.pins]  # 添加字符串清理
    }

    if node.class_name == "EdGraphNode_Comment":
        data = node.node_data if isinstance(node.node_data, dict) else {}
        result["comment"] = {
            "text": node.node_comment or "",
            "color": _sanitize_recursive(data.get("comment_color")),
            "width": data.get("node_width"),
            "height": data.get("node_height"),
            "font_size": data.get("font_size"),
            "depth": data.get("comment_depth"),
        }
        result["comment"] = {
            key: value for key, value in result["comment"].items()
            if value is not None
        }

    # CallFunction 节点提取结构化 parameters
    if node.class_name == "K2Node_CallFunction":
        from uasset_read.formatters.json_formatter import _extract_call_function_parameters
        result["parameters"] = _extract_call_function_parameters(node)

    return result


def _comment_enclosed_nodes(comment_node: UEdGraphNode, graph: UEdGraph) -> List[str]:
    """Return export names for nodes inside an EdGraph comment rectangle."""
    data = comment_node.node_data if isinstance(comment_node.node_data, dict) else {}
    width = data.get("node_width") or getattr(comment_node, "node_width", 0) or 0
    height = data.get("node_height") or getattr(comment_node, "node_height", 0) or 0
    if width <= 0 or height <= 0:
        return []

    left = comment_node.node_pos_x
    top = comment_node.node_pos_y
    right = left + width
    bottom = top + height
    enclosed: List[str] = []
    for node in graph.nodes:
        if node is comment_node or node.class_name == "EdGraphNode_Comment":
            continue
        if left <= node.node_pos_x <= right and top <= node.node_pos_y <= bottom:
            enclosed.append(getattr(node, "_export_object_name", "") or node.node_guid)
    return enclosed


def _get_start_event_name(node: UEdGraphNode) -> str:
    """获取起点节点的事件名称（D-19-11）。

    支持4种起点类型：
    - K2Node_Event: event_reference.member_name（dict或dataclass）
    - K2Node_EnhancedInputAction: input_action_path或class_name
    - K2Node_VariableSet: "VariableSet"
    - K2Node_CustomEvent: "CustomEvent.{custom_event_name}"（从 node_data 提取）或回退 "CustomEvent"

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
            return f"Event.{mn.split('/')[-1]}"
        return f"Event.{mn}"

    elif node.class_name == "K2Node_EnhancedInputAction":
        if nd:
            if isinstance(nd, dict):
                path = nd.get("input_action_path", "")
            else:
                path = getattr(nd, 'input_action_path', "")
            if path:
                return f"InputAction.{path.split('/')[-1] if '/' in path else path}"
        return f"InputAction.{node.class_name}"
    elif node.class_name == "K2Node_VariableSet":
        return "VariableSet"
    elif node.class_name == "K2Node_CustomEvent":
        # 从 node_data 提取实际事件名（D-19-11 扩展）
        if nd:
            if isinstance(nd, dict):
                # 直接从 dict 获取，或从 _raw_properties 获取（UE 原始属性名 CustomPropertyName）
                event_name = (
                    nd.get("custom_event_name")
                    or nd.get("CustomEventName")
                    or nd.get("_raw_properties", {}).get("CustomPropertyName")
                )
            else:
                event_name = getattr(nd, 'custom_event_name', None)
            if event_name:
                return f"CustomEvent.{event_name}"
        return "CustomEvent"
    elif node.class_name == "K2Node_FunctionEntry":
        if not nd:
            return node.class_name
        if isinstance(nd, dict):
            fr = nd.get("function_reference")
        else:
            fr = getattr(nd, 'function_reference', None)
        if fr:
            mn = getattr(fr, 'member_name', None) if not isinstance(fr, dict) else fr.get("member_name")
            if mn and mn != "None":
                if '/' in mn:
                    return f"FunctionEntry.{mn.split('/')[-1]}"
                return f"FunctionEntry.{mn}"
        return node.class_name

    return node.class_name


def is_function_graph(graph: UEdGraph) -> bool:
    """判断图是否为函数图（非事件图）。

    组合判断（D-01）：
    1. 含 K2Node_FunctionEntry → Function Graph
    2. 含 K2Node_Event → EventGraph
    3. Fallback: graph_name 模式
    """
    node_types = {n.class_name for n in graph.nodes}
    if "K2Node_FunctionEntry" in node_types:
        return True
    if "K2Node_Event" in node_types:
        return False
    return graph.graph_name.lower() != "eventgraph"


def is_boundary_node(node: UEdGraphNode, pin_name: str) -> bool:
    """判断是否为数据流边界节点。

    Args:
        node: 目标节点
        pin_name: pin 名称（用于 self 检测）

    Returns:
        bool: True=边界（停止追踪），False=继续追踪
    """
    if node.class_name in DATA_BOUNDARY_NODES:
        return True
    # Self 引用（包括 self 和 Target 别名）
    pin_lower = pin_name.lower()
    if pin_lower == "self" or pin_lower == "target":
        return True
    return False
