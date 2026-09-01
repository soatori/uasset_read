"""Skeleton semantic content extractor (#557).

Reads from ExportIR.asset_type_data (parse_skeleton output).
Projects bone hierarchy, retarget sources, and skeleton metadata.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from uasset_read.models.ir import PackageIR, ExportIR


def _build_bones(asset_type_data: dict) -> list[dict]:
    """Build bone list from reference_skeleton data."""
    ref_skeleton = asset_type_data.get("reference_skeleton", {})
    if not ref_skeleton:
        return []

    names = ref_skeleton.get("names", [])
    parents = ref_skeleton.get("parents", [])

    bones = []
    for i, name in enumerate(names):
        bone: dict = {
            "name": name,
            "parent_index": parents[i] if i < len(parents) else -1,
        }
        bones.append(bone)

    return bones


def _build_retarget_sources(asset_type_data: dict) -> list[dict]:
    """Build retarget sources list."""
    raw_sources = asset_type_data.get("retarget_sources", [])
    if not raw_sources:
        return []

    sources = []
    for src in raw_sources:
        source: dict = {
            "name": src.get("name", ""),
            "pose_name": src.get("pose_name", ""),
        }
        if "source_mesh" in src:
            source["source_mesh"] = src["source_mesh"]
        sources.append(source)

    return sources


def build_skeleton_content(
    package_ir: "PackageIR",
    export_ir: "ExportIR",
    coverage_model,
) -> dict:
    """Build the Skeleton domain content dict.

    Reads the manifest from ExportIR.asset_type_data and extracts
    bone hierarchy, retarget sources, and skeleton metadata.
    """
    asset_type_data = getattr(export_ir, "asset_type_data", None)

    if not asset_type_data or not isinstance(asset_type_data, dict):
        coverage_model.track("bone_hierarchy", False)
        return {}

    # Build bones from reference_skeleton
    bones = _build_bones(asset_type_data)
    has_bones = len(bones) > 0
    coverage_model.track("bone_hierarchy", has_bones)

    # Build retarget sources
    retarget_sources = _build_retarget_sources(asset_type_data)
    coverage_model.track("retarget_sources", len(retarget_sources) > 0)

    # Get GUID
    guid = asset_type_data.get("guid", "")

    content: dict = {"skeleton": {}}

    # bone_count at top level (contract: always present when skeleton data exists)
    content["skeleton"]["bone_count"] = len(bones)

    # Skeleton summary (optional metadata)
    skeleton_summary: dict = {}
    if guid:
        skeleton_summary["guid"] = guid
    if skeleton_summary:
        content["skeleton"]["skeleton_summary"] = skeleton_summary

    # Bones
    if has_bones:
        content["skeleton"]["bones"] = bones

    # Retarget sources
    if retarget_sources:
        content["skeleton"]["retarget_sources"] = retarget_sources

    # Hierarchy validation (from handler output)
    valid_hierarchy = asset_type_data.get("valid_hierarchy")
    if valid_hierarchy is not None:
        content["skeleton"]["valid_hierarchy"] = valid_hierarchy

    hierarchy_diagnostics = asset_type_data.get("hierarchy_diagnostics")
    if hierarchy_diagnostics:
        content["skeleton"]["hierarchy_diagnostics"] = hierarchy_diagnostics

    # Parse status (from handler output)
    parse_status = asset_type_data.get("parse_status")
    if parse_status and parse_status != "success":
        content["skeleton"]["parse_status"] = parse_status

    return content
