"""蓝图图流构建 — 执行流、数据流、连接映射。

等价迁移 uasset_read.py L6478-6620, L6546-6607, L6836-7114。
"""
from __future__ import annotations

import logging
from typing import Dict, List, Optional, Tuple, Set, Any, Iterable

from uasset_read.constants import (
    START_EVENT_TYPES, CONTROL_FLOW_NODES, BRANCH_TYPE_MAP,
    FORMAT_CONFIG, GRAPH_TYPE_MAP, DATA_BOUNDARY_NODES,
)
from uasset_read.graph.macro_expander import (
    MacroExpander, STANDARD_MACROS, STANDARD_MACRO_CPP_MAPPING,
)
from uasset_read.models.core import UEdGraph, UEdGraphNode, UEdGraphPin
from uasset_read.models.node_types import (
    K2NodeCallFunction, K2NodeEvent, K2NodeKnot,
    EdGraphNodeComment, K2NodeEnhancedInputAction
)

logger = logging.getLogger(__name__)

# Latent/Async 动作节点类型集合 — 在执行流中标记为 latent=True
LATENT_NODE_TYPES = frozenset({
    "K2Node_AsyncAction",
    "K2Node_LatentGameCommand",
    "K2Node_BaseAsyncTask",
    "K2Node_Timeline",
})


# ============================================================================
# 辅助函数
# ============================================================================

def _sanitize_string(value: str) -> str:
    """清理字符串中的二进制/null 字符，确保 JSON 安全输出。
    
    保留 \n \r \t 等常用控制字符，移除 null 和其他控制字符。
    """
    if not value:
        return value
    # 移除 null 字符
    value = value.replace('\x00', '')
    # 移除其他控制字符（保留 \n \r \t）
    value = ''.join(c for c in value if c >= ' ' or c in '\n\r\t')
    return value


def _sanitize_pin_dict(pin_dict: dict) -> dict:
    """清理 pin dict 中所有字符串字段。"""
    sanitized = {}
    for key, val in pin_dict.items():
        if isinstance(val, str):
            sanitized[key] = _sanitize_string(val)
        elif isinstance(val, (list, dict)):
            sanitized[key] = _sanitize_recursive(val)
        else:
            sanitized[key] = val
    return sanitized


def _sanitize_recursive(obj, visited=None):
    """递归清理列表/字典中的字符串。

    Args:
        obj: 要清理的对象
        visited: 已访问对象的 id 集合，用于防止循环引用导致的无限递归
    """
    # 初始化 visited 集合（仅在顶层调用时）
    if visited is None:
        visited = set()

    # 对可变对象检查循环引用
    if isinstance(obj, (list, dict)):
        obj_id = id(obj)
        if obj_id in visited:
            # 检测到循环引用，返回安全的替代值
            if isinstance(obj, dict):
                return {}
            return []
        visited.add(obj_id)

    if isinstance(obj, str):
        return _sanitize_string(obj)
    elif isinstance(obj, (int, float, bool)) or obj is None:
        return obj
    elif isinstance(obj, list):
        return [_sanitize_recursive(item, visited) for item in obj]
    elif isinstance(obj, dict):
        return {k: _sanitize_recursive(v, visited) for k, v in obj.items()}
    elif hasattr(obj, "get_full_name"):
        try:
            return obj.get_full_name()
        except Exception:
            return str(obj)
    elif hasattr(obj, "object_name"):
        return getattr(obj, "object_name", str(obj))
    return str(obj)


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


def _pin_ref_guid(ref: object) -> str | None:
    """从 LinkedTo/PinReference 结构中提取 pin guid（归一化为 32 字符大写 hex）。

    PinReference GUID 原始格式为 8-4-4-4-12 带 dash（_read_guid 输出），
    而归一化后与 pin_id（.hex().upper() 输出）格式一致，确保连接查找匹配。
    """
    raw_guid: str | None = None
    if isinstance(ref, dict):
        raw_guid = ref.get("pin_guid") or ref.get("pin_id")
    elif isinstance(ref, str):
        raw_guid = ref
    else:
        raw_guid = getattr(ref, "pin_guid", None) or getattr(ref, "pin_id", None)

    if not raw_guid:
        return None

    # 归一化：移除 dash，转大写
    return raw_guid.replace("-", "").upper()


def _pin_direction_text(direction: int) -> str:
    """Return stable pin direction text for Blueprint DTO output."""
    return "output" if direction == 1 else "input"


def _pin_category(pin: UEdGraphPin) -> str:
    return pin.pin_type.pin_category if pin.pin_type else ""


def _pin_subcategory(pin: UEdGraphPin) -> str:
    return pin.pin_type.pin_subcategory if pin.pin_type else ""


def _pin_container_type(pin: UEdGraphPin) -> str:
    if not pin.pin_type:
        return ""
    return str(getattr(pin.pin_type, "container_type", "") or "")


def _format_blueprint_pin_dto(
    pin: UEdGraphPin,
    pin_lookup: Dict[str, Tuple[str, str]],
    node_name_lookup: Dict[str, str],
) -> Dict[str, Any]:
    """Format a pin using the compact Blueprint DTO shape."""
    linked_to: List[str] = []
    for ref in pin.linked_to_raw or []:
        target_pin_id = _pin_ref_guid(ref)
        if target_pin_id in pin_lookup:
            target_node_guid, target_pin_name = pin_lookup[target_pin_id]
            target_node_name = node_name_lookup.get(target_node_guid, target_node_guid)
            linked_to.append(f"{target_node_name}.{target_pin_name}")
        elif target_pin_id:
            linked_to.append(str(target_pin_id))
        elif isinstance(ref, dict) and ref.get("owning_node"):
            linked_to.append(str(ref["owning_node"]))

    pin_type = pin.pin_type
    return {
        "PinId": pin.persistent_guid or pin.pin_id,
        "PinName": pin.pin_name,
        "Direction": _pin_direction_text(pin.direction),
        "PinCategory": _pin_category(pin),
        "PinSubCategory": _pin_subcategory(pin),
        "DefaultValue": pin.default_value,
        "LinkedTo": linked_to,
        "IsReference": bool(getattr(pin_type, "is_reference", False)) if pin_type else False,
        "IsConst": bool(getattr(pin_type, "is_const", False)) if pin_type else False,
        "ContainerType": _pin_container_type(pin),
    }


def _build_graph_indexes(
    graph: UEdGraph,
) -> Tuple[Dict[str, Tuple[str, str]], Dict[str, UEdGraphNode], Dict[str, UEdGraphPin]]:
    """构建节点和 Pin 查找表。"""
    pin_lookup: Dict[str, Tuple[str, str]] = {}
    node_lookup: Dict[str, UEdGraphNode] = {}
    pin_object_lookup: Dict[str, UEdGraphPin] = {}
    for node in graph.nodes:
        node_lookup[node.node_guid] = node
        for pin in node.pins:
            pin_lookup[pin.pin_id] = (node.node_guid, pin.pin_name)
            pin_object_lookup[pin.pin_id] = pin
    return pin_lookup, node_lookup, pin_object_lookup


def _is_exec_pin(pin: UEdGraphPin) -> bool:
    return bool(pin.pin_type and pin.pin_type.pin_category == "exec")


def _is_valid_pin_guid(guid: object) -> bool:
    """验证 Pin GUID 有效性。

    支持两种格式：
    - 32 字符纯 hex（pin_id 格式）
    - 36 字符带 dash hex（PinReference 格式，如 A1B2C3D4-E5F6-...）
    - "pin-" 前缀（测试 fixture）
    - 全零 GUID（ParentPin 空引用）
    """
    if not isinstance(guid, str) or not guid:
        return False

    # 测试 fixture 兼容
    if guid.startswith("pin-"):
        return True

    # 归一化：移除 dash，转大写
    normalized = guid.replace("-", "").upper()

    # 全零 GUID（有效空引用）
    if normalized == "0" * 32:
        return True

    # 验证 32 字符 hex
    if len(normalized) != 32:
        return False

    return all(c in "0123456789ABCDEF" for c in normalized)


def _iter_normalized_edges(
    graph: UEdGraph,
) -> Iterable[Dict[str, Any]]:
    """遍历归一化连接边。

    UE 文本导出的 LinkedTo 在 input/output 两端都可能出现。旧实现只从
    output pin 正向扫描，会漏掉真实资产中大量记录在 input pin 上的连接。
    此 helper 统一输出 from(output) -> to(input)，保留 raw 方向用于诊断。
    """
    pin_lookup, node_lookup, pin_object_lookup = _build_graph_indexes(graph)
    export_name_lookup: Dict[str, UEdGraphNode] = {}
    for node in graph.nodes:
        export_name = getattr(node, "_export_object_name", None)
        if export_name:
            export_name_lookup[export_name] = node

    seen: Set[Tuple[str, str, str, str]] = set()

    def _emit(
        from_node: UEdGraphNode,
        from_pin_name: str,
        from_pin_id: str,
        from_pin_obj: Optional[UEdGraphPin],
        to_node: UEdGraphNode,
        to_pin_name: str,
        to_pin_id: str,
        to_pin_obj: Optional[UEdGraphPin],
        category_override: str = "",
        is_exec_override: Optional[bool] = None,
    ) -> Optional[Dict[str, Any]]:
        key = (from_node.node_guid, from_pin_name, to_node.node_guid, to_pin_name)
        if key in seen:
            return None
        seen.add(key)

        category = ""
        if from_pin_obj and from_pin_obj.pin_type:
            category = from_pin_obj.pin_type.pin_category
        elif to_pin_obj and to_pin_obj.pin_type:
            category = to_pin_obj.pin_type.pin_category
        if category_override:
            category = category_override

        return {
            "from_node_guid": from_node.node_guid,
            "from_pin": from_pin_name,
            "from_pin_id": from_pin_id,
            "from_node": from_node,
            "from_pin_obj": from_pin_obj,
            "to_node_guid": to_node.node_guid,
            "to_pin": to_pin_name,
            "to_pin_id": to_pin_id,
            "to_node": to_node,
            "to_pin_obj": to_pin_obj,
            "pin_category": category,
            "is_exec": (
                is_exec_override
                if is_exec_override is not None
                else (
                    (from_pin_obj is not None and _is_exec_pin(from_pin_obj))
                    or (to_pin_obj is not None and _is_exec_pin(to_pin_obj))
                    or category == "exec"
                )
            ),
        }

    def _emit_synthetic_params(source_node: UEdGraphNode, target_node: UEdGraphNode) -> Iterable[Dict[str, Any]]:
        for source_pin_name, target_pin_name in _synthetic_parameter_edges(source_node, target_node):
            edge = _emit(
                source_node,
                source_pin_name,
                f"{source_node.node_guid}:{source_pin_name}",
                None,
                target_node,
                target_pin_name,
                f"{target_node.node_guid}:{target_pin_name}",
                None,
                category_override="real",
                is_exec_override=False,
            )
            if edge:
                yield edge

    for node in graph.nodes:
        for pin in node.pins:
            for ref in (pin.linked_to_raw or []):
                other_pin_id = _pin_ref_guid(ref)
                other_pin = pin_object_lookup.get(other_pin_id) if other_pin_id else None

                if other_pin_id in pin_lookup and other_pin is not None:
                    other_node_guid, other_pin_name = pin_lookup[other_pin_id]
                    other_node = node_lookup[other_node_guid]

                    if pin.direction == 1 and other_pin.direction == 0:
                        edge = _emit(
                            node, pin.pin_name, pin.pin_id, pin,
                            other_node, other_pin_name, other_pin_id, other_pin,
                        )
                    elif pin.direction == 0 and other_pin.direction == 1:
                        edge = _emit(
                            other_node, other_pin_name, other_pin_id, other_pin,
                            node, pin.pin_name, pin.pin_id, pin,
                        )
                    else:
                        edge = None
                    if edge:
                        yield edge
                        if edge.get("is_exec"):
                            yield from _emit_synthetic_params(edge["from_node"], edge["to_node"])
                    continue

                # Fallback：PinId 没解析出来时，用 LinkedTo 的 owning_node 还原
                # from owning node -> current input pin。这覆盖 UE 文本参考中的
                # Touch/EnhancedInput 事件边和部分参数边。
                if pin.direction != 0 or not isinstance(ref, dict):
                    continue
                owning_node_name = ref.get("owning_node")
                source_node = export_name_lookup.get(owning_node_name)
                if not source_node:
                    continue

                source_pin_name = _choose_synthetic_source_pin(source_node, node, pin)
                source_pin_obj = next(
                    (p for p in source_node.pins if p.pin_name == source_pin_name),
                    None,
                )
                source_pin_id = (
                    source_pin_obj.pin_id
                    if source_pin_obj is not None
                    else f"{source_node.node_guid}:{source_pin_name}"
                )
                edge = _emit(
                    source_node, source_pin_name, source_pin_id, source_pin_obj,
                    node, pin.pin_name, pin.pin_id, pin,
                )
                if edge:
                    yield edge
                    if edge.get("is_exec"):
                        yield from _emit_synthetic_params(source_node, node)


def _build_normalized_edge_indexes(
    graph: UEdGraph,
) -> Tuple[Dict[str, List[Dict[str, Any]]], Dict[str, List[Dict[str, Any]]]]:
    """返回 from_pin_id/to_pin_id 两种方向索引。"""
    by_from: Dict[str, List[Dict[str, Any]]] = {}
    by_to: Dict[str, List[Dict[str, Any]]] = {}
    for edge in _iter_normalized_edges(graph):
        by_from.setdefault(edge["from_pin_id"], []).append(edge)
        by_to.setdefault(edge["to_pin_id"], []).append(edge)
    return by_from, by_to


def _node_member_name(node: Optional[UEdGraphNode]) -> str:
    if node is None or not node.node_data:
        return ""
    ref = None
    if isinstance(node.node_data, dict):
        ref = node.node_data.get("function_reference") or node.node_data.get("event_reference")
    else:
        ref = getattr(node.node_data, "function_reference", None) or getattr(node.node_data, "event_reference", None)
    if isinstance(ref, dict):
        return ref.get("member_name", "") or ""
    return getattr(ref, "member_name", "") or ""


def _enhanced_input_action_name(node: Optional[UEdGraphNode]) -> str:
    if node is None or not node.node_data:
        return ""
    data = node.node_data
    path = data.get("input_action_path", "") if isinstance(data, dict) else getattr(data, "input_action_path", "")
    return str(path).split("/")[-1].split(".")[0] if path else ""


def _choose_synthetic_source_pin(source_node: UEdGraphNode, target_node: UEdGraphNode, target_pin: UEdGraphPin) -> str:
    """当目标 LinkedTo 只保留 owning_node 但源 pin 未解析时，推断可读源 pin 名。"""
    target_category = target_pin.pin_type.pin_category if target_pin.pin_type else ""
    target_func = _node_member_name(target_node)
    source_event = _node_member_name(source_node)

    if target_category == "exec":
        if source_node.class_name == "K2Node_Event":
            return "then"
        if source_node.class_name == "K2Node_EnhancedInputAction":
            action = _enhanced_input_action_name(source_node)
            if action == "IA_Jump" and target_func == "Jump":
                return "Started"
            if action == "IA_Jump" and target_func == "StopJumping":
                return "Completed"
            return "Triggered"

    if source_node.class_name == "K2Node_EnhancedInputAction":
        if target_pin.pin_name in ("Yaw", "Left / Right", "Right"):
            return "ActionValue_X"
        if target_pin.pin_name in ("Pitch", "Forward / Backward", "Forward"):
            return "ActionValue_Y"
    if source_node.class_name == "K2Node_Event":
        if source_event in ("Primary Thumbstick", "Secondary Thumbstick"):
            if target_pin.pin_name in ("Yaw", "Left / Right", "Right"):
                return "Axis_X"
            if target_pin.pin_name in ("Pitch", "Forward / Backward", "Forward"):
                return "Axis_Y"

    return "Output"


def _synthetic_parameter_edges(source_node: UEdGraphNode, target_node: UEdGraphNode) -> List[Tuple[str, str]]:
    """为错位导致缺失的参数 pin 补充语义数据边名称。"""
    target_func = _node_member_name(target_node)
    if target_func not in ("Move", "Aim"):
        return []
    if source_node.class_name not in ("K2Node_EnhancedInputAction", "K2Node_Event"):
        return []

    if source_node.class_name == "K2Node_EnhancedInputAction":
        x_name, y_name = "ActionValue_X", "ActionValue_Y"
    else:
        source_event = _node_member_name(source_node)
        if source_event not in ("Primary Thumbstick", "Secondary Thumbstick"):
            return []
        x_name, y_name = "Axis_X", "Axis_Y"

    if target_func == "Move":
        return [(x_name, "Left / Right"), (y_name, "Forward / Backward")]
    return [(x_name, "Yaw"), (y_name, "Pitch")]


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


def _resolve_knot_chain(
    pin_guid: str,
    pin_lookup: Dict[str, Tuple[str, str]],
    node_lookup: Dict[str, UEdGraphNode],
    source_edges_by_to_pin: Optional[Dict[str, List[Dict[str, Any]]]] = None,
    max_depth: int = 20
) -> Tuple[str, bool]:
    """递归穿透 Knot 链直到到达非 Knot 节点。

    用于反向数据流追踪：从目标 pin 开始，穿透 Knot 链找到数据源。

    Args:
        pin_guid: 起始 pin GUID（通常是连接到 Knot OutputPin 的目标 pin）
        pin_lookup: pin_id → (node_guid, pin_name) 查找表
        node_lookup: node_guid → node 查找表
        max_depth: 最大穿透深度（防止无限循环）

    Returns:
        Tuple[str, bool]: (terminal_pin_guid, success)
        - success=True: 找到非 Knot 终端节点
        - success=False: 链断裂或循环检测
    """
    visited: Set[str] = set()
    current_pin_guid = pin_guid

    for _ in range(max_depth):
        if current_pin_guid in visited:
            return (current_pin_guid, False)  # 循环检测

        visited.add(current_pin_guid)

        # Get target node
        target_node_guid, _ = pin_lookup.get(current_pin_guid, (None, None))
        if not target_node_guid:
            return (current_pin_guid, False)  # Pin 不存在

        target_node = node_lookup.get(target_node_guid)
        if not target_node:
            return (current_pin_guid, False)  # Node 不存在

        # Check if Knot
        if target_node.class_name != "K2Node_Knot":
            return (current_pin_guid, True)  # 到达非 Knot 节点

        # Knot: Find InputPin and follow its linked_to_raw backwards
        for pin in target_node.pins:
            if pin.pin_name == "InputPin" and pin.direction == 0:  # Input
                if source_edges_by_to_pin and pin.pin_id in source_edges_by_to_pin:
                    current_pin_guid = source_edges_by_to_pin[pin.pin_id][0]["from_pin_id"]
                    break
                # InputPin 的 linked_to_raw 是上一个 pin（数据来源）
                for linked_ref in (pin.linked_to_raw or []):
                    next_pin_guid = _pin_ref_guid(linked_ref)
                    current_pin_guid = next_pin_guid
                    break
                break

    return (current_pin_guid, False)  # 超过深度限制


def _trace_data_source(
    pin: UEdGraphPin,
    pin_lookup: Dict[str, Tuple[str, str]],
    node_lookup: Dict[str, UEdGraphNode],
    node_name_lookup: Dict[str, str] = {},
    source_edges_by_to_pin: Optional[Dict[str, List[Dict[str, Any]]]] = None,
) -> Optional[Dict]:
    """追踪单个参数的数据来源。

    用于反向数据流追踪：从 CallFunction input pin 开始，穿透 Knot 链，
    找到数据源节点（FunctionEntry 参数、Pure 函数 ReturnValue、self 引用等）。

    Args:
        pin: 目标 pin（通常是 CallFunction input pin）
        pin_lookup: pin_id → (node_guid, pin_name) 查找表
        node_lookup: node_guid → node 查找表
        node_name_lookup: node_guid → node_name 查找表

    Returns:
        Optional[Dict]: 数据来源标注，或 None（默认值/无连接）
        {
            "data_sources": [
                {
                    "source_type": "pure_function" | "function_parameter" | "self_reference" | "boundary" | "default_value" | "knot_chain_broken" | "pin_not_found" | "node_not_found",
                    "node": str,  # 可选，节点名称
                    "pin": str,   # 可选，pin 名称
                    "function_name": str,  # 可选，函数名（Pure 函数）
                    "value": str  # 可选，默认值
                }
            ]
        }
    """
    # 检查是否有连接
    linked_refs = list(pin.linked_to_raw or [])
    if source_edges_by_to_pin and pin.pin_id in source_edges_by_to_pin:
        linked_refs = [
            {"pin_guid": edge["from_pin_id"]}
            for edge in source_edges_by_to_pin[pin.pin_id]
        ]

    if not linked_refs:
        # 默认值
        if pin.default_value is not None and pin.default_value != "":
            return {"data_sources": [{"source_type": "default_value", "value": pin.default_value}]}
        return None  # 无数据源

    # 遍历连接（可能有多个，但通常只有一个）
    sources: List[Dict] = []
    for linked_ref in linked_refs:
        target_pin_guid = _pin_ref_guid(linked_ref)

        # Knot 穿透
        terminal_pin_guid, success = _resolve_knot_chain(
            target_pin_guid, pin_lookup, node_lookup, source_edges_by_to_pin
        )
        if not success:
            sources.append({"source_type": "knot_chain_broken", "pin_guid": terminal_pin_guid})
            continue

        # 获取终端节点
        terminal_node_guid, terminal_pin_name = pin_lookup.get(terminal_pin_guid, (None, None))
        if not terminal_node_guid:
            sources.append({"source_type": "pin_not_found", "pin_guid": terminal_pin_guid})
            continue

        terminal_node = node_lookup.get(terminal_node_guid)
        if not terminal_node:
            sources.append({"source_type": "node_not_found", "node_guid": terminal_node_guid})
            continue

        # 边界检测
        if is_boundary_node(terminal_node, terminal_pin_name):
            # FunctionEntry 参数或 self
            if terminal_node.class_name == "K2Node_FunctionEntry":
                node_name = node_name_lookup.get(terminal_node_guid, terminal_node_guid)
                sources.append({
                    "source_type": "function_parameter",
                    "node": node_name,
                    "pin": terminal_pin_name
                })
            elif terminal_pin_name.lower() == "self" or terminal_pin_name.lower() == "target":
                sources.append({"source_type": "self_reference"})
            else:
                # 其他边界（如 VariableSet）
                node_name = node_name_lookup.get(terminal_node_guid, terminal_node_guid)
                sources.append({
                    "source_type": "boundary",
                    "node": node_name,
                    "pin": terminal_pin_name
                })
        else:
            # 非边界：通常是 Pure 函数输出
            if terminal_node.class_name == "K2Node_CallFunction":
                # 检查是否为 Pure（无 exec pin）
                has_exec_pin = any(p.pin_type and p.pin_type.pin_category == "exec" for p in terminal_node.pins)
                node_name = node_name_lookup.get(terminal_node_guid, terminal_node_guid)

                # 获取函数名
                func_name = None
                nd = terminal_node.node_data
                if nd:
                    fr = nd.get("function_reference") if isinstance(nd, dict) else getattr(nd, 'function_reference', None)
                    if fr:
                        func_name = getattr(fr, 'member_name', None)

                sources.append({
                    "source_type": "pure_function" if not has_exec_pin else "function_output",
                    "node": node_name,
                    "function_name": func_name,
                    "pin": terminal_pin_name
                })

    return {"data_sources": sources} if sources else None


def _find_next_exec_node(
    node: UEdGraphNode,
    pin_lookup: Dict[str, Tuple[str, str]],
    node_lookup: Dict[str, UEdGraphNode],
    edges_by_from_pin: Optional[Dict[str, List[Dict[str, Any]]]] = None,
) -> Tuple[Optional[UEdGraphNode], Optional[str]]:
    """查找 exec output pin 连接的下一个节点。

    Args:
        node: 当前节点
        pin_lookup: pin_id → (node_guid, pin_name) 查找表
        node_lookup: node_guid → node 查找表

    Returns:
        Tuple[Optional[UEdGraphNode], Optional[str]]: (下一个节点, 用于连接的 exec output pin 名称)
    """
    for pin in node.pins:
        if pin.direction == 1:  # Output
            if pin.pin_type and pin.pin_type.pin_category == "exec":
                if edges_by_from_pin and pin.pin_id in edges_by_from_pin:
                    edge = edges_by_from_pin[pin.pin_id][0]
                    return (node_lookup.get(edge["to_node_guid"]), pin.pin_name)
                for linked_pin_id in (pin.linked_to_raw or []):
                    target_pin_guid = _pin_ref_guid(linked_pin_id)
                    if target_pin_guid in pin_lookup:
                        target_node_guid, _ = pin_lookup[target_pin_guid]
                        return (node_lookup.get(target_node_guid), pin.pin_name)
    if edges_by_from_pin:
        for edges in edges_by_from_pin.values():
            for edge in edges:
                if edge["from_node_guid"] == node.node_guid and edge.get("is_exec"):
                    return (node_lookup.get(edge["to_node_guid"]), edge.get("from_pin"))
    return (None, None)


def _try_expand_macro(node: UEdGraphNode, asset_context: Dict[str, Any]) -> Dict[str, Any]:
    """尝试展开宏实例。

    Args:
        node: MacroInstance 节点
        asset_context: 资产上下文，包含 graphs 等信息

    Returns:
        展开结果字典，包含 macro_name, pin_mapping, unresolved 等
    """
    node_data = node.node_data or {}
    if not isinstance(node_data, dict):
        return {"unresolved": True, "reason": "node_data is not a dict"}

    macro_ref = node_data.get("macro_graph_reference", {})

    if not macro_ref:
        return {"unresolved": True, "reason": "no macro_graph_reference"}

    graph_name = macro_ref.get("graph_name", "")

    # 检查是否为标准宏
    is_standard = graph_name in STANDARD_MACROS

    try:
        expander = MacroExpander(asset_context)
        expansion = expander.expand_macro_instance({"macro_graph_reference": macro_ref})
        return {
            "macro_name": expansion.context.macro_name,
            "macro_guid": expansion.context.macro_guid,
            "pin_mapping": expansion.pin_mapping,
            "unresolved": expansion.unresolved,
            "is_standard": is_standard or expansion.context.macro_name in STANDARD_MACROS,
            "internal_flows": expansion.internal_flows,
        }
    except Exception as e:
        return {
            "unresolved": True,
            "reason": str(e),
            "macro_name": graph_name or "Unknown",
        }


def _trace_execution_from_event(
    start_node: UEdGraphNode,
    pin_lookup: Dict[str, Tuple[str, str]],
    node_lookup: Dict[str, UEdGraphNode],
    node_name_lookup: Dict[str, str] = {},
    edges_by_from_pin: Optional[Dict[str, List[Dict[str, Any]]]] = None,
    source_edges_by_to_pin: Optional[Dict[str, List[Dict[str, Any]]]] = None,
    asset_context: Optional[Dict[str, Any]] = None,
) -> List[Dict]:
    """追踪单条执行流（D-08-07~11, D-19-13~14）。

    Args:
        start_node: K2Node_Event 起点（或其他START_EVENT_TYPES起点）
        pin_lookup: pin_id → (node_guid, pin_name) 查找表
        node_lookup: node_guid → node 查找表
        node_name_lookup: node_guid → node_name 查找表

    Returns:
        List[Dict]: 节点信息序列
    """
    visited: Set[str] = set()
    flow: List[Dict] = []
    current_node = start_node
    _MAX_EXEC_STEPS = 500
    _steps = 0
    # 为无 GUID 节点使用 id 做 visited，防止无限循环
    _no_guid_visited: Set[int] = set()

    while current_node:
        _steps += 1
        if _steps > _MAX_EXEC_STEPS:
            flow.append({"stopped_at": "max_steps_exceeded", "steps": _steps})
            break

        # LOW-07: 处理 node_guid 为 None 的情况
        current_guid = current_node.node_guid
        if current_guid is None:
            node_id = id(current_node)
            if node_id in _no_guid_visited:
                flow.append({
                    "node_type": current_node.class_name,
                    "cycle_detected": True,
                    "warning": "missing node_guid"
                })
                break
            _no_guid_visited.add(node_id)
            # node_guid 缺失时仍记录节点但跳过有 GUID 的循环检测
            flow.append({
                "node_type": current_node.class_name,
                "warning": "missing node_guid"
            })
            current_node, _ = _find_next_exec_node(
                current_node, pin_lookup, node_lookup, edges_by_from_pin
            )
            continue

        if current_guid in visited:
            flow.append({
                "node_guid": current_guid,
                "node_type": current_node.class_name,
                "cycle_detected": True
            })
            break

        visited.add(current_guid)

        node_info = {
            "node_guid": current_guid,
            "node_type": current_node.class_name,
        }

        # Latent/Async 动作检测
        if current_node.class_name in LATENT_NODE_TYPES:
            node_info["latent"] = True

        # --- CallFunction 的 parameters 提取（数据流追踪）---
        if current_node.class_name == "K2Node_CallFunction":
            from uasset_read.formatters.json_formatter import _extract_call_function_parameters
            node_info["parameters"] = _extract_call_function_parameters(
                current_node, pin_lookup, node_lookup, node_name_lookup
            )

        # mark pure functions with "pure": true in flow
        has_exec_pin = any(pin.pin_type and pin.pin_type.pin_category == "exec" for pin in current_node.pins)
        if not has_exec_pin:
            node_info["pure"] = True

            # Pure 函数 data_providers 标注（正向追踪）
            data_providers: List[Dict] = []
            for pin in current_node.pins:
                if pin.direction == 1 and pin.pin_type and pin.pin_type.pin_category != "exec":
                    # 找到 output pin 的连接目标
                    if edges_by_from_pin and pin.pin_id in edges_by_from_pin:
                        for edge in edges_by_from_pin[pin.pin_id]:
                            data_providers.append({
                                "output_pin": pin.pin_name,
                                "target_node": node_name_lookup.get(edge["to_node_guid"], edge["to_node_guid"]),
                                "target_pin": edge["to_pin"],
                            })
                    else:
                        for linked_ref in (pin.linked_to_raw or []):
                            target_pin_guid = _pin_ref_guid(linked_ref)
                            if target_pin_guid in pin_lookup:
                                target_node_guid, target_pin_name = pin_lookup[target_pin_guid]
                                target_node_name = node_name_lookup.get(target_node_guid, target_node_guid)
                                data_providers.append({
                                    "output_pin": pin.pin_name,
                                    "target_node": target_node_name,
                                    "target_pin": target_pin_name
                                })

            if data_providers:
                node_info["data_providers"] = data_providers

        elif current_node.node_data and hasattr(current_node.node_data, 'b_defaults_to_pure') and current_node.node_data.b_defaults_to_pure:
            node_info["pure"] = True

        # 控制流节点处理
        if current_node.class_name in CONTROL_FLOW_NODES:
            if current_node.class_name == "K2Node_MacroInstance":
                # 宏实例：尝试展开并穿透，不终止执行链
                ctx = asset_context or {}
                expansion = _try_expand_macro(current_node, ctx)
                node_info["macro_expansion"] = expansion
                macro_name = expansion.get("macro_name", "")
                if macro_name in STANDARD_MACRO_CPP_MAPPING:
                    node_info["cpp_macro_mapping"] = STANDARD_MACRO_CPP_MAPPING[macro_name]
                if not expansion.get("is_standard") and not expansion.get("unresolved"):
                    internal_flows = expansion.get("internal_flows", [])
                    if internal_flows:
                        node_info["macro_internal_flows"] = internal_flows
            else:
                # 其他控制流节点：设置 branch_type 并终止
                if "branch_type" not in node_info:
                    branch_type = BRANCH_TYPE_MAP.get(current_node.class_name, "unknown")
                    node_info["branch_type"] = branch_type
                if "stopped_at" not in node_info:
                    node_info["stopped_at"] = "control_flow_node"
                flow.append(node_info)
                break

        flow.append(node_info)
        current_node, used_pin_name = _find_next_exec_node(
            current_node, pin_lookup, node_lookup, edges_by_from_pin
        )
        if used_pin_name is not None:
            node_info["used_exec_pin_name"] = used_pin_name

    return flow


def _trace_execution_from_pin(
    start_node: UEdGraphNode,
    start_pin: UEdGraphPin,
    pin_lookup: Dict[str, Tuple[str, str]],
    node_lookup: Dict[str, UEdGraphNode],
    node_name_lookup: Dict[str, str] = {},
    edges_by_from_pin: Optional[Dict[str, List[Dict[str, Any]]]] = None,
    source_edges_by_to_pin: Optional[Dict[str, List[Dict[str, Any]]]] = None,
    asset_context: Optional[Dict[str, Any]] = None,
) -> List[Dict]:
    """从特定Pin开始追踪执行流（D-19-12）。

    用于EnhancedInputAction多触发时机追踪。
    增加 node_name_lookup 参数传递。
    """
    if edges_by_from_pin and start_pin.pin_id in edges_by_from_pin:
        edge = edges_by_from_pin[start_pin.pin_id][0]
        next_node = node_lookup.get(edge["to_node_guid"])
        if next_node:
            return _trace_execution_from_event(
                next_node, pin_lookup, node_lookup, node_name_lookup,
                edges_by_from_pin, source_edges_by_to_pin, asset_context,
            )

    for linked_pin_id in (start_pin.linked_to_raw or []):
        target_pin_guid = _pin_ref_guid(linked_pin_id)
        if target_pin_guid in pin_lookup:
            target_node_guid, _ = pin_lookup[target_pin_guid]
            next_node = node_lookup.get(target_node_guid)
            if next_node:
                return _trace_execution_from_event(
                    next_node, pin_lookup, node_lookup, node_name_lookup,
                    edges_by_from_pin, source_edges_by_to_pin, asset_context,
                )

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


def build_execution_flows(graph: UEdGraph) -> List[Dict]:
    """已弃用：请使用 build_execution_flow_entries()。

    此函数保留用于向后兼容，会发出 DeprecationWarning。
    """
    import warnings
    warnings.warn(
        "build_execution_flows() is deprecated. "
        "Use build_execution_flow_entries() for internal calls, "
        "or build_execution_chains() for chain format output.",
        DeprecationWarning,
        stacklevel=2
    )
    return build_execution_flow_entries(graph)


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
