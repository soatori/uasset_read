"""UEdGraph 序列化器 — Graph 容器读取。"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING, List, Optional

if TYPE_CHECKING:
    from uasset_read.archive import FArchive
    from uasset_read.serializers.package_summary import PackageFileSummary
    from uasset_read.serializers.object_resources import ObjectExport, ObjectImport
    from uasset_read.link.linker import PackageLinker

from uasset_read.constants import MAX_NODES_PER_GRAPH
from uasset_read.exceptions import ParseError
from uasset_read.models.core import UEdGraphNode
from uasset_read.serializers.object_resources import PackageIndex
from uasset_read.serializers.graph._common import _rcn, _gac, _read_guid
from uasset_read.serializers.graph.nodes import read_ue_graph_node

logger = logging.getLogger(__name__)


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
) -> "UEdGraph":
    """读取 UEdGraph 容器（EdGraph.cpp）。

    参考 UE C++ UEdGraph::Serialize() 实现
    """
    from uasset_read.models.core import UEdGraph

    archive.seek(graph_export.serial_offset)

    # 1. Schema
    schema_index = archive.read_i32()
    schema: Optional[str] = None
    if schema_index != 0:
        schema = _rcn(PackageIndex(schema_index), import_map, export_map, linker)

    # 2. Nodes array
    nodes_count = archive.read_i32()
    if nodes_count < 0:
        raise ParseError(f"Invalid nodes_count {nodes_count} (negative) at graph {graph_export.object_name}")
    if nodes_count > MAX_NODES_PER_GRAPH:
        raise ParseError(f"nodes_count {nodes_count} exceeds MAX_NODES_PER_GRAPH {MAX_NODES_PER_GRAPH} at graph {graph_export.object_name}")

    nodes: List[UEdGraphNode] = []
    failed_nodes: List[str] = []

    for _ in range(nodes_count):
        node_index = archive.read_i32()
        if node_index > 0 and node_index <= len(export_map):
            node_export = export_map[node_index - 1]
            try:
                node = read_ue_graph_node(archive, name_map, summary, export_map, import_map, node_export, linker)
                node._export_index = node_index  # tag for dedup
                nodes.append(node)
            except ParseError:
                failed_nodes.append(node_export.object_name)

    # UE 5.x fallback: always scan export_map for nodes whose outer is this graph.
    # Main path nodes_count can be incomplete due to UE5 serialization differences;
    # fallback discovery via outer_index scan catches the rest. Dedup by _export_index.
    if graph_export_idx > 0:
        if len(nodes) > 0:
            logger.debug("Main path collected %d nodes but fallback still triggered — merging with outer_index scan", len(nodes))

        # Build outer_index -> exports mapping for O(1) lookup
        outer_to_exports: Dict[int, List[Tuple[int, Any]]] = {}
        for idx, node_export in enumerate(export_map):
            outer_idx = node_export.outer_index.index
            if outer_idx not in outer_to_exports:
                outer_to_exports[outer_idx] = []
            outer_to_exports[outer_idx].append((idx + 1, node_export))

        # Use pre-built mapping instead of O(N) scan
        for node_idx, node_export in outer_to_exports.get(graph_export_idx, []):
            node_class = _gac(node_export, import_map, export_map, linker)
            if node_class and (node_class.startswith("K2Node") or node_class.startswith("EdGraphNode") or "Node" in node_class):
                # Skip if already collected by main path (same export index)
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
                except ParseError:
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

    # 3. GraphGuid
    graph_guid = _read_guid(archive, uppercase=False)

    # 4. bEditable
    b_editable = archive.read_u8() != 0

    return UEdGraph(
        graph_name=graph_export.object_name,
        graph_class=graph_class,
        schema=schema,
        nodes=nodes,
        graph_guid=graph_guid,
        b_editable=b_editable,
    )
