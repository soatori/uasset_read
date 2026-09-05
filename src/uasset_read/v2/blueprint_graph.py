"""Blueprint graph decode-pass support (issue #621 Phase 4.5).

The v2 handler layer never touches the archive, but editor-saved graph pins
are not exports — they are serialized inside each node export's serial region
after the tagged property stream. The fixture-proven binary readers in
``serializers/graph*.py`` are v1 modules this plan reuses unchanged (first v2
consumer, reader-layer reuse like serializers/object_resources.py — not v1
extractor bridging per D2). This module is the v2 decode-pass seam: it runs
those readers once per package at depth="decode" and converts the result into
JSON-safe plain dicts that travel through the ``extras`` channel
(``package_data[2]``) to the handlers.

UE source: UEdGraph::Serialize / UEdGraphNode::Serialize /
UEdGraphPin::Serialize in Engine/Source/Runtime/Engine/Classes/EdGraph/EdGraph*.h.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from uasset_read.archive import FArchive
    from uasset_read.serializers.object_resources import ObjectExport
    from uasset_read.serializers.package_summary import PackageFileSummary

logger = logging.getLogger(__name__)

# Hard caps on converted output. Values chosen so the largest tracked package
# (ALS_AnimBP: 275 graphs, ~2,700 node exports) passes without cap engagement
# while runaway editor graphs stay bounded (canonical design: bounded by default).
MAX_GRAPHS_PER_PACKAGE = 512
MAX_NODES_PER_GRAPH_OUTPUT = 512
MAX_PINS_PER_NODE_OUTPUT = 64


def _validate_graph_export_offset(export, archive_size: int) -> bool:
    """Validate whether a graph export's serialization offset is within valid range.

    When serial_offset is 0 and serial_size > 0, the offset is abnormal (non-Default__ export).
    When serial_offset + serial_size exceeds archive boundary, data is truncated.
    """
    serial_offset = getattr(export, "serial_offset", 0)
    serial_size = getattr(export, "serial_size", 0)

    if serial_size == 0:
        return True  # empty export, skip check

    # Check for negative values
    if serial_offset < 0 or serial_size < 0:
        logger.warning(
            "Graph export '%s' offset abnormal: offset=%d, size=%d",
            export.object_name,
            serial_offset,
            serial_size,
        )
        return False

    # Offset should not be 0 (unless it is a special Default__ export)
    if serial_offset == 0 and not str(getattr(export, "object_name", "")).startswith("Default__"):
        logger.warning(
            "Graph export '%s' serial_offset=0 and serial_size=%d, offset abnormal",
            export.object_name,
            serial_size,
        )
        return False

    # Check if exceeding archive boundary
    if archive_size > 0 and serial_offset + serial_size > archive_size:
        logger.warning(
            "Graph export '%s' offset out of bounds: offset=%d + size=%d > archive_size=%d",
            export.object_name,
            serial_offset,
            serial_size,
            archive_size,
        )
        return False

    return True


def _is_graph_class(class_name: str | None) -> bool:
    """Narrower than v1's EDGRAPH_CLASS_NAMES — only real UEdGraph containers."""
    if not class_name:
        return False
    return class_name.endswith("Graph")


def _pin_direction(direction: int) -> str:
    # EEdGraphPinDirection: EGPD_Input = 0, EGPD_Output = 1
    return {0: "input", 1: "output"}.get(direction, "unknown")


def read_blueprint_graphs(
    archive: FArchive,
    summary: PackageFileSummary,
    name_map: list[str],
    import_map: list[Any],
    export_map: list[ObjectExport],
    *,
    max_graphs: int = MAX_GRAPHS_PER_PACKAGE,
) -> list[dict[str, Any]]:
    """Parse all graph exports in the package and return plain graph dicts.

    Runs the shared binary readers (serializers/graph.read_ue_graph per graph
    export) and converts the resulting UEdGraph trees. Never raises on a
    single bad graph: failures produce a dict-level ``parse_errors`` count and
    the caller's diagnostics cover it. The archive must be open on the full
    package (decode pass restores the full read range before calling).
    """
    from uasset_read.serializers.graph import read_ue_graph
    from uasset_read.serializers.object_resources import get_asset_class

    archive_size = 0
    if archive is not None:
        try:
            archive_size = archive.total_size()
        except (OSError, AttributeError):
            archive_size = 0

    graphs: list[dict[str, Any]] = []
    processed = 0
    for export_idx, export in enumerate(export_map):
        class_name = get_asset_class(export, import_map, export_map)
        if not class_name or not _is_graph_class(class_name):
            continue
        if processed >= max_graphs:
            break
        processed += 1
        try:
            if not _validate_graph_export_offset(export, archive_size):
                graphs.append(_error_graph(export_idx, class_name, "offset validation failed"))
                continue
            graph = read_ue_graph(
                archive,
                name_map,
                summary,
                export_map,
                import_map,
                export,
                class_name,
                export_idx + 1,  # 1-based index
            )
            graphs.append(_graph_to_dict(graph, export_idx, class_name))
        except Exception as exc:  # one bad graph must not kill the decode pass
            graphs.append(_error_graph(export_idx, class_name, f"{type(exc).__name__}: {exc}"))
    resolve_pin_links(graphs)
    return graphs


def _error_graph(export_idx: int, class_name: str, reason: str) -> dict[str, Any]:
    return {
        "id": f"export:{export_idx}",
        "name": "",
        "graph_class": class_name or "",
        "kind": "unknown",
        "nodes": [],
        "node_count": 0,
        "pin_count": 0,
        "edge_count": 0,
        "truncated": {"nodes": False, "pins": False},
        "parse_errors": [reason],
    }


def _convert_nodes(graph: Any, nodes: list[dict[str, Any]], pin_count: int, node_limit: int) -> tuple[int, bool, bool]:
    """Convert nodes from a UEdGraph into dicts, appending to *nodes*.

    Returns (pin_count, node_truncated, pin_truncated).
    """
    node_truncated = False
    pin_truncated = False
    for node in graph.nodes:
        if len(nodes) >= node_limit:
            node_truncated = True
            break
        pins: list[dict[str, Any]] = []
        for pin in node.pins:
            if len(pins) >= MAX_PINS_PER_NODE_OUTPUT:
                pin_truncated = True
                break
            pins.append(
                {
                    "id": str(pin.pin_id),
                    "name": str(pin.pin_name),
                    "direction": _pin_direction(pin.direction),
                    "category": str(pin.pin_type.pin_category) if pin.pin_type else "",
                    "linked": [],
                }
            )
        pin_count += len(pins)
        nodes.append(
            {
                "id": f"export:{node._export_index - 1}" if getattr(node, "_export_index", 0) else "",
                "type": str(node.class_name or ""),
                "name": str(graph.graph_name or ""),
                "position": {
                    "x": int(node.node_pos_x or 0),
                    "y": int(node.node_pos_y or 0),
                },
                "pins": pins,
            }
        )
    return pin_count, node_truncated, pin_truncated


def _collect_pin_links_recursive(graph: Any) -> list[dict[str, Any]]:
    """Collect pin links from a UEdGraph and all its subgraphs."""
    links = _collect_pin_links(graph)
    for sub in graph.subgraphs:
        links.extend(_collect_pin_links_recursive(sub))
    return links


def _graph_to_dict(graph: Any, export_idx: int, class_name: str) -> dict[str, Any]:
    """Convert one UEdGraph tree into a JSON-safe dict (bounded).

    Recursively flattens subgraph nodes into the parent's ``nodes`` list,
    since UE subgraphs are a visual-organization concept and the output
    contract uses a flat node array per graph.
    """
    nodes: list[dict[str, Any]] = []
    pin_count = 0
    node_truncated = False
    pin_truncated = False

    # Top-level nodes
    pin_count, node_truncated, pin_truncated = _convert_nodes(graph, nodes, pin_count, MAX_NODES_PER_GRAPH_OUTPUT)
    # Subgraph nodes (flattened into the same list)
    for sub in graph.subgraphs:
        if node_truncated:
            break
        sub_pin_count, sub_node_trunc, sub_pin_trunc = _convert_nodes(sub, nodes, pin_count, MAX_NODES_PER_GRAPH_OUTPUT)
        pin_count = sub_pin_count
        if sub_node_trunc:
            node_truncated = True
        if sub_pin_trunc:
            pin_truncated = True

    return {
        "id": f"export:{export_idx}",
        "name": str(graph.graph_name or ""),
        "graph_class": class_name,
        "kind": "unknown",  # finalized by the handler from name / FunctionGraphs
        "nodes": nodes,
        "node_count": len(nodes),
        "pin_count": pin_count,
        "edge_count": 0,  # set by resolve_pin_links
        "truncated": {"nodes": node_truncated, "pins": pin_truncated},
        "_pin_links": _collect_pin_links_recursive(graph),
    }


def _collect_pin_links(graph: Any) -> list[dict[str, Any]]:
    """Collect (source pin, target pin-guid) link records from one UEdGraph tree.

    ``UEdGraphPin.linked_to_raw`` entries are ``{"owning_node": <target node
    name>, "pin_guid": <target 32-hex>}`` — the *target's* GUID (verified on
    the tracked fixtures); the source is the pin owning the list. So each
    record carries the owning pin's own id (``from_pin``) plus the target
    ``pin_guid``; ``owning_node`` (a display name, not an index) is unused.
    """
    links: list[dict[str, Any]] = []
    for node in graph.nodes:
        for pin in node.pins:
            for entry in pin.linked_to_raw:
                links.append(
                    {
                        "from_node": getattr(node, "_export_index", 0),  # 1-based
                        "from_pin": str(pin.pin_id),
                        "to_pin": str(entry.get("pin_guid", "")),
                    }
                )
    return links


def _collect_all_nodes(graphs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Collect every node dict from the emitted graphs.

    The emitter inlines subgraph nodes into their owning graph's ``nodes`` list
    (see ``_graph_to_dict``), so an emitted graph dict carries no ``subgraphs``
    key and a recursive walk here would be dead weight.
    """
    return [n for g in graphs for n in g.get("nodes", [])]


def resolve_pin_links(graphs: list[dict[str, Any]]) -> None:
    """Resolve every graph's GUID-keyed links to (to_node, to_pin), in place.

    Builds one package-wide index of pin_guid -> (node id, pin id), then walks
    each graph's ``_pin_links`` records. A link whose target guid is absent is
    counted in the graph's ``unresolved_links`` (cross-package or clipped pin)
    and dropped — the reader pass turns that counter into a diagnostic, never
    a silent loss. Consumes and deletes ``_pin_links``; sets ``edge_count``.
    """
    all_nodes = _collect_all_nodes(graphs)
    guid_index: dict[str, tuple[str, str]] = {}
    for node in all_nodes:
        for pin in node.get("pins", []):
            if pin["id"]:
                guid_index[pin["id"]] = (node["id"], pin["id"])
    for graph in graphs:
        graph["unresolved_links"] = 0
        edge_count = 0
        for rec in graph.pop("_pin_links", []):
            target = guid_index.get(rec["to_pin"])
            if target is None:
                graph["unresolved_links"] += 1
                continue
            edge_count += 1
            source_node_id = f"export:{rec['from_node'] - 1}"
            for node in graph["nodes"]:
                if node["id"] != source_node_id:
                    continue
                for pin in node["pins"]:
                    if pin["id"] == rec["from_pin"]:
                        pin["linked"].append({"to_node": target[0], "to_pin": target[1]})
        graph["edge_count"] = edge_count
