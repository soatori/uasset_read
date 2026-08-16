"""Graph/node/pin/port emission for Blueprint semantic JSON (BP-6, 7, 8)."""
from __future__ import annotations

from typing import Any

from uasset_read.semantic.blueprint.ids import (
    ascii_slug, graph_id, node_id, data_endpoint, exec_endpoint,
)
from uasset_read.semantic.blueprint.types import type_ref_from_pin

_NODE_KIND_MAP = {
    "K2Node_Event": "event",
    "K2Node_CustomEvent": "custom_event",
    "K2Node_FunctionEntry": "function_entry",
    "K2Node_FunctionResult": "function_result",
    "K2Node_CallFunction": "call",
    "K2Node_VariableGet": "variable_get",
    "K2Node_VariableSet": "variable_set",
    "K2Node_IfThenElse": "branch",
    "K2Node_SwitchInteger": "switch",
    "K2Node_SwitchString": "switch",
    "K2Node_SwitchEnum": "switch",
    "K2Node_SwitchName": "switch",
    "K2Node_ExecutionSequence": "sequence",
    "K2Node_MultiGate": "sequence",
    "K2Node_MacroInstance": "macro",
    "K2Node_DynamicCast": "cast",
    "K2Node_ClassDynamicCast": "cast",
    "K2Node_MakeStruct": "make_struct",
    "K2Node_BreakStruct": "break_struct",
    "K2Node_CreateDelegate": "delegate_bind",
    "K2Node_AddDelegate": "delegate_bind",
    "K2Node_RemoveDelegate": "delegate_unbind",
    "K2Node_CallDelegate": "delegate_call",
    "K2Node_Literal": "literal",
    "K2Node_Knot": "reroute",
    "K2Node_Tunnel": "tunnel",
    "EdGraphNode_Comment": "comment",
}

_GRAPH_KIND_RULES = (
    ("UserConstructionScript", "construction_script"),
    ("MacroGraph", "macro"),
    ("collapsed", "collapsed_graph"),
    ("FunctionGraph", "function"),
    ("EdGraph", "event_graph"),
)


def _graph_kind(graph_name: str, graph_class: str) -> str:
    text = f"{graph_class}.{graph_name}".lower()
    for needle, kind in _GRAPH_KIND_RULES:
        if needle.lower() in text:
            return kind
    return "event_graph"


def _node_name(node) -> str:
    """Semantic node name: member ref > variable/event pin > class (BP-5)."""
    member = getattr(node, "member_name", None)
    if member:
        return member
    for pin in getattr(node, "pins", None) or []:
        name = getattr(pin, "pin_name", "") or ""
        if name and name.lower() not in {"execute", "then", "self", "inputpin", "outputpin"}:
            return name
    return getattr(node, "node_class", "") or getattr(node, "class_name", "") or "unnamed"


def _direction_str(pin) -> str:
    direction = getattr(pin, "direction", 0)
    if direction in ("EGPD_Input", "EGPD_Output"):
        return "output" if direction == "EGPD_Output" else "input"
    return "output" if direction == 1 else "input"


def _is_exec(pin) -> bool:
    category = getattr(pin, "pin_category", "") or ""
    if not category:
        pin_type_str = str(getattr(pin, "pin_type", "") or "")
        category = pin_type_str.split("(", 1)[0].strip().lower()
    return category.lower() == "exec"


def _linked_guids(pin) -> list[str]:
    linked = getattr(pin, "linked_to", None)
    if isinstance(linked, list) and linked and isinstance(linked[0], str):
        return [g for g in linked if g]
    raw = getattr(pin, "linked_to_raw", None) or []
    return [r.get("pin_guid") for r in raw if isinstance(r, dict) and r.get("pin_guid")]


def _pin_keep(pin, connected: bool) -> bool:
    """BP-8 keep rule: connected, defaulted, ref/wildcard pins are kept."""
    if connected:
        return True
    if getattr(pin, "orphaned", False) or getattr(pin, "orphaned_pin", False):
        return False
    if getattr(pin, "default_value", "") or getattr(pin, "default_object_name", None) \
            or getattr(pin, "default_text_value", None):
        return True
    if getattr(pin, "is_reference", False):
        return True
    category = (getattr(pin, "pin_category", "") or "").lower()
    return category == "wildcard"


def emit_graphs(graphs, table, reporting, *, mode: str) -> tuple[list[dict], dict]:
    """Emit graphs with nodes/pins/ports.

    Returns (graphs_json, index): index maps pin_guid -> endpoint info for
    flows.py. Deterministic order: graphs and nodes in serialization order;
    duplicate graph names get a numeric suffix.
    """
    graphs_json: list[dict] = []
    index: dict[str, dict] = {}
    graph_slug_counts: dict[str, int] = {}

    def emit(graph) -> None:
        name = getattr(graph, "graph_name", "") or "Graph"
        slug = ascii_slug(name)
        seen = graph_slug_counts.get(slug, 0)
        graph_slug_counts[slug] = seen + 1
        if seen:
            slug = f"{slug}_{seen}"
        gid = graph_id(slug)
        nodes_json: list[dict] = []
        ordinal_counts: dict[tuple[str, str], int] = {}

        for node in getattr(graph, "nodes", None) or []:
            node_json, node_index = _emit_node(node, slug, ordinal_counts, table, reporting, mode)
            if node_json is None:
                continue
            nodes_json.append(node_json)
            index.update(node_index)

        kind = _graph_kind(name, getattr(graph, "graph_class", "") or "")
        if kind == "event_graph" and any(
                _NODE_KIND_MAP.get(getattr(n, "node_class", "") or getattr(n, "class_name", "") or "") == "function_entry"
                for n in getattr(graph, "nodes", None) or []):
            kind = "function"  # evidence-based: graph contains a FunctionEntry node
        entry: dict = {"id": gid, "name": name, "kind": kind, "nodes": nodes_json}
        if mode == "debug":
            entry["evidence"] = {"graph_guid": getattr(graph, "graph_guid", "") or ""}
        graphs_json.append(entry)

        for subgraph in getattr(graph, "subgraphs", None) or []:
            emit(subgraph)

    for graph in graphs:
        emit(graph)
    return graphs_json, index


def _emit_node(node, graph_slug, ordinal_counts, table, reporting, mode):
    node_class = getattr(node, "node_class", "") or getattr(node, "class_name", "") or ""
    kind = _NODE_KIND_MAP.get(node_class)
    status = "recognized"
    if kind is None:
        kind = "custom"
        status = "opaque"
        reporting.diagnostic("BP_NODE_UNRECOGNIZED", f"graph:{graph_id(graph_slug)}/nodes",
                             "warning", "semantic_loss", occurrence={"class": node_class})
    if kind == "comment":
        return None, {}

    raw_name = _node_name(node)
    name_slug = ascii_slug(raw_name)
    key = (kind, name_slug)
    ordinal = ordinal_counts.get(key, 0)
    ordinal_counts[key] = ordinal + 1
    nid = node_id(graph_slug, kind, name_slug, ordinal)

    node_index: dict[str, dict] = {}
    data_pins: dict[str, dict] = {}
    control_ports: dict[str, dict] = {}

    for pin in getattr(node, "pins", None) or []:
        pin_id = getattr(pin, "pin_guid", "") or ""
        direction = _direction_str(pin)
        is_exec = _is_exec(pin)
        pin_name = getattr(pin, "pin_name", "") or ""
        endpoint = exec_endpoint(pin_name) if is_exec else data_endpoint(pin_name, direction)
        linked = _linked_guids(pin)
        if pin_id:
            node_index[pin_id] = {
                "node": nid, "graph": graph_id(graph_slug), "endpoint": endpoint,
                "direction": direction, "is_exec": is_exec,
                "orphaned": bool(getattr(pin, "orphaned", False)
                                 or getattr(pin, "orphaned_pin", False)),
                "not_connectable": bool(getattr(pin, "not_connectable", False)),
                "linked": linked,
            }
        connected = bool(linked)
        if is_exec:
            role = ascii_slug(pin_name).lower().replace("_", "-") or "port"
            control_ports[endpoint] = {"name": pin_name, "direction": direction, "role": role}
        elif _pin_keep(pin, connected):
            dpin: dict = {"name": pin_name, "direction": direction,
                          "type": type_ref_from_pin(table, pin)}
            if getattr(pin, "sub_pin_guids", None):
                dpin["path"] = [ascii_slug(pin_name)]
            if getattr(pin, "parent_pin_guid", ""):
                dpin["split_child"] = True
            data_pins[endpoint] = dpin

    result: dict = {"id": nid, "kind": kind}
    if raw_name != name_slug:
        result["label"] = raw_name
    if status != "recognized":
        result["status"] = status
        result["source_type"] = node_class
    if data_pins:
        result["data_pins"] = data_pins
    if control_ports:
        result["control_ports"] = control_ports
    if mode == "debug":
        result["evidence"] = {"node_guid": getattr(node, "node_guid", "") or "",
                              "source_class": node_class}
    return result, node_index
