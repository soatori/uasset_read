"""UEdGraph container reader.

Pin and Node serializers live in graph_pin.py and graph_node.py.
Shared helpers (GUID, PropertyTag, FText, pin validation)
are in graph_helpers.py to break the circular import cycle.
"""

from __future__ import annotations

import logging
import struct
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from uasset_read.archive import FArchive
    from uasset_read.serializers.package_summary import PackageFileSummary
    from uasset_read.serializers.object_resources import ObjectExport, ObjectImport

from uasset_read.exceptions import ParseError
from uasset_read.serializers.object_resources import resolve_class_name
from uasset_read.models.core import UEdGraph, UEdGraphNode

logger = logging.getLogger(__name__)


# ============================================================================
# UEdGraph reading
# ============================================================================


def read_ue_graph(
    archive: FArchive,
    name_map: list[str],
    summary: PackageFileSummary,
    export_map: list[ObjectExport],
    import_map: list[ObjectImport],
    graph_export: ObjectExport,
    graph_export_idx: int = 0,
    _parsed_indices: set | None = None,
) -> UEdGraph:
    """Read UEdGraph container (EdGraph.cpp).

    Nodes are discovered by scanning export_map for node exports whose outer
    is this graph (the Nodes UPROPERTY path is dead: ObjectExport.properties
    is never populated). Node data is read via
    archive.seek(node_export.serial_offset) (script_serial + pins are
    separate binary segments).

    Reference: UE C++ UEdGraph::Serialize()
    """
    # Lazy import to avoid circular dependency (graph.py -> graph_node.py)
    from uasset_read.serializers.graph_node import read_ue_graph_node

    if _parsed_indices is None:
        _parsed_indices = set()
    _parsed_indices.add(graph_export_idx)

    nodes: list[UEdGraphNode] = []
    parse_errors: list[str] = []

    def read_node(node_export: ObjectExport, node_idx: int) -> UEdGraphNode:
        node = read_ue_graph_node(archive, name_map, summary, export_map, import_map, node_export)
        node._export_index = node_idx  # tag for dedup
        return node

    def fallback_node(node_export: ObjectExport, node_idx: int, node_class: str, exc: BaseException) -> UEdGraphNode:
        """Addressable partial node: keeps the 1-based export index so the
        conversion emits export:N — never id=\"\" — and never fabricates pins."""
        reason = f"node export:{node_idx - 1} ({node_export.object_name}): {type(exc).__name__}: {exc}"
        parse_errors.append(reason)
        return UEdGraphNode(
            node_pos_x=0,
            node_pos_y=0,
            node_comment="",
            pins=[],
            class_name=node_class or "",
            node_data={"_parse_error": True, "node_name": node_export.object_name, "reason": reason},
            _export_index=node_idx,
        )

    # Scan export_map for nodes whose outer is this graph (catches nodes not
    # listed in any pre-parsed Nodes tag, e.g. dynamically added nodes).
    if graph_export_idx > 0:
        for node_export in export_map:
            if node_export.outer_index.index == graph_export_idx:
                node_class = resolve_class_name(node_export.class_index, import_map, export_map)
                if node_class and (
                    node_class.startswith("K2Node") or node_class.startswith("EdGraphNode") or "Node" in node_class
                ):
                    node_idx = export_map.index(node_export) + 1
                    try:
                        nodes.append(read_node(node_export, node_idx))
                    except (ParseError, struct.error, OSError, ValueError, KeyError) as exc:
                        nodes.append(fallback_node(node_export, node_idx, node_class or "", exc))

    # Subgraph references from AnimGraphNode node_data.subgraph_references
    # (name overridden by owner).
    subgraphs: list[UEdGraph] = []

    def parse_subgraph(pkg_idx: int) -> UEdGraph | None:
        """Resolve one subgraph export reference; None when absent or not a graph."""
        if pkg_idx <= 0 or pkg_idx > len(export_map) or pkg_idx in _parsed_indices:
            return None
        subgraph_export = export_map[pkg_idx - 1]
        subgraph_class = resolve_class_name(subgraph_export.class_index, import_map, export_map) or ""
        if not (subgraph_class.endswith("Graph") or subgraph_class == "EdGraph" or subgraph_class == "UberEdGraph"):
            return None
        return read_ue_graph(
            archive,
            name_map,
            summary,
            export_map,
            import_map,
            subgraph_export,
            pkg_idx,
            _parsed_indices=_parsed_indices,
        )

    # 6b. From AnimGraphNode node_data.subgraph_references (name overridden by owner)
    for node in nodes:
        node_data = getattr(node, "node_data", None)
        if not isinstance(node_data, dict):
            continue
        for ref_key, ref_info in node_data.get("subgraph_references", {}).items():
            if not isinstance(ref_info, dict) or "error" in ref_info:
                continue
            try:
                subgraph = parse_subgraph(ref_info.get("package_index", 0))
                if subgraph is not None:
                    subgraph.graph_name = f"{node.node_comment or node.class_name}.{ref_key}"
                    subgraphs.append(subgraph)
            except (struct.error, OSError, ValueError, KeyError) as e:
                logger.debug("Failed to parse subgraph %s: %s", ref_info.get("object_name", ""), e)

    return UEdGraph(
        graph_name=graph_export.object_name,
        nodes=nodes,
        subgraphs=subgraphs,
        parse_errors=parse_errors,
    )
