"""蓝图图构建工具函数。

从 flow_builder.py 提取的共享辅助函数：字符串清理、Pin 引用格式化、
节点索引构建、连接遍历等。
"""

from typing import Dict, List, Optional, Tuple, Set, Any, Iterable

from uasset_read.models.core import UEdGraph, UEdGraphNode, UEdGraphPin
from uasset_read.core.utils import normalize_hex_guid as _normalize_pin_id


# ============================================================================
# 字符串清理
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


# ============================================================================
# Pin 引用与 GUID 工具
# ============================================================================

def _pin_ref_guid(ref: object) -> str | None:
    """从 LinkedTo/PinReference 结构中提取 pin guid（归一化为 32 字符小写 hex）。

    PinReference GUID 原始格式为 8-4-4-4-12 带 dash（_read_guid 输出），
    而归一化后与 pin_id（.hex() 输出）格式一致，确保连接查找匹配。
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

    # 归一化：移除 dash，转小写
    return _normalize_pin_id(raw_guid)


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

    # 归一化：移除 dash，转小写
    normalized = _normalize_pin_id(guid)

    # 全零 GUID（有效空引用）
    if normalized == "0" * 32:
        return True

    # 验证 32 字符 hex（normalized 为小写）
    if len(normalized) != 32:
        return False

    return all(c in "0123456789abcdef" for c in normalized)


# ============================================================================
# 节点名称与索引
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


# ============================================================================
# 图索引构建
# ============================================================================

def _build_graph_indexes(
    graph: UEdGraph,
) -> Tuple[Dict[str, Tuple[str, str]], Dict[str, UEdGraphNode], Dict[str, UEdGraphPin]]:
    """构建节点和 Pin 查找表。

    Pin key 统一归一化为小写 hex（与 _pin_ref_guid 输出格式对齐），
    避免大小写不一致导致的连接查找失败。
    """
    pin_lookup: Dict[str, Tuple[str, str]] = {}
    node_lookup: Dict[str, UEdGraphNode] = {}
    pin_object_lookup: Dict[str, UEdGraphPin] = {}
    for node in graph.nodes:
        node_lookup[node.node_guid] = node
        for pin in node.pins:
            normalized_key = _normalize_pin_id(pin.pin_id)
            pin_lookup[normalized_key] = (node.node_guid, pin.pin_name)
            pin_object_lookup[normalized_key] = pin
    return pin_lookup, node_lookup, pin_object_lookup


# ============================================================================
# 合成边配置（可配置的游戏特定映射表）
# ============================================================================

# 默认禁用游戏特定合成边（需要显式配置才启用）
# 配置格式：
#   EXEC_PIN_MAPPING: { (source_class, action_name): { target_func: exec_pin_name } }
#   PARAM_EDGE_MAPPING: { target_func: [(source_pin, target_pin)] }

EXEC_PIN_MAPPING: Dict[str, Dict[str, str]] = {}
"""EnhancedInputAction/Event → exec pin 名称映射。
默认为空（不启用游戏特定映射）。"""

PARAM_EDGE_MAPPING: Dict[str, List[Tuple[str, str]]] = {}
"""函数参数边映射：{ target_func: [(source_pin_name, target_pin_name)] }。
默认为空（不启用游戏特定映射）。"""


def configure_synthetic_edges(
    exec_mapping: Optional[Dict[str, Dict[str, str]]] = None,
    param_mapping: Optional[Dict[str, List[Tuple[str, str]]]] = None,
) -> None:
    """配置合成边映射表。

    Args:
        exec_mapping: EnhancedInputAction → exec pin 名称映射
        param_mapping: 函数参数边映射
    """
    global EXEC_PIN_MAPPING, PARAM_EDGE_MAPPING
    if exec_mapping is not None:
        EXEC_PIN_MAPPING = exec_mapping
    if param_mapping is not None:
        PARAM_EDGE_MAPPING = param_mapping

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
    """当目标 LinkedTo 只保留 owning_node 但源 pin 未解析时，推断可读源 pin 名。

    使用配置的 EXEC_PIN_MAPPING 查找映射，而非硬编码游戏特定值。
    """
    target_category = target_pin.pin_type.pin_category if target_pin.pin_type else ""
    target_func = _node_member_name(target_node)

    if target_category == "exec":
        if source_node.class_name == "K2Node_Event":
            return "then"
        if source_node.class_name == "K2Node_EnhancedInputAction":
            action = _enhanced_input_action_name(source_node)
            # 查找配置的 exec pin 映射
            mapping_key = f"{source_node.class_name}:{action}"
            if mapping_key in EXEC_PIN_MAPPING:
                pin_map = EXEC_PIN_MAPPING[mapping_key]
                if target_func in pin_map:
                    return pin_map[target_func]
            # 默认行为
            return "Triggered"

    return "Output"


def _synthetic_parameter_edges(source_node: UEdGraphNode, target_node: UEdGraphNode) -> List[Tuple[str, str]]:
    """为错位导致缺失的参数 pin 补充语义数据边名称。

    使用配置的 PARAM_EDGE_MAPPING 查找映射，而非硬编码游戏特定值。
    """
    target_func = _node_member_name(target_node)

    # 查找配置的参数边映射
    if target_func in PARAM_EDGE_MAPPING:
        return PARAM_EDGE_MAPPING[target_func]

    return []


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
                            node, pin.pin_name, _normalize_pin_id(pin.pin_id), pin,
                            other_node, other_pin_name, other_pin_id, other_pin,
                        )
                    elif pin.direction == 0 and other_pin.direction == 1:
                        edge = _emit(
                            other_node, other_pin_name, other_pin_id, other_pin,
                            node, pin.pin_name, _normalize_pin_id(pin.pin_id), pin,
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
                    _normalize_pin_id(source_pin_obj.pin_id)
                    if source_pin_obj is not None
                    else f"{source_node.node_guid}:{source_pin_name}"
                )
                edge = _emit(
                    source_node, source_pin_name, source_pin_id, source_pin_obj,
                    node, pin.pin_name, _normalize_pin_id(pin.pin_id), pin,
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
