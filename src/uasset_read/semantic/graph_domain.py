"""Graph domain extractor -- extracts data from graph-based assets.

Graph assets (Material, SoundCue, Niagara) contain node/pin graphs
that describe their behavior visually.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from uasset_read.semantic.ir import ContentNode

if TYPE_CHECKING:
    from uasset_read.models.ir import ExportIR


def extract_graph(export: ExportIR) -> ContentNode:
    """Extract data from a graph export.

    Args:
        export: ExportIR for a graph asset

    Returns:
        ContentNode tree with graph data
    """
    children: list[ContentNode] = []

    # Core metadata
    children.append(ContentNode(key="class_name", value=export.object_class))
    children.append(ContentNode(key="object_name", value=export.object_name))
    children.append(ContentNode(key="serial_size", value=export.serial_size))

    # Asset type data (SoundCue specific, Material/Niagara opaque)
    if export.asset_type_data:
        for key in ("parse_status", "first_node", "volume_multiplier",
                     "pitch_multiplier", "node_count", "raw_offset", "sample_size"):
            if key in export.asset_type_data:
                children.append(ContentNode(key=key, value=export.asset_type_data[key]))

    # Graphs
    if export.graphs:
        graph_nodes: list[ContentNode] = []
        for i, graph in enumerate(export.graphs):
            graph_children: list[ContentNode] = []
            graph_children.append(ContentNode(key="name", value=graph.graph_name))
            graph_children.append(ContentNode(key="node_count", value=len(graph.nodes)))
            graph_nodes.append(ContentNode(
                key=str(i),
                children=tuple(graph_children),
            ))
        children.append(ContentNode(key="graphs", children=tuple(graph_nodes)))

    # Sort by key for deterministic output
    children.sort(key=lambda c: c.key)

    return ContentNode(key="root", children=tuple(children))
