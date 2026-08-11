"""Structured domain extractor -- extracts data from structured assets.

Structured assets (StaticMesh, Skeleton, AnimSequence, DataTable)
have well-defined internal structures that can be partially or fully parsed.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from uasset_read.semantic.ir import ContentNode

if TYPE_CHECKING:
    from uasset_read.models.ir import ExportIR


def extract_structured(export: ExportIR) -> ContentNode:
    """Extract data from a structured export.

    Args:
        export: ExportIR for a structured asset

    Returns:
        ContentNode tree with structured data
    """
    children: list[ContentNode] = []

    # Core metadata
    children.append(ContentNode(key="class_name", value=export.object_class))
    children.append(ContentNode(key="object_name", value=export.object_name))
    children.append(ContentNode(key="serial_size", value=export.serial_size))

    # Asset type data (domain-specific parsed data)
    if export.asset_type_data:
        for key, value in export.asset_type_data.items():
            if key == "parse_status":
                children.append(ContentNode(key="parse_status", value=value))
            elif key == "reference_skeleton":
                children.append(ContentNode(
                    key="reference_skeleton",
                    children=_dict_to_content_nodes(value),
                ))
            elif key == "retarget_sources":
                children.append(ContentNode(
                    key="retarget_sources",
                    children=_dict_to_content_nodes(value),
                ))
            elif key == "row_count":
                children.append(ContentNode(key="row_count", value=value))
            elif key == "rows":
                # Rows are too large to inline; show count only
                children.append(ContentNode(
                    key="row_sample_count",
                    value=len(value) if isinstance(value, list) else 0,
                ))
            elif key == "guid":
                children.append(ContentNode(key="guid", value=value))

    # Sort by key for deterministic output
    children.sort(key=lambda c: c.key)

    return ContentNode(key="root", children=tuple(children))


def _dict_to_content_nodes(data: dict | list) -> tuple[ContentNode, ...]:
    """Convert a dict or list to ContentNode children."""
    if isinstance(data, dict):
        return tuple(
            ContentNode(
                key=str(k),
                value=v if not isinstance(v, (dict, list)) else None,
                children=_dict_to_content_nodes(v) if isinstance(v, (dict, list)) else None,
            )
            for k, v in sorted(data.items(), key=lambda x: str(x[0]))
        )
    if isinstance(data, list):
        return tuple(
            ContentNode(
                key=str(i),
                value=v if not isinstance(v, (dict, list)) else None,
                children=_dict_to_content_nodes(v) if isinstance(v, (dict, list)) else None,
            )
            for i, v in enumerate(data)
        )
    return ()
