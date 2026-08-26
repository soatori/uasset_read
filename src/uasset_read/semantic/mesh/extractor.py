"""Mesh semantic content extractor (#557a).

Reads from ExportIR.asset_type_data (PropertyMetadataHandler output).
Projects mesh summary, material slots, and LOD info for StaticMesh and SkeletalMesh.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from uasset_read.models.ir import PackageIR, ExportIR


def _extract_bounds(properties: list) -> dict | None:
    """Extract bounding box from properties."""
    for prop in properties:
        if getattr(prop, "name", None) == "ExtendedBounds":
            value = getattr(prop, "value", None)
            if isinstance(value, dict):
                origin = value.get("origin") or value.get("Origin")
                extent = value.get("extent") or value.get("Extent")
                if origin and extent:
                    return {
                        "origin": {"x": origin.get("x", 0.0), "y": origin.get("y", 0.0), "z": origin.get("z", 0.0)},
                        "extent": {"x": extent.get("x", 0.0), "y": extent.get("y", 0.0), "z": extent.get("z", 0.0)},
                    }
    return None


def _extract_material_slots(properties: list) -> list[dict]:
    """Extract material slot assignments from properties."""
    materials = []
    for prop in properties:
        name = getattr(prop, "name", None)
        if name and "material" in name.lower():
            value = getattr(prop, "value", None)
            if isinstance(value, dict) and "SlotName" in value:
                materials.append(
                    {
                        "slot_index": len(materials),
                        "material_name": value.get("SlotName", ""),
                    }
                )
    return materials


def build_mesh_content(
    package_ir: "PackageIR",
    export_ir: "ExportIR",
    coverage_model,
    evidence_list,
) -> dict:
    """Build the Mesh domain content dict."""
    asset_type_data = getattr(export_ir, "asset_type_data", None)
    properties = getattr(export_ir, "properties", None) or []
    object_class = getattr(export_ir, "object_class", "") or ""

    if not asset_type_data or not isinstance(asset_type_data, dict):
        coverage_model.track("mesh_summary", False)
        return {}

    coverage_model.track("mesh_summary", True)

    mesh_summary: dict = {}
    for key in ("lod_count", "section_count", "vertex_count", "triangle_count", "material_count"):
        val = asset_type_data.get(key)
        if val is not None:
            mesh_summary[key] = val

    bounds = _extract_bounds(properties)
    if bounds:
        mesh_summary["bounds"] = bounds

    is_skeletal = object_class == "SkeletalMesh"
    if is_skeletal:
        for key in ("bone_count",):
            val = asset_type_data.get(key)
            if val is not None:
                mesh_summary[key] = val

    materials = _extract_material_slots(properties)
    has_materials = len(materials) > 0
    coverage_model.track("materials", has_materials)

    lod_info = asset_type_data.get("lod_info", [])
    has_lod = len(lod_info) > 0
    coverage_model.track("lod_info", has_lod)

    content: dict = {"mesh": {"mesh_summary": mesh_summary}}
    if has_materials:
        content["mesh"]["materials"] = materials
    if has_lod:
        content["mesh"]["lod_info"] = lod_info
    if is_skeletal:
        skeleton_ref = asset_type_data.get("skeleton_ref")
        physics_ref = asset_type_data.get("physics_asset_ref")
        if skeleton_ref is not None:
            content["mesh"]["skeleton_ref"] = skeleton_ref
        if physics_ref is not None:
            content["mesh"]["physics_asset_ref"] = physics_ref

    return content
