"""Blueprint graph decode-pass support.

The handler layer never touches the archive, but editor-saved graph pins
are not exports — they are serialized inside each node export's serial region
after the tagged property stream.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from uasset_read.archive import FArchive
    from uasset_read.serializers.object_resources import ObjectExport
    from uasset_read.serializers.package_summary import PackageFileSummary

logger = logging.getLogger(__name__)

# Hard caps on converted output.
MAX_GRAPHS_PER_PACKAGE = 512
MAX_NODES_PER_GRAPH_OUTPUT = 512
MAX_PINS_PER_NODE_OUTPUT = 64


def _validate_graph_export_offset(export, archive_size: int) -> bool:
    """Validate whether a graph export's serialization offset is within valid range."""
    serial_offset = getattr(export, "serial_offset", 0)
    serial_size = getattr(export, "serial_size", 0)

    if serial_size == 0:
        return True  # empty export, skip check

    # Check for negative values
    if serial_offset < 0 or serial_size < 0:
        return False

    # Check for overflow
    if serial_offset + serial_size > archive_size:
        return False

    return True


def read_blueprint_graphs(
    archive: "FArchive",
    exports: list["ObjectExport"],
    summary: "PackageFileSummary",
) -> list[dict[str, Any]]:
    """Read blueprint graphs from exports.

    Returns a list of graph dicts, each containing nodes and pins.
    """
    from uasset_read.serializers.graph import read_graph
    from uasset_read.serializers.graph_node import read_graph_node
    from uasset_read.serializers.graph_pin import read_graph_pin

    graphs: list[dict[str, Any]] = []
    archive_size = archive.total_size()

    for export in exports:
        if not _validate_graph_export_offset(export, archive_size):
            logger.warning(
                "Skipping graph export with invalid offset: %s",
                getattr(export, "object_name", "unknown"),
            )
            continue

        # Read the graph from the export's serial region
        graph = read_graph(archive, export)
        if graph is not None:
            graphs.append(graph)

            # Enforce caps
            if len(graphs) >= MAX_GRAPHS_PER_PACKAGE:
                logger.warning(
                    "Reached maximum graphs per package (%d)",
                    MAX_GRAPHS_PER_PACKAGE,
                )
                break

    return graphs
