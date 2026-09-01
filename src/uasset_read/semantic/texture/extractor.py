"""Texture semantic content extractor (#557b).

Reads from ExportIR.asset_type_data (PropertyMetadataHandler output).
Projects resource properties and bulk data summary for Texture2D/TextureCube.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from uasset_read.semantic.asset_data import pick

if TYPE_CHECKING:
    from uasset_read.models.ir import PackageIR, ExportIR

_RESOURCE_KEYS = (
    "size_x",
    "size_y",
    "format",
    "num_mips",
    "is_streaming",
    "streaming_channels",
    "lod_group",
    "address_x",
    "address_y",
    "filter",
    "srgb",
)

_BULK_KEYS = ("total_mip_bytes", "compressed_mip_bytes", "chunk_count", "first_mip")


def build_texture_content(
    package_ir: "PackageIR",
    export_ir: "ExportIR",
    coverage_model,
) -> dict:
    """Build the Texture domain content dict."""
    asset_type_data = getattr(export_ir, "asset_type_data", None)

    if not asset_type_data or not isinstance(asset_type_data, dict):
        coverage_model.track("resource_properties", False)
        return {}

    # Resource properties
    resource_properties: dict = pick(asset_type_data, _RESOURCE_KEYS)
    has_resources = len(resource_properties) > 0
    coverage_model.track("resource_properties", has_resources)

    # Bulk summary
    bulk_summary: dict = pick(asset_type_data, _BULK_KEYS)
    has_bulk = len(bulk_summary) > 0
    coverage_model.track("bulk_summary", has_bulk)

    # TextureCube: add cube_face_count
    object_class = getattr(export_ir, "object_class", "") or ""
    if "Cube" in object_class:
        resource_properties["cube_face_count"] = 6

    content: dict = {"texture": {}}
    if has_resources:
        content["texture"]["resource_properties"] = resource_properties
    if has_bulk:
        content["texture"]["bulk_summary"] = bulk_summary

    return content
