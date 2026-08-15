"""UEdGraph container reader and backward-compatible re-exports.

Pin and Node serializers live in graph_pin.py and graph_node.py.
Shared helpers (GUID, PropertyTag, FText, diagnostic tracing, pin validation)
are in graph_helpers.py to break the circular import cycle.

This module:
  - imports helpers it needs from graph_helpers (one-way)
  - defines read_ue_graph / _extract_graph_properties
  - re-exports symbols from graph_pin.py and graph_node.py for backward compat
"""
from __future__ import annotations

import logging
import struct
from typing import TYPE_CHECKING, List, Optional

if TYPE_CHECKING:
    from uasset_read.archive import FArchive
    from uasset_read.serializers.package_summary import PackageFileSummary
    from uasset_read.serializers.object_resources import ObjectExport, ObjectImport
    from uasset_read.link.linker import PackageLinker

from uasset_read.constants import (
    MAX_NODES_PER_GRAPH,  # noqa: F401 — backward-compat re-export
    MAX_SUBGRAPHS,        # noqa: F401 — backward-compat re-export
)
from uasset_read.exceptions import ParseError
from uasset_read.serializers.graph_helpers import _gac
from uasset_read.serializers.graph_helpers import (  # noqa: F401 — backward-compat re-exports
    read_ftext_with_history,
)
from uasset_read.models.core import UEdGraph, UEdGraphNode

logger = logging.getLogger(__name__)


# ============================================================================
# UEdGraph reading
# ============================================================================

def _extract_graph_properties(
    graph_export: ObjectExport,
) -> tuple:
    """Extract UEdGraph fields from pre-parsed PropertyTag data.

    UEdGraph Schema, Nodes, GraphGuid are UPROPERTY in UE, so they are
    serialized via PropertyTag in export body.  Read them from
    graph_export.properties instead of parsing binary again.

    Returns:
        (schema_name, node_indices, graph_guid_str)
        schema_name: full name of Schema import, e.g. "EdGraphSchema_K2", None if not found
        node_indices: 1-based export index list of nodes
        graph_guid_str: hex string of GraphGuid (lowercase, no dash), "" if not found
    """
    schema_name: Optional[str] = None
    node_indices: List[int] = []
    graph_guid: str = ""

    props = getattr(graph_export, "properties", None) or []
    for prop in props:
        name = getattr(prop, "name", None) or (prop.get("name") if isinstance(prop, dict) else None)
        value = getattr(prop, "value", None) or (prop.get("value") if isinstance(prop, dict) else None)
        if name == "Schema" and value is not None:
            # ObjectProperty -> import reference
            if isinstance(value, dict):
                schema_name = value.get("object_name") or value.get("full_name")
            elif isinstance(value, int):
                # Unresolved PackageIndex (legacy)
                pass
        elif name == "Nodes" and isinstance(value, list):
            node_indices = [v for v in value if isinstance(v, int) and v > 0]
        elif name == "GraphGuid" and isinstance(value, dict):
            fields = value.get("fields", {})
            if fields:
                a = fields.get("A", 0) & 0xFFFFFFFF
                b = fields.get("B", 0) & 0xFFFFFFFF
                c = fields.get("C", 0) & 0xFFFFFFFF
                d = fields.get("D", 0) & 0xFFFFFFFF
                graph_guid = (
                    f"{a & 0xFF:02x}{(a >> 8) & 0xFF:02x}{(a >> 16) & 0xFF:02x}{(a >> 24) & 0xFF:02x}"
                    f"{b & 0xFF:02x}{(b >> 8) & 0xFF:02x}{c & 0xFF:02x}{(c >> 8) & 0xFF:02x}"
                    f"{(c >> 16) & 0xFF:02x}{(c >> 24) & 0xFF:02x}{d & 0xFF:02x}{(d >> 8) & 0xFF:02x}"
                    f"{(d >> 16) & 0xFF:02x}{(d >> 24) & 0xFF:02x}"
                )

    return schema_name, node_indices, graph_guid


def read_ue_graph(
    archive: FArchive,
    name_map: List[str],
    summary: PackageFileSummary,
    export_map: List[ObjectExport],
    import_map: List[ObjectImport],
    graph_export: ObjectExport,
    graph_class: str,
    graph_export_idx: int = 0,
    linker: Optional["PackageLinker"] = None,
    _parsed_indices: Optional[set] = None,
) -> UEdGraph:
    """Read UEdGraph container (EdGraph.cpp).

    Schema / Nodes / GraphGuid are UPROPERTY, extracted by the PropertyTag
    parser during preload into graph_export.properties.  This function reads
    them from the pre-parsed properties instead of parsing binary again.

    Node data is still read via archive.seek(node_export.serial_offset)
    (node export's script_serial + pins are separate binary segments).

    Reference: UE C++ UEdGraph::Serialize()
    """
    # Lazy import to avoid circular dependency (graph.py -> graph_node.py)
    from uasset_read.serializers.graph_node import read_ue_graph_node  # noqa: F811

    if _parsed_indices is None:
        _parsed_indices = set()
    _parsed_indices.add(graph_export_idx)

    # -- 1. Extract Schema / Nodes / GraphGuid from PropertyTag --
    schema_name, node_indices, graph_guid = _extract_graph_properties(graph_export)

    # Resolve Schema reference
    schema: Optional[str] = schema_name

    # -- 2. Read each node's binary data by node_indices --
    if len(node_indices) > MAX_NODES_PER_GRAPH:
        logger.debug("node_indices count %d exceeds MAX_NODES_PER_GRAPH %d, truncating",
                       len(node_indices), MAX_NODES_PER_GRAPH)
        node_indices = node_indices[:MAX_NODES_PER_GRAPH]

    nodes: List[UEdGraphNode] = []

    for node_index in node_indices:
        if node_index <= 0 or node_index > len(export_map):
            continue
        node_export = export_map[node_index - 1]
        try:
            node = read_ue_graph_node(archive, name_map, summary, export_map, import_map, node_export, linker)
            node._export_index = node_index  # tag for dedup
            nodes.append(node)
        except (ParseError, struct.error, OSError, ValueError, KeyError):
            logger.debug("Failed to read node %s (export #%d) in graph %s",
                           node_export.object_name, node_index, graph_export.object_name)

    # UE 5.x fallback: scan export_map for nodes whose outer is this graph.
    # Catches nodes not listed in the Nodes PropertyTag (e.g. dynamically added nodes).
    if graph_export_idx > 0:
        for node_export in export_map:
            if node_export.outer_index.index == graph_export_idx:
                node_class = _gac(node_export, import_map, export_map, linker)
                if node_class and (node_class.startswith("K2Node") or node_class.startswith("EdGraphNode") or "Node" in node_class):
                    node_idx = export_map.index(node_export) + 1
                    already_collected = any(
                        getattr(n, '_export_index', None) == node_idx
                        for n in nodes
                    )
                    if already_collected:
                        continue
                    try:
                        node = read_ue_graph_node(archive, name_map, summary, export_map, import_map, node_export, linker)
                        node._export_index = node_idx  # tag for dedup
                        nodes.append(node)
                    except (ParseError, struct.error, OSError, ValueError, KeyError):
                        nodes.append(UEdGraphNode(
                            node_guid="",
                            node_pos_x=0,
                            node_pos_y=0,
                            node_comment="",
                            pins=[],
                            class_name=node_class or "",
                            node_data={"_parse_error": True, "node_name": node_export.object_name},
                        ))
                        nodes[-1]._export_object_name = node_export.object_name

    # -- 3. bEditable / SubGraphs -- from PropertyTag or fallback --
    # These fields may be WITH_EDITORONLY_DATA and absent from PropertyTag.
    b_editable = True  # default
    subgraph_indices: List[int] = []

    props = getattr(graph_export, "properties", None) or []
    for prop in props:
        pname = getattr(prop, "name", None) or (prop.get("name") if isinstance(prop, dict) else None)
        pvalue = getattr(prop, "value", None) or (prop.get("value") if isinstance(prop, dict) else None)
        if pname == "bEditable":
            b_editable = bool(pvalue) if pvalue is not None else True
        elif pname == "SubGraphs" and isinstance(pvalue, list):
            if len(pvalue) > MAX_SUBGRAPHS:
                logger.debug(
                    "SubGraphs count %d exceeds limit %d, truncating",
                    len(pvalue), MAX_SUBGRAPHS,
                )
                pvalue = pvalue[:MAX_SUBGRAPHS]
            subgraph_indices = [v for v in pvalue if isinstance(v, int) and v > 0]

    # 6. Parse subgraphs (merge SubGraphs array + AnimGraphNode nested subgraphs)
    subgraphs: List[UEdGraph] = []

    # 6a. Parse from SubGraphs array (directly serialized subgraph references)
    for pkg_idx in subgraph_indices:
        if pkg_idx <= 0 or pkg_idx > len(export_map):
            continue
        if pkg_idx in _parsed_indices:
            continue

        subgraph_export = export_map[pkg_idx - 1]
        subgraph_class = _gac(subgraph_export, import_map, export_map, linker) or ""

        if not (subgraph_class.endswith("Graph") or subgraph_class == "EdGraph" or subgraph_class == "UberEdGraph"):
            continue

        try:
            subgraph = read_ue_graph(
                archive, name_map, summary, export_map, import_map,
                subgraph_export, subgraph_class, pkg_idx, linker,
                _parsed_indices=_parsed_indices,
            )
            subgraphs.append(subgraph)
        except (struct.error, OSError, ValueError, KeyError) as e:
            logger.debug("Failed to parse SubGraphs entry %d: %s", pkg_idx, e)

    # 6b. Parse from AnimGraphNode node_data.subgraph_references
    for node in nodes:
        node_data = getattr(node, "node_data", None)
        if not isinstance(node_data, dict):
            continue

        subgraph_refs = node_data.get("subgraph_references", {})
        for ref_key, ref_info in subgraph_refs.items():
            if not isinstance(ref_info, dict) or "error" in ref_info:
                continue

            pkg_idx = ref_info.get("package_index", 0)
            if pkg_idx <= 0 or pkg_idx > len(export_map):
                continue
            if pkg_idx in _parsed_indices:
                continue

            subgraph_export = export_map[pkg_idx - 1]
            subgraph_class = _gac(subgraph_export, import_map, export_map, linker) or ""

            if not (subgraph_class.endswith("Graph") or subgraph_class == "EdGraph" or subgraph_class == "UberEdGraph"):
                continue

            try:
                subgraph = read_ue_graph(
                    archive, name_map, summary, export_map, import_map,
                    subgraph_export, subgraph_class, pkg_idx, linker,
                    _parsed_indices=_parsed_indices,
                )
                subgraph.graph_name = f"{node.node_comment or node.class_name}.{ref_key}"
                subgraphs.append(subgraph)
            except (struct.error, OSError, ValueError, KeyError) as e:
                logger.debug("Failed to parse subgraph %s: %s", ref_info.get("object_name", ""), e)

    return UEdGraph(
        graph_name=graph_export.object_name,
        graph_class=graph_class,
        schema=schema,
        nodes=nodes,
        graph_guid=graph_guid,
        b_editable=b_editable,
        subgraphs=subgraphs,
    )


# ============================================================================
# Backward-compatible re-exports from graph_pin.py and graph_node.py
#
# Import cycle is now broken: graph_pin.py and graph_node.py import shared
# helpers from graph_helpers.py (not from graph.py).  The re-exports below
# are safe one-way imports.
# ============================================================================

from uasset_read.serializers.graph_pin import (  # noqa: E402, F401
    read_ed_graph_pin_type,
    read_pin_reference,
    read_pin_array,
    read_ue_graph_pin,
)
from uasset_read.serializers.graph_node import (  # noqa: E402, F401
    read_ue_graph_node,
    create_node_from_archive,
    read_fmember_reference,
    read_k2node_call_function,
    read_k2node_event,
    read_k2node_knot,
    read_edgraph_node_comment,
    read_k2node_enhanced_input,
    read_k2node_functionentry,
    read_k2node_message,
    read_k2node_call_delegate,
    read_k2node_call_array_function,
    read_k2node_call_parent_function,
    read_k2node_function_result,
    read_k2node_create_widget,
    read_k2node_add_delegate,
    read_k2node_macro_instance,
    read_k2node_assign_delegate,
    read_k2node_get_data_table_row,
    read_k2node_load_asset,
    read_k2node_spawn_actor_from_class,
)
