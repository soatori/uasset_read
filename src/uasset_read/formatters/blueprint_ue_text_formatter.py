"""UE 原样风格蓝图节点文本格式化器。

.. deprecated:: 0.4.5
    推荐使用 parse_single(format='blueprint_ue_text') 统一入口，这些函数已转换为带
    DeprecationWarning 的薄包装器，将在未来版本中移除。
"""
from __future__ import annotations

import warnings
from typing import TYPE_CHECKING, Dict, List, Optional

if TYPE_CHECKING:
    from uasset_read.models.result import ParseResult
    from uasset_read.models.core import UEdGraph, UEdGraphNode, UEdGraphPin


_CLASS_PATHS = {
    "K2Node_CallFunction": "/Script/BlueprintGraph.K2Node_CallFunction",
    "K2Node_Event": "/Script/BlueprintGraph.K2Node_Event",
    "K2Node_FunctionEntry": "/Script/BlueprintGraph.K2Node_FunctionEntry",
    "K2Node_Knot": "/Script/BlueprintGraph.K2Node_Knot",
    "K2Node_EnhancedInputAction": "/Script/InputBlueprintNodes.K2Node_EnhancedInputAction",
    "EdGraphNode_Comment": "/Script/UnrealEd.EdGraphNode_Comment",
}

_CONTAINER_LABELS = {
    0: "None",
    1: "Array",
    2: "Set",
    3: "Map",
}

_BLUEPRINT_UE_TEXT_DEPRECATION_MSG = (
    "format_blueprint_ue_text() 已弃用，推荐使用 "
    "parse_single(file_path, format='blueprint_ue_text') 统一入口。"
    "此函数将在未来版本中移除。"
)


def format_blueprint_ue_text(result: "ParseResult") -> str:
    """输出接近 UE 文本导出的 Begin Object / CustomProperties Pin 格式。

    .. deprecated:: 0.4.5
        推荐使用 parse_single(file_path, format='blueprint_ue_text') 统一入口。
    """
    warnings.warn(_BLUEPRINT_UE_TEXT_DEPRECATION_MSG, DeprecationWarning, stacklevel=2)
    if not result.graphs or not result.summary:
        return ""

    package_name = result.summary.package_name or "Unknown"
    asset_name = package_name.split("/")[-1] if package_name else "Unknown"
    sections: List[str] = []
    for graph in result.graphs:
        if sections:
            sections.append("")
        sections.extend(_format_graph(graph, package_name, asset_name))
    return "\n".join(sections).rstrip()


def _format_graph(graph: "UEdGraph", package_name: str, asset_name: str) -> List[str]:
    pin_lookup = _build_pin_lookup(graph)
    lines: List[str] = []
    for node in graph.nodes:
        if isinstance(node.node_data, dict) and node.node_data.get("_parse_error"):
            continue
        lines.extend(_format_node(node, graph.graph_name, package_name, asset_name, pin_lookup))
    return lines


def _build_pin_lookup(graph: "UEdGraph") -> Dict[str, Dict[str, str]]:
    lookup: Dict[str, Dict[str, str]] = {}
    for node in graph.nodes:
        node_name = getattr(node, "_export_object_name", None) or node.class_name
        for pin in node.pins:
            lookup[pin.pin_id] = {
                "node_name": node_name,
                "pin_name": pin.pin_name,
            }
    return lookup


def _format_node(
    node: "UEdGraphNode",
    graph_name: str,
    package_name: str,
    asset_name: str,
    pin_lookup: Dict[str, Dict[str, str]],
) -> List[str]:
    node_name = getattr(node, "_export_object_name", None) or node.class_name
    class_path = _CLASS_PATHS.get(node.class_name, f"/Script/Unknown.{node.class_name}")
    export_path = f"{class_path}'{package_name}.{asset_name}:{graph_name}.{node_name}'"

    lines = [
        f'Begin Object Class={class_path} Name="{node_name}" ExportPath="{export_path}"',
    ]

    data = node.node_data or {}
    if node.class_name == "K2Node_CallFunction":
        ref = data.get("function_reference")
        if ref:
            lines.append(f"   FunctionReference={_format_member_reference(ref)}")
    elif node.class_name == "K2Node_Event":
        ref = data.get("event_reference")
        if ref:
            lines.append(f"   EventReference={_format_member_reference(ref)}")
        if data.get("b_override_function"):
            lines.append("   bOverrideFunction=True")
    elif node.class_name == "K2Node_EnhancedInputAction":
        path = data.get("input_action_path")
        if path:
            lines.append(f'   InputAction="{path}"')
        adv = data.get("advanced_pin_display")
        if adv and adv != "Default":
            lines.append(f"   AdvancedPinDisplay={adv}")
    elif node.class_name == "K2Node_FunctionEntry":
        ref = data.get("function_reference")
        if ref:
            lines.append(f"   FunctionReference={_format_member_reference(ref)}")
    elif node.class_name == "EdGraphNode_Comment":
        color = data.get("comment_color")
        if color:
            lines.append(
                "   CommentColor=("
                f"R={color[0]:.6f},G={color[1]:.6f},B={color[2]:.6f},A={color[3]:.6f})"
            )
        if data.get("comment_depth") is not None:
            lines.append(f"   CommentDepth={data['comment_depth']}")
        if data.get("node_width") is not None:
            lines.append(f"   NodeWidth={data['node_width']}")
        if data.get("node_height") is not None:
            lines.append(f"   NodeHeight={data['node_height']}")

    lines.append(f"   NodePosX={node.node_pos_x}")
    lines.append(f"   NodePosY={node.node_pos_y}")
    if node.node_comment:
        lines.append(f'   NodeComment="{_escape(node.node_comment)}"')
    if node.node_guid:
        lines.append(f"   NodeGuid={node.node_guid.upper()}")

    for pin in node.pins:
        lines.append("   " + _format_pin(pin, pin_lookup))

    lines.append("End Object")
    return lines


def _format_member_reference(ref: object) -> str:
    member_parent = getattr(ref, "member_parent", None)
    member_name = getattr(ref, "member_name", "") or ""
    member_guid = getattr(ref, "member_guid", None)
    b_self_context = getattr(ref, "b_self_context", False)
    parts = []
    if member_parent:
        parts.append(f'MemberParent="{member_parent}"')
    parts.append(f'MemberName="{member_name}"')
    if member_guid:
        parts.append(f"MemberGuid={str(member_guid).upper()}")
    if b_self_context:
        parts.append("bSelfContext=True")
    return "(" + ",".join(parts) + ")"


def _format_pin(pin: "UEdGraphPin", pin_lookup: Dict[str, Dict[str, str]]) -> str:
    pin_type = pin.pin_type
    category = pin_type.pin_category if pin_type else ""
    subcategory = pin_type.pin_subcategory if pin_type else ""
    if category == "None":
        category = ""
    if subcategory == "None":
        subcategory = ""
    subcategory_object = _pin_subcategory_object(pin)
    container = _CONTAINER_LABELS.get(getattr(pin_type, "container_type", 0), "None")
    parts = [
        f"PinId={pin.pin_id.upper()}",
        f'PinName="{_escape(pin.pin_name)}"',
    ]
    if pin.pin_friendly_name:
        parts.append(f'PinFriendlyName="{_escape(pin.pin_friendly_name)}"')
    if pin.pin_tooltip:
        parts.append(f'PinToolTip="{_escape(pin.pin_tooltip)}"')
    if pin.direction == 1:
        parts.append('Direction="EGPD_Output"')
    parts.extend([
        f'PinType.PinCategory="{category}"',
        f'PinType.PinSubCategory="{subcategory}"',
        f"PinType.PinSubCategoryObject={subcategory_object}",
        "PinType.PinSubCategoryMemberReference=()",
        "PinType.PinValueType=()",
        f"PinType.ContainerType={container}",
        f"PinType.bIsReference={_bool_text(getattr(pin_type, 'is_reference', False))}",
        f"PinType.bIsConst={_bool_text(getattr(pin_type, 'is_const', False))}",
        f"PinType.bIsWeakPointer={_bool_text(getattr(pin_type, 'is_weak_pointer', False))}",
        f"PinType.bIsUObjectWrapper={_bool_text(getattr(pin_type, 'is_uobject_wrapper', False))}",
        "PinType.bSerializeAsSinglePrecisionFloat="
        + _bool_text(getattr(pin_type, "b_serialize_as_single_precision_float", False)),
    ])
    if pin.default_value not in (None, ""):
        parts.append(f'DefaultValue="{_escape(str(pin.default_value))}"')
    if pin.auto_default_value not in (None, ""):
        parts.append(f'AutogeneratedDefaultValue="{_escape(str(pin.auto_default_value))}"')
    default_object = _default_object_text(pin)
    if default_object is not None:
        parts.append(f'DefaultObject="{_escape(default_object)}"')
    if pin.linked_to_raw:
        parts.append(f"LinkedTo=({_join_refs(pin.linked_to_raw, pin_lookup)},)")
    if pin.sub_pins:
        parts.append(f"SubPins=({_join_refs(pin.sub_pins, pin_lookup)},)")
    if pin.parent_pin:
        parts.append(f"ParentPin={_pin_reference_text(pin.parent_pin, pin_lookup)}")
    if pin.ref_pass_through:
        parts.append(
            "ReferencePassThroughConnection="
            + _pin_reference_text(pin.ref_pass_through, pin_lookup)
        )
    persistent_guid = pin.persistent_guid or ("0" * 32)
    parts.extend([
        f"PersistentGuid={persistent_guid.upper()}",
        f"bHidden={_bool_text(pin.hidden)}",
        f"bNotConnectable={_bool_text(pin.not_connectable)}",
        "bDefaultValueIsReadOnly=False",
        "bDefaultValueIsIgnored=False",
        f"bAdvancedView={_bool_text(pin.advanced_view)}",
        f"bOrphanedPin={_bool_text(pin.orphaned_pin)}",
    ])
    return "CustomProperties Pin (" + ",".join(parts) + ",)"


def _pin_subcategory_object(pin: "UEdGraphPin") -> str:
    pin_type = pin.pin_type
    if pin_type is None:
        return "None"
    if getattr(pin_type, "pin_subcategory_object_ref", None) is not None:
        return f'"{_normalize_object_path(pin_type.pin_subcategory_object_ref.get_full_name())}"'
    if getattr(pin_type, "pin_subcategory_object_name", None):
        return f'"{_normalize_object_path(pin_type.pin_subcategory_object_name)}"'
    if getattr(pin_type, "pin_subcategory_object", 0):
        return str(pin_type.pin_subcategory_object)
    return "None"


def _default_object_text(pin: "UEdGraphPin") -> Optional[str]:
    if getattr(pin, "default_object_ref", None) is not None:
        return _normalize_object_path(pin.default_object_ref.get_full_name())
    default_object = getattr(pin, "default_object", None)
    if default_object not in (None, 0):
        return str(default_object)
    return None


def _normalize_object_path(value: str) -> str:
    if value.startswith("/Script/CoreUObject./"):
        return value[len("/Script/CoreUObject."):]
    return value


def _join_refs(refs: List[object], pin_lookup: Dict[str, Dict[str, str]]) -> str:
    return ",".join(
        text for text in (_pin_reference_text(ref, pin_lookup) for ref in refs) if text
    )


def _pin_reference_text(ref: object, pin_lookup: Dict[str, Dict[str, str]]) -> str:
    pin_guid = None
    owning_node = None
    if isinstance(ref, dict):
        pin_guid = ref.get("pin_guid") or ref.get("pin_id")
        owning_node = ref.get("owning_node")
    else:
        pin_guid = getattr(ref, "pin_guid", None) or getattr(ref, "pin_id", None)
        owning_node = getattr(ref, "owning_node", None)

    if pin_guid and pin_guid in pin_lookup:
        target = pin_lookup[pin_guid]
        return f"{target['node_name']} {pin_guid.upper()}"
    if owning_node and pin_guid:
        return f"{owning_node} {str(pin_guid).upper()}"
    if pin_guid:
        return str(pin_guid).upper()
    return ""


def _bool_text(value: bool) -> str:
    return "True" if value else "False"


def _escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")


__all__ = ["format_blueprint_ue_text"]
