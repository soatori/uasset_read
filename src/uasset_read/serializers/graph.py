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

from uasset_read.constants import MAX_NODES_PER_GRAPH, MAX_SUBGRAPHS
from uasset_read.exceptions import ParseError
from uasset_read.serializers.object_resources import resolve_class_name
from uasset_read.models.core import UEdGraph, UEdGraphNode

logger = logging.getLogger(__name__)


# ============================================================================
# UEdGraph reading
# ============================================================================


def _extract_graph_properties(
    graph_export: ObjectExport,
) -> list[int]:
    """Extract the Nodes export-index list from pre-parsed PropertyTag data.

    UEdGraph.Nodes is a UPROPERTY in UE, serialized via PropertyTag in the
    export body. Schema/GraphGuid/bEditable were write-only for the v2
    projection and were deleted with the subtraction wave.

    Returns:
        node_indices: 1-based export index list of nodes
    """
    node_indices: list[int] = []

    props = getattr(graph_export, "properties", None) or []
    for prop in props:
        name = getattr(prop, "name", None) or (prop.get("name") if isinstance(prop, dict) else None)
        value = getattr(prop, "value", None) or (prop.get("value") if isinstance(prop, dict) else None)
        if name == "Nodes" and isinstance(value, list):
            node_indices = [v for v in value if isinstance(v, int) and v > 0]

    return node_indices


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

    Nodes are a UPROPERTY extracted by the PropertyTag parser during preload
    into graph_export.properties. This function reads them from the
    pre-parsed properties instead of parsing binary again.

    Node data is still read via archive.seek(node_export.serial_offset)
    (node export's script_serial + pins are separate binary segments).

    Reference: UE C++ UEdGraph::Serialize()
    """
    # Lazy import to avoid circular dependency (graph.py -> graph_node.py)
    from uasset_read.serializers.graph_node import read_ue_graph_node

    if _parsed_indices is None:
        _parsed_indices = set()
    _parsed_indices.add(graph_export_idx)

    # -- 1. Extract Nodes from PropertyTag --
    node_indices = _extract_graph_properties(graph_export)

    # -- 2. Read each node's binary data by node_indices --
    if len(node_indices) > MAX_NODES_PER_GRAPH:
        logger.debug(
            "node_indices count %d exceeds MAX_NODES_PER_GRAPH %d, truncating", len(node_indices), MAX_NODES_PER_GRAPH
        )
        node_indices = node_indices[:MAX_NODES_PER_GRAPH]

    nodes: list[UEdGraphNode] = []

    def read_node(node_export: ObjectExport, node_idx: int) -> UEdGraphNode:
        node = read_ue_graph_node(archive, name_map, summary, export_map, import_map, node_export)
        node._export_index = node_idx  # tag for dedup
        return node

    for node_index in node_indices:
        if node_index <= 0 or node_index > len(export_map):
            continue
        node_export = export_map[node_index - 1]
        try:
            nodes.append(read_node(node_export, node_index))
        except (ParseError, struct.error, OSError, ValueError, KeyError):
            logger.debug(
                "Failed to read node %s (export #%d) in graph %s",
                node_export.object_name,
                node_index,
                graph_export.object_name,
            )

    # UE 5.x fallback: scan export_map for nodes whose outer is this graph.
    # Catches nodes not listed in the Nodes PropertyTag (e.g. dynamically added nodes).
    if graph_export_idx > 0:
        for node_export in export_map:
            if node_export.outer_index.index == graph_export_idx:
                node_class = resolve_class_name(node_export.class_index, import_map, export_map)
                if node_class and (
                    node_class.startswith("K2Node") or node_class.startswith("EdGraphNode") or "Node" in node_class
                ):
                    node_idx = export_map.index(node_export) + 1
                    already_collected = any(getattr(n, "_export_index", None) == node_idx for n in nodes)
                    if already_collected:
                        continue
                    try:
                        nodes.append(read_node(node_export, node_idx))
                    except (ParseError, struct.error, OSError, ValueError, KeyError):
                        nodes.append(
                            UEdGraphNode(
                                node_pos_x=0,
                                node_pos_y=0,
                                node_comment="",
                                pins=[],
                                class_name=node_class or "",
                                node_data={"_parse_error": True, "node_name": node_export.object_name},
                            )
                        )

    # -- 3. SubGraphs -- from PropertyTag --
    subgraph_indices: list[int] = []

    props = getattr(graph_export, "properties", None) or []
    for prop in props:
        pname = getattr(prop, "name", None) or (prop.get("name") if isinstance(prop, dict) else None)
        pvalue = getattr(prop, "value", None) or (prop.get("value") if isinstance(prop, dict) else None)
        if pname == "SubGraphs" and isinstance(pvalue, list):
            if len(pvalue) > MAX_SUBGRAPHS:
                logger.debug(
                    "SubGraphs count %d exceeds limit %d, truncating",
                    len(pvalue),
                    MAX_SUBGRAPHS,
                )
                pvalue = pvalue[:MAX_SUBGRAPHS]
            subgraph_indices = [v for v in pvalue if isinstance(v, int) and v > 0]

    # 6. Parse subgraphs (merge SubGraphs array + AnimGraphNode nested subgraphs)
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

    # 6a. From the SubGraphs array (directly serialized subgraph references)
    for pkg_idx in subgraph_indices:
        try:
            subgraph = parse_subgraph(pkg_idx)
        except (struct.error, OSError, ValueError, KeyError) as e:
            logger.debug("Failed to parse SubGraphs entry %d: %s", pkg_idx, e)
            subgraph = None
        if subgraph is not None:
            subgraphs.append(subgraph)

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
    )
