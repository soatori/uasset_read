"""Graph domain extractor — Material, SoundCue, Niagara assets.

Returns a plain dict for SemanticIR.content. No ContentNode usage.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from uasset_read.semantic.models import EvidenceEntry

if TYPE_CHECKING:
    from uasset_read.models.ir import ExportIR
    from uasset_read.semantic.coverage import CoverageModel


def extract_graph(
    export: ExportIR,
    coverage: CoverageModel,
    evidence_list: list[EvidenceEntry] | None = None,
) -> dict:
    """Extract graph domain data from an export.

    Handles Material, SoundCue, and Niagara asset types that carry
    UEdGraph-based data on the export.

    Args:
        export: The primary export IR.
        coverage: Coverage tracker — calls ``track()`` for each data scope.
        evidence_list: Optional mutable list for debug evidence entries.

    Returns:
        A dict suitable for ``SemanticIR.content``.
    """
    # -- graph_metadata: always available if export exists --
    graph_metadata: dict = {
        "class_name": export.object_class or "",
        "object_name": export.object_name or "",
        "serial_size": export.serial_size,
    }
    coverage.track("graph_metadata", True)

    # -- asset_type_data: only if present on the export --
    asset_type_data: dict | None = None
    atd = export.asset_type_data
    has_atd = isinstance(atd, dict) and len(atd) > 0
    if has_atd:
        asset_type_data = {}
        for key in (
            "parse_status",
            "first_node",
            "volume_multiplier",
            "pitch_multiplier",
            "node_count",
            "raw_offset",
            "sample_size",
        ):
            if key in atd:  # type: ignore[operator]
                asset_type_data[key] = atd[key]  # type: ignore[index]
    coverage.track("asset_type_data", has_atd)

    # -- graphs: only if present on the export --
    graphs_data: list[dict] = []
    graphs = export.graphs
    has_graphs = isinstance(graphs, list) and len(graphs) > 0
    if has_graphs:
        for g in graphs:
            graphs_data.append({
                "name": g.graph_name,
                "node_count": len(g.nodes),
            })
    coverage.track("graphs", has_graphs)

    # -- evidence (debug only) --
    if evidence_list is not None:
        evidence_list.append(EvidenceEntry(key="export_index", value=export.index))

    # -- assemble result with sorted keys for determinism --
    result: dict = {
        "graph_metadata": graph_metadata,
    }
    if asset_type_data is not None:
        result["asset_type_data"] = asset_type_data
    if graphs_data:
        result["graphs"] = graphs_data

    return result
