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

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from uasset_read.archive import FArchive
    from uasset_read.serializers.object_resources import ObjectExport
    from uasset_read.serializers.package_summary import PackageFileSummary

# Hard caps on converted output. Values chosen so the largest tracked package
# (ALS_AnimBP: 275 graphs, ~2,700 node exports) passes without cap engagement
# while runaway editor graphs stay bounded (canonical design: bounded by default).
MAX_GRAPHS_PER_PACKAGE = 512
MAX_NODES_PER_GRAPH_OUTPUT = 256
MAX_PINS_PER_NODE_OUTPUT = 64


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
    from uasset_read.graph.parser import _validate_graph_export_offset
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
        if not _is_graph_class(class_name):
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
                None,  # linker not needed for single-package resolution
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


def _graph_to_dict(graph: Any, export_idx: int, class_name: str) -> dict[str, Any]:
    """Convert one UEdGraph tree into a JSON-safe dict (bounded).

    Node object model (models/core.py UEdGraphNode): ``_export_index`` is the
    1-based export index stamped by the shared readers; ``node_pos_x/y`` carry
    the editor position; ``pin_id`` is the 32-hex serialized pin GUID. Node
    display names come from the export entry (models/core UEdGraphNode has no
    name field); ``export.object_name`` is the serialized object name.
    """
    nodes: list[dict[str, Any]] = []
    pin_count = 0
    node_truncated = False
    pin_truncated = False
    for node in graph.nodes:
        if len(nodes) >= MAX_NODES_PER_GRAPH_OUTPUT:
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
                    # links are resolved package-wide by resolve_pin_links
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
    # _pin_links carries the raw GUID-keyed link records for the resolver;
    # resolve_pin_links consumes and removes it before the dicts leave the
    # module (extras and semantic output never contain non-JSON keys).
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
        "_pin_links": _collect_pin_links(graph),
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


def resolve_pin_links(graphs: list[dict[str, Any]]) -> None:
    """Resolve every graph's GUID-keyed links to (to_node, to_pin), in place.

    Builds one package-wide index of pin_guid -> (node id, pin id), then walks
    each graph's ``_pin_links`` records. A link whose target guid is absent is
    counted in the graph's ``unresolved_links`` (cross-package or clipped pin)
    and dropped — the reader pass turns that counter into a diagnostic, never
    a silent loss. Consumes and deletes ``_pin_links``; sets ``edge_count``.
    """
    guid_index: dict[str, tuple[str, str]] = {}
    for graph in graphs:
        for node in graph["nodes"]:
            for pin in node["pins"]:
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
