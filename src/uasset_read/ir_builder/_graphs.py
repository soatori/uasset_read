"""IR 构建层 — 图相关函数（GraphIR / NodeIR / PinIR）。"""
from __future__ import annotations

from uasset_read.ir_builder._utils import _safe_str, _normalize_guid, _extract_pin_guid
from uasset_read.models.ir import GraphIR, NodeIR, PinIR


def _build_graph_ir(graph) -> GraphIR:
    nodes = []
    for node in getattr(graph, "nodes", None) or []:
        nodes.append(_build_node_ir(node))

    return GraphIR(
        graph_guid=_normalize_guid(getattr(graph, "graph_guid", None)),
        graph_name=_safe_str(getattr(graph, "graph_name", None)),
        graph_class=_safe_str(getattr(graph, "graph_class", None)),
        nodes=nodes,
        execution_chains=getattr(graph, "execution_chains", None) or [],
    )


def _build_node_ir(node) -> NodeIR:
    pins = []
    for pin in getattr(node, "pins", None) or []:
        pins.append(_build_pin_ir(pin))

    return NodeIR(
        node_guid=_normalize_guid(getattr(node, "node_guid", None)),
        node_class=_safe_str(getattr(node, "class_name", None)),
        node_comment=getattr(node, "node_comment", None),
        pins=pins,
        execution_flow=getattr(node, "execution_flow", None) or [],
        macro_expansion=getattr(node, "macro_expansion", None),
    )


def _build_pin_ir(pin) -> PinIR:
    linked_to = []
    for ref in getattr(pin, "linked_to_raw", None) or []:
        guid = _extract_pin_guid(ref)
        if guid:
            linked_to.append(guid)

    direction = "EGPD_Input"
    if getattr(pin, "direction", 0) == 1:
        direction = "EGPD_Output"

    return PinIR(
        pin_name=_safe_str(getattr(pin, "pin_name", None)),
        pin_type=_safe_str(getattr(pin, "pin_type", None)),
        pin_type_value=getattr(pin, "pin_type_value", None),
        linked_to=linked_to,
        direction=direction,
        default_value=getattr(pin, "default_value", None),
    )
