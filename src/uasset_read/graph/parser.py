from __future__ import annotations

"""Blueprint graph parsing entry — extract all EdGraph/UberEdGraph from ExportMap.

Equivalent migration from uasset_read.py L3095-3143.
"""

from typing import TYPE_CHECKING, List, Optional

if TYPE_CHECKING:
    from uasset_read.archive import FArchive
    from uasset_read.serializers.package_summary import PackageFileSummary
    from uasset_read.serializers.object_resources import ObjectExport, ObjectImport
    from uasset_read.link.linker import PackageLinker

import logging

from uasset_read.constants import PKG_Cooked
from uasset_read.serializers.object_resources import get_asset_class
from uasset_read.serializers.graph import read_ue_graph
from uasset_read.models.core import UEdGraph

logger = logging.getLogger(__name__)

# Known EdGraph subclass names (used for graph type matching)
# Includes engine built-in subclasses and common custom graph types
EDGRAPH_CLASS_NAMES = frozenset({
    "EdGraph",
    "UberEdGraph",
    # Animation graphs
    "AnimGraph",
    "AnimBlueprintGeneratedClass",
    # Control Rig graphs
    "ControlRigGraph",
    "RigGraph",
    # Material graphs
    "MaterialGraph",
    "MaterialGraphEdNode",
    # Particle system graphs
    "CascadeParticleSystemGraph",
    # Niagara graphs
    "NiagaraGraph",
    "NiagaraScript",
    # Custom graph types (common prefix matching)
    "K2Node_Graph",
})


def _validate_graph_export_offset(export, archive_size: int) -> bool:
    """Validate whether a graph export's serialization offset is within valid range.

    When serial_offset is 0 and serial_size > 0, the offset is abnormal (non-Default__ export).
    When serial_offset + serial_size exceeds archive boundary, data is truncated.

    Args:
        export: ObjectExport instance
        archive_size: total archive file size (bytes)

    Returns:
        True indicates offset is valid and safe to read
    """
    serial_offset = getattr(export, "serial_offset", 0)
    serial_size = getattr(export, "serial_size", 0)

    if serial_size == 0:
        return True  # empty export, skip check

    # Check for negative values
    if serial_offset < 0 or serial_size < 0:
        logger.warning(
            "Graph export '%s' offset abnormal: offset=%d, size=%d",
            export.object_name, serial_offset, serial_size,
        )
        return False

    # Offset should not be 0 (unless it is a special Default__ export)
    if serial_offset == 0 and not str(getattr(export, "object_name", "")).startswith("Default__"):
        logger.warning(
            "Graph export '%s' serial_offset=0 and serial_size=%d, offset abnormal",
            export.object_name, serial_size,
        )
        return False

    # Check if exceeding archive boundary
    if archive_size > 0 and serial_offset + serial_size > archive_size:
        logger.warning(
            "Graph export '%s' offset out of bounds: offset=%d + size=%d > archive_size=%d",
            export.object_name, serial_offset, serial_size, archive_size,
        )
        return False

    return True


def extract_blueprint_graphs(
    archive: FArchive,
    summary: PackageFileSummary,
    name_map: List[str],
    import_map: List[ObjectImport],
    export_map: List[ObjectExport],
    linker: Optional["PackageLinker"] = None,
) -> List[UEdGraph]:
    """
    Extract Blueprint graphs from ExportMap (equivalent migration from uasset_read.py L3095-3143).

    Iterates ExportMap; exports whose ClassIndex resolves to contain "EdGraph" or "UberEdGraph"
    are treated as graph objects. For each graph, calls read_ue_graph to fully parse the
    Graph->Node->Pin three-layer structure.

    Safety check: PKG_Cooked check avoids parsing stripped assets.

    Args:
        archive: FArchive binary reader
        summary: PackageFileSummary containing package_flags
        name_map: name table list
        import_map: import table list (for ClassIndex resolution)
        export_map: export table list (for ClassIndex resolution)

    Returns:
        List[UEdGraph]: list of detected graphs
    """
    graphs: List[UEdGraph] = []

    # PKG_Cooked check — cooked assets have no graph data
    is_cooked = (summary.package_flags & PKG_Cooked) != 0
    if is_cooked:
        return []

    # Get archive size for offset validation
    archive_size = 0
    if archive is not None:
        try:
            archive_size = archive.total_size()
        except (OSError, AttributeError):
            archive_size = 0

    # Iterate ExportMap to find EdGraph/UberEdGraph type exports
    for export_idx, export in enumerate(export_map):
        class_name = get_asset_class(export, import_map, export_map)

        # Extended graph type matching: exact match + suffix match (covers custom graph subclasses)
        is_graph_type = (
            class_name is not None
            and (
                class_name in EDGRAPH_CLASS_NAMES
                or class_name.endswith("Graph")
                or class_name.endswith("EdGraph")
            )
        )

        if class_name and is_graph_type:
            # Validate graph export offset is within valid range
            if not _validate_graph_export_offset(export, archive_size):
                logger.warning(
                    "Skipping graph export '%s' (offset validation failed)",
                    export.object_name,
                )
                continue

            graph = read_ue_graph(
                archive, name_map, summary,
                export_map, import_map,
                export, class_name, export_idx + 1, linker  # 1-based index
            )
            graphs.append(graph)

    return graphs
