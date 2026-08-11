"""Resource domain extractor — extracts metadata from resource assets.

Resource assets (Texture2D, SoundWave) output only metadata:
dimensions, format, duration, sizes, SHA-256. No pixel/audio arrays.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from uasset_read.semantic.ir import ContentNode

if TYPE_CHECKING:
    from uasset_read.models.ir import ExportIR


def extract_resource(export: ExportIR) -> ContentNode:
    """Extract metadata from a resource export.

    Args:
        export: ExportIR for a resource asset

    Returns:
        ContentNode tree with resource metadata
    """
    children: list[ContentNode] = []

    # Core metadata
    children.append(ContentNode(key="class_name", value=export.object_class))
    children.append(ContentNode(key="object_name", value=export.object_name))
    children.append(ContentNode(key="serial_size", value=export.serial_size))

    # Extract properties as metadata (only known resource-relevant keys)
    _RESOURCE_PROPERTY_KEYS = frozenset({
        "SizeX", "SizeY", "SizeZ", "NumMips", "Format",
        "bHasAlphaChannel", "SRGB", "LODGroup",
        "SampleRate", "NumChannels", "Duration",
    })
    for prop in export.properties:
        if prop.name in _RESOURCE_PROPERTY_KEYS:
            children.append(ContentNode(key=prop.name, value=prop.value))

    # Asset type data (parse_status, raw_offset, sample_size)
    if export.asset_type_data:
        for key in ("parse_status", "raw_offset", "sample_size"):
            if key in export.asset_type_data:
                children.append(ContentNode(key=key, value=export.asset_type_data[key]))

    # Sort by key for deterministic output
    children.sort(key=lambda c: c.key)

    return ContentNode(key="root", children=tuple(children))
