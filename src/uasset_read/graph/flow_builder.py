"""蓝图图流构建 — 执行流、数据流、连接映射。

等价迁移 uasset_read.py L6478-6620, L6546-6607, L6836-7114。
"""

import logging
from typing import Dict, List, Optional, Tuple, Set, Any

from uasset_read.constants import (
    START_EVENT_TYPES, CONTROL_FLOW_NODES, BRANCH_TYPE_MAP,
    FORMAT_CONFIG, GRAPH_TYPE_MAP, DATA_BOUNDARY_NODES, UE_NONE_SENTINEL,
)
from uasset_read.graph.macro_expander import (
    MacroExpander, STANDARD_MACROS, STANDARD_MACRO_CPP_MAPPING,
)
from uasset_read.models.core import UEdGraph, UEdGraphNode, UEdGraphPin
from uasset_read.core.utils import normalize_hex_guid as _normalize_pin_id
from uasset_read.graph.graph_utils import (
    _sanitize_pin_dict, _sanitize_recursive,
    _derive_node_name, format_pin_ref, _pin_ref_guid,
    _is_valid_pin_guid,
    _format_blueprint_pin_dto, _build_graph_indexes,
    _iter_normalized_edges, _build_normalized_edge_indexes,
    _node_member_name,
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
# 辅助函数 — 大部分已提取到 graph_utils.py，仅保留 flow_builder 专用函数
# ============================================================================

def _extract_call_function_parameters(
    node: Any,
    pin_lookup: Optional[Dict] = None,
    node_lookup: Optional[Dict] = None,
    node_name_lookup: Optional[Dict] = None
) -> Dict[str, List[Dict]]:
    """从 K2Node_CallFunction 节点的 pins 中提取函数参数。

    过滤 exec pins，将输入/输出参数分离为结构化数组。
    """
    input_params: List[Dict] = []
    output_params: List[Dict] = []

    for pin in node.pins:
        if pin.pin_type and pin.pin_type.pin_category == "exec":
            continue

        param: Dict[str, Any] = {
            "name": pin.pin_name,
            "pin_category": pin.pin_type.pin_category if pin.pin_type else "",
        }
        if pin.pin_type:
            if pin.pin_type.pin_subcategory:
                param["pin_subcategory"] = pin.pin_type.pin_subcategory
            if pin.pin_type.is_reference:
                param["is_reference"] = True
        if pin.default_value is not None and pin.default_value != "":
            param["default_value"] = pin.default_value

        if pin.direction == 0:  # Input
            if pin_lookup and node_lookup and node_name_lookup:
                try:
                    data_source = _trace_data_source(pin, pin_lookup, node_lookup, node_name_lookup)
                    if data_source:
                        param["data_source"] = data_source
                except (KeyError, AttributeError, ValueError) as e:
                    logger.debug("追踪数据源失败: %s", e, exc_info=True)

            input_params.append(param)
        else:  # Output
            output_params.append(param)

    return {"input_params": input_params, "output_params": output_params}

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

        if not mn or mn == UE_NONE_SENTINEL:
            return node.class_name

        # member_name can be a path like "/Game/.../BP_X_37120"
        # or "/Game/Blueprints/BP_Test.ReceiveBeginPlay"
        if '/' in mn:
            last_segment = mn.split('/')[-1]
            # 对象名.成员名 格式：取成员名部分
            if '.' in last_segment:
                last_segment = last_segment.split('.')[-1]
            return f"Event.{last_segment}"
        # 纯成员名中也可能含点号
        if '.' in mn:
            return f"Event.{mn.split('.')[-1]}"
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
            if mn and mn != UE_NONE_SENTINEL:
                if '/' in mn:
                    return f"FunctionEntry.{mn.split('/')[-1]}"
                return f"FunctionEntry.{mn}"
        return node.class_name

    return node.class_name

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
                if source_edges_by_to_pin and _normalize_pin_id(pin.pin_id) in source_edges_by_to_pin:
                    current_pin_guid = source_edges_by_to_pin[_normalize_pin_id(pin.pin_id)][0]["from_pin_id"]
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
    node_name_lookup: Optional[Dict[str, str]] = None,
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
    # 初始化可变默认参数
    if node_name_lookup is None:
        node_name_lookup = {}

    # 检查是否有连接
    linked_refs = list(pin.linked_to_raw or [])
    normalized_pin_id = _normalize_pin_id(pin.pin_id)
    if source_edges_by_to_pin and normalized_pin_id in source_edges_by_to_pin:
        linked_refs = [
            {"pin_guid": edge["from_pin_id"]}
            for edge in source_edges_by_to_pin[normalized_pin_id]
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
                if edges_by_from_pin and _normalize_pin_id(pin.pin_id) in edges_by_from_pin:
                    edge = edges_by_from_pin[_normalize_pin_id(pin.pin_id)][0]
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
    except (KeyError, AttributeError, ValueError, TypeError) as e:
        return {
            "unresolved": True,
            "reason": str(e),
            "macro_name": graph_name or "Unknown",
        }

def _trace_execution_from_event(
    start_node: UEdGraphNode,
    pin_lookup: Dict[str, Tuple[str, str]],
    node_lookup: Dict[str, UEdGraphNode],
    node_name_lookup: Optional[Dict[str, str]] = None,
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
    # 初始化可变默认参数
    if node_name_lookup is None:
        node_name_lookup = {}

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
                    if edges_by_from_pin and _normalize_pin_id(pin.pin_id) in edges_by_from_pin:
                        for edge in edges_by_from_pin[_normalize_pin_id(pin.pin_id)]:
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
    node_name_lookup: Optional[Dict[str, str]] = None,
    edges_by_from_pin: Optional[Dict[str, List[Dict[str, Any]]]] = None,
    source_edges_by_to_pin: Optional[Dict[str, List[Dict[str, Any]]]] = None,
    asset_context: Optional[Dict[str, Any]] = None,
) -> List[Dict]:
    """从特定Pin开始追踪执行流（D-19-12）。

    用于EnhancedInputAction多触发时机追踪。
    增加 node_name_lookup 参数传递。
    """
    # 初始化可变默认参数
    if node_name_lookup is None:
        node_name_lookup = {}

    if edges_by_from_pin and _normalize_pin_id(start_pin.pin_id) in edges_by_from_pin:
        edge = edges_by_from_pin[_normalize_pin_id(start_pin.pin_id)][0]
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
            pin_lookup[_normalize_pin_id(pin.pin_id)] = (node.node_guid, pin.pin_name)

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
            pin_lookup[_normalize_pin_id(pin.pin_id)] = (node.node_guid, pin.pin_name)

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

def _build_graph_dict(graph: UEdGraph) -> Dict[str, Any]:
    """将单个 UEdGraph 转换为 MacroExpander 期望的字典格式。

    包含完整的 pin 数据（pin_id、linked_to_raw、parent_pin）和
    tunnel 节点属性（b_can_have_outputs、b_can_have_inputs、exact_class），
    确保宏展开时 tunnel/pin 数据不丢失。
    """
    direction_map = {0: "EGPD_Input", 1: "EGPD_Output"}

    nodes = []
    for node in graph.nodes:
        nd = node.node_data if isinstance(node.node_data, dict) else {}

        node_dict: Dict[str, Any] = {
            "node_type": node.class_name,
            "node_guid": node.node_guid,
            "pins": [
                {
                    "pin_id": pin.pin_id,
                    "pin_name": pin.pin_name,
                    "direction": direction_map.get(pin.direction, pin.direction),
                    "pin_type": {
                        "pin_category": pin.pin_type.pin_category if pin.pin_type else "",
                        "pin_subcategory": pin.pin_type.pin_subcategory if pin.pin_type else "",
                    } if pin.pin_type else {},
                    "linked_to_raw": pin.linked_to_raw or [],
                    "parent_pin": pin.parent_pin,
                    "default_value": pin.default_value or "",
                }
                for pin in node.pins
            ],
            "macro_graph_reference": nd.get("macro_graph_reference", {}),
        }

        # 提取 Tunnel 节点特有属性（从 _raw_properties 或 node_data）
        if node.class_name == "K2Node_Tunnel":
            raw_props = nd.get("_raw_properties", {})
            node_dict["exact_class"] = "UK2Node_Tunnel"
            node_dict["b_can_have_inputs"] = raw_props.get("bCanHaveInputs", False)
            node_dict["b_can_have_outputs"] = raw_props.get("bCanHaveOutputs", False)

        nodes.append(node_dict)

    return {
        "guid": graph.graph_guid or "",
        "name": graph.graph_name,
        "nodes": nodes,
    }

def _build_asset_context_from_graph(graph: UEdGraph) -> Dict[str, Any]:
    """从 UEdGraph 构建宏展开所需的 asset_context。

    将 UEdGraph 及其所有 subgraph 转换为 MacroExpander 期望的字典格式。
    BFS 遍历 subgraph（带 visited 集合防止循环引用），确保宏图定义
    （包含 Tunnel 节点）被正确收集。
    """
    all_graphs: List[Dict[str, Any]] = []
    visited: set = set()

    # BFS 遍历：顶层图 + 所有子图
    queue = [graph]
    while queue:
        g = queue.pop(0)
        g_id = id(g)
        if g_id in visited:
            continue
        visited.add(g_id)

        all_graphs.append(_build_graph_dict(g))
        for subgraph in getattr(g, "subgraphs", None) or []:
            if id(subgraph) not in visited:
                queue.append(subgraph)

    return {"graphs": all_graphs}

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
            pin_lookup[_normalize_pin_id(pin.pin_id)] = (node.node_guid, pin.pin_name)

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
    """为函数图中错位缺失的参数边补充语义数据流。

    动态检测模式：查找 FunctionEntry 的输出参数与 CallFunction 的
    匹配输入参数之间的连接关系，不再依赖特定模板名称。
    """
    def ref(node: UEdGraphNode, pin_name: str) -> Dict:
        return format_pin_ref(node.node_guid, pin_name, node_name_lookup, mode)

    # 查找 FunctionEntry 节点
    function_entry = None
    for node in graph.nodes:
        if node.class_name == "K2Node_FunctionEntry":
            function_entry = node
            break

    if function_entry is None:
        return []

    # 收集 FunctionEntry 的输出参数 pin 名称
    fe_output_pins = [
        pin.pin_name for pin in function_entry.pins
        if pin.direction == 1  # Output
        and pin.pin_type and pin.pin_type.pin_category != "exec"
    ]

    if not fe_output_pins:
        return []

    # 收集图中所有 CallFunction 节点的输入参数 pin 名称
    nodes_by_func: Dict[str, List[UEdGraphNode]] = {}
    for node in graph.nodes:
        name = _node_member_name(node)
        if name:
            nodes_by_func.setdefault(name, []).append(node)

    flows: List[Dict] = []
    for func_nodes in nodes_by_func.values():
        for node in func_nodes:
            if node.class_name != "K2Node_CallFunction":
                continue
            for pin in node.pins:
                if (
                    pin.direction == 0  # Input
                    and pin.pin_type
                    and pin.pin_type.pin_category != "exec"
                    and pin.pin_name in fe_output_pins
                    and not (pin.linked_to_raw or [])
                ):
                    # 该输入 pin 未连接但与 FunctionEntry 输出参数同名
                    flows.append({
                        "source": ref(function_entry, pin.pin_name),
                        "target": ref(node, pin.pin_name),
                    })

    return flows

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
                pin_lookup[_normalize_pin_id(pin.pin_id)] = (node.node_guid, pin.pin_name)

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
                    if raw_name and raw_name != UE_NONE_SENTINEL:
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
            # 创建辅助函数：提取节点的数据流标注
            def _annotate_node_with_data_flow(  # noqa: B023 - source_edges_by_to_pin and edges_by_from_pin are not loop variables
                node_guid: str,
                node_type: str,
                node_pins: List[UEdGraphPin],
                n_name_lookup: Dict[str, str],
                p_lookup: Dict[str, Tuple[str, str]],
                n_lookup: Dict[str, UEdGraphNode]
            ) -> Dict[str, List[Dict]]:
                """从 data_flows 中提取节点的 data_providers 和 data_sources 标注。"""
                _node_name = n_name_lookup.get(node_guid, node_guid)  # noqa: F841 - extracted for clarity
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
                            source_edges_by_to_pin,  # noqa: B023 - defined outside loop
                        )
                        if data_source:
                            sources.append({
                                "input_pin": pin.pin_name,
                                "data_source": data_source
                            })

                    # Output pin → data_providers（正向追踪）
                    elif pin.direction == 1:
                        # 找到 output pin 的连接目标
                        edges = edges_by_from_pin.get(_normalize_pin_id(pin.pin_id), [])  # noqa: B023 - edges_by_from_pin is not a loop variable
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
