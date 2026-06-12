"""蓝图翻译参考文本格式化器。

输出面向 C++ 翻译理解的紧凑文本，而不是 UE 原始复制文本。
保留节点语义、位置、GUID、关键引脚和连接关系，尽量去掉序列化噪声。
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Dict, List

if TYPE_CHECKING:
    from uasset_read.models.result import ParseResult
    from uasset_read.models.core import UEdGraph, UEdGraphNode, UEdGraphPin


_CLASS_FRIENDLY_NAMES = {
    "K2Node_CallFunction": "CallFunction",
    "K2Node_Event": "Event",
    "K2Node_EnhancedInputAction": "EnhancedInput",
    "K2Node_FunctionEntry": "FunctionEntry",
    "K2Node_Knot": "Reroute",
    "EdGraphNode_Comment": "Comment",
}

def format_blueprint_translation_text(result: "ParseResult") -> str:
    """将解析结果格式化为紧凑的蓝图翻译参考文本。"""
    lines: List[str] = []

    package_name = result.summary.package_name if result.summary else "Unknown"
    asset_name = package_name.split("/")[-1] if package_name else "Unknown"
    lines.append(f"Asset: {asset_name}")
    if result.blueprint and result.blueprint.parent_class:
        lines.append(f"ParentClass: {result.blueprint.parent_class}")
    if result.blueprint and result.blueprint.functions:
        func_names = ", ".join(
            func.name for func in result.blueprint.functions if func.name
        )
        if func_names:
            lines.append(f"Functions: {func_names}")
    if result.blueprint and result.blueprint.events:
        event_names = ", ".join(
            event.name for event in result.blueprint.events if event.name
        )
        if event_names:
            lines.append(f"Events: {event_names}")

    if not result.graphs:
        lines.append("Graphs: (none)")
        return "\n".join(lines)

    lines.append("")
    for graph_idx, graph in enumerate(result.graphs):
        if graph_idx > 0:
            lines.append("")
        lines.extend(_format_graph(graph, package_name))

    return "\n".join(lines).rstrip()


def _format_graph(graph: "UEdGraph", package_name: str) -> List[str]:
    lines: List[str] = []
    graph_type = graph.graph_class or "Unknown"
    lines.append(f"Graph: {graph.graph_name} ({graph_type})")
    lines.append(f"  Nodes: {len(graph.nodes)}")

    node_name_lookup = _build_node_name_lookup(graph)
    pin_lookup = _build_pin_lookup(graph, node_name_lookup)

    for idx, node in enumerate(graph.nodes):
        if isinstance(node.node_data, dict) and node.node_data.get("_parse_error"):
            continue
        lines.extend(_format_node(graph, node, idx, package_name, node_name_lookup, pin_lookup))

    return lines


def _build_node_name_lookup(graph: "UEdGraph") -> Dict[str, str]:
    lookup: Dict[str, str] = {}
    for idx, node in enumerate(graph.nodes):
        if node.node_guid:
            lookup[node.node_guid] = f"{node.class_name}_{idx}"
    return lookup


def _build_pin_lookup(
    graph: "UEdGraph",
    node_name_lookup: Dict[str, str],
) -> Dict[str, Dict[str, str]]:
    """pin_id -> {node_name, pin_name}."""
    lookup: Dict[str, Dict[str, str]] = {}
    for node in graph.nodes:
        node_name = node_name_lookup.get(node.node_guid, node.class_name)
        for pin in node.pins:
            lookup[pin.pin_id] = {
                "node_name": node_name,
                "pin_name": pin.pin_name,
                "node_guid": node.node_guid,
            }
    return lookup


def _format_node(
    graph: "UEdGraph",
    node: "UEdGraphNode",
    idx: int,
    package_name: str,
    node_name_lookup: Dict[str, str],
    pin_lookup: Dict[str, Dict[str, str]],
) -> List[str]:
    lines: List[str] = []
    node_name = node_name_lookup.get(node.node_guid, f"{node.class_name}_{idx}")
    friendly = _CLASS_FRIENDLY_NAMES.get(node.class_name, node.class_name)
    semantic = _node_semantic_name(node)

    header = f"  - {node_name} [{friendly}"
    if semantic and semantic != friendly:
        header += f": {semantic}"
    header += "]"
    lines.append(header)

    lines.append(f"    Pos: ({node.node_pos_x}, {node.node_pos_y})")
    if node.node_guid:
        lines.append(f"    Guid: {node.node_guid}")
    if node.node_comment and node.class_name != "EdGraphNode_Comment":
        lines.append(f"    Comment: {node.node_comment}")

    if node.class_name == "EdGraphNode_Comment":
        comment_text = getattr(node, "node_comment", "")
        if comment_text:
            lines.append(f"    Note: {comment_text}")
        comment_meta = _format_comment_meta(node)
        if comment_meta:
            lines.append(f"    Meta: {comment_meta}")
        return lines

    extra = _format_node_extra(node)
    if extra:
        for item in extra:
            lines.append(f"    {item}")

    relevant_pins = [pin for pin in node.pins if _pin_is_important(pin)]
    if relevant_pins:
        lines.append("    Pins:")
        for pin in relevant_pins:
            lines.append(
                "      - "
                + _format_pin(pin, pin_lookup)
            )

    if node.class_name == "K2Node_Knot":
        knot_line = _format_knot_summary(node, pin_lookup)
        if knot_line:
            lines.append(f"    {knot_line}")

    return lines


def _format_node_extra(node: "UEdGraphNode") -> List[str]:
    data = node.node_data
    if not data:
        return []

    if node.class_name == "K2Node_CallFunction":
        ref = _get_ref(data, "function_reference")
        if ref:
            return [f"Call: {_member_name(ref)}"]

    if node.class_name == "K2Node_Event":
        ref = _get_ref(data, "event_reference")
        if ref:
            return [f"Event: {_member_name(ref)}"]

    if node.class_name == "K2Node_EnhancedInputAction":
        path = _get_value(data, "input_action_path")
        if path:
            return [f"InputAction: {_short_action_name(path)}", f"InputPath: {path}"]

    if node.class_name == "K2Node_FunctionEntry":
        ref = _get_ref(data, "function_reference")
        if ref:
            return [f"Entry: {_member_name(ref)}"]

    return []


def _format_comment_meta(node: "UEdGraphNode") -> str:
    parts: List[str] = []
    width = getattr(node, "node_width", None)
    height = getattr(node, "node_height", None)
    if width is not None and height is not None:
        parts.append(f"size={width}x{height}")
    color = getattr(node, "comment_color", None)
    if color:
        parts.append(
            "color="
            + ",".join(_fmt_float(v) for v in color)
        )
    return "; ".join(parts)


def _format_knot_summary(
    node: "UEdGraphNode",
    pin_lookup: Dict[str, Dict[str, str]],
) -> str:
    input_pin = next((p for p in node.pins if p.direction == 0), None)
    output_pin = next((p for p in node.pins if p.direction == 1), None)
    if not input_pin or not output_pin:
        return ""

    src = _pin_source_text(input_pin, pin_lookup)
    dst = _pin_targets_text(output_pin, pin_lookup)
    if not src and not dst:
        return ""
    return f"Reroute: {src or input_pin.pin_name} -> {dst or output_pin.pin_name}"


def _pin_is_important(pin: "UEdGraphPin") -> bool:
    if pin.linked_to_raw:
        return True
    if pin.sub_pins:
        return True
    if pin.parent_pin:
        return True
    if pin.ref_pass_through:
        return True
    if _is_readable_text(pin.default_value):
        return True
    if _is_readable_text(pin.auto_default_value):
        return True
    if pin.pin_type and pin.pin_type.pin_category == "exec":
        return pin.direction in (0, 1)
    return False


def _format_pin(
    pin: "UEdGraphPin",
    pin_lookup: Dict[str, Dict[str, str]],
) -> str:
    direction = "in" if pin.direction == 0 else "out"
    type_label = _pin_type_label(pin)

    pieces = [f"{direction} {pin.pin_name} [{type_label}]"]

    if _is_readable_text(pin.default_value):
        pieces.append(f"default={_quote(pin.default_value)}")
    if _is_readable_text(pin.auto_default_value) and pin.auto_default_value != pin.default_value:
        pieces.append(f"auto={_quote(pin.auto_default_value)}")

    if pin.linked_to_raw:
        pieces.append(f"links={_pin_targets_text(pin, pin_lookup)}")
    if pin.sub_pins:
        pieces.append(f"subpins={_pin_subpins_text(pin, pin_lookup)}")
    if pin.parent_pin:
        pieces.append(f"parent={_pin_reference_text(pin.parent_pin, pin_lookup)}")
    if pin.ref_pass_through:
        pieces.append(
            f"pass={_pin_reference_text(pin.ref_pass_through, pin_lookup)}"
        )

    return " | ".join(pieces)


def _pin_type_label(pin: "UEdGraphPin") -> str:
    pin_type = pin.pin_type
    if pin_type is None:
        return "unknown"

    category = pin_type.pin_category or "unknown"
    if pin_type.pin_subcategory:
        return f"{category}/{pin_type.pin_subcategory}"
    return category


def _pin_targets_text(
    pin: "UEdGraphPin",
    pin_lookup: Dict[str, Dict[str, str]],
) -> str:
    targets: List[str] = []
    for ref in pin.linked_to_raw or []:
        text = _pin_reference_text(ref, pin_lookup)
        if text:
            targets.append(text)
    return ", ".join(targets)


def _pin_subpins_text(
    pin: "UEdGraphPin",
    pin_lookup: Dict[str, Dict[str, str]],
) -> str:
    targets: List[str] = []
    for ref in pin.sub_pins or []:
        text = _pin_reference_text(ref, pin_lookup)
        if text:
            targets.append(text)
    return ", ".join(targets)


def _pin_source_text(
    pin: "UEdGraphPin",
    pin_lookup: Dict[str, Dict[str, str]],
) -> str:
    if pin.linked_to_raw:
        return _pin_targets_text(pin, pin_lookup)
    if _is_readable_text(pin.default_value):
        return str(pin.default_value)
    return pin.pin_name


def _is_readable_text(value: object) -> bool:
    if not isinstance(value, str) or value == "":
        return False
    if "\x00" in value:
        return False
    control_count = sum(1 for ch in value if ord(ch) < 32 and ch not in "\n\r\t")
    return control_count == 0 and len(value) <= 256


def _pin_reference_text(
    ref: object,
    pin_lookup: Dict[str, Dict[str, str]],
) -> str:
    pin_guid = None
    owning_node = None

    if isinstance(ref, dict):
        pin_guid = ref.get("pin_guid") or ref.get("pin_id")
        owning_node = ref.get("owning_node")
    elif isinstance(ref, str):
        pin_guid = ref
    else:
        pin_guid = getattr(ref, "pin_guid", None) or getattr(ref, "pin_id", None)
        owning_node = getattr(ref, "owning_node", None)

    if pin_guid and pin_guid in pin_lookup:
        target = pin_lookup[pin_guid]
        return f"{target['node_name']}.{target['pin_name']}"

    if owning_node and pin_guid:
        return f"{owning_node}.{pin_guid}"

    if pin_guid:
        return pin_guid

    return ""


def _node_semantic_name(node: "UEdGraphNode") -> str:
    data = node.node_data
    if node.class_name == "K2Node_CallFunction":
        ref = _get_ref(data, "function_reference")
        return _member_name(ref) if ref else ""
    if node.class_name == "K2Node_Event":
        ref = _get_ref(data, "event_reference")
        return _member_name(ref) if ref else ""
    if node.class_name == "K2Node_EnhancedInputAction":
        path = _get_value(data, "input_action_path")
        return _short_action_name(path) if path else ""
    if node.class_name == "K2Node_FunctionEntry":
        ref = _get_ref(data, "function_reference")
        return _member_name(ref) if ref else ""
    if node.class_name == "EdGraphNode_Comment":
        return getattr(node, "node_comment", "") or ""
    if node.class_name == "K2Node_Knot":
        return "Reroute"
    return ""


def _short_action_name(path: object) -> str:
    if not isinstance(path, str) or not path:
        return ""
    tail = path.split("'")[-2] if "'" in path and path.count("'") >= 2 else path
    leaf = tail.split("/")[-1] if "/" in tail else tail
    return leaf.split(".")[0] if "." in leaf else leaf


def _get_ref(data: object, field_name: str) -> object:
    if isinstance(data, dict):
        return data.get(field_name)
    return getattr(data, field_name, None)


def _get_value(data: object, field_name: str) -> object:
    if isinstance(data, dict):
        return data.get(field_name)
    return getattr(data, field_name, None)


def _member_name(ref: object) -> str:
    if ref is None:
        return ""
    if isinstance(ref, dict):
        value = ref.get("member_name", "")
    else:
        value = getattr(ref, "member_name", "")
    if not isinstance(value, str):
        return ""
    return value


def _format_bool(value: object) -> str:
    return "True" if bool(value) else "False"


def _fmt_float(value: object) -> str:
    try:
        number = float(value)
    except Exception:
        return str(value)
    text = f"{number:.6f}".rstrip("0").rstrip(".")
    return text if text else "0"


def _quote(value: object) -> str:
    text = str(value)
    text = text.replace("\\", "\\\\").replace("\"", "\\\"")
    text = text.replace("\r", "\\r").replace("\n", "\\n").replace("\t", "\\t")
    return f"\"{text}\""


__all__ = ["format_blueprint_translation_text"]
