"""Standalone types semantic content extractor (#557h).

Dispatches on object_class for SubsurfaceProfile, CurveFloat, and FoliageType.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from uasset_read.models.ir import PackageIR, ExportIR


def _build_subsurface_profile(asset_type_data: dict, cov) -> dict:
    props: dict = {}
    for key in ("surface_albedo", "mean_free_path", "mean_free_path_dist",
                "subsurface_color", "boundary_color_bleed", "extinction_scale",
                "normal_scale", "custom_profile_curve"):
        val = asset_type_data.get(key)
        if val is not None:
            props[key] = val
    cov.track("profile_properties", len(props) > 0)
    return {"standalone": {"profile_properties": props}}


def _build_curve(asset_type_data: dict, cov) -> dict:
    keys = asset_type_data.get("keys", [])
    key_count = asset_type_data.get("key_count", len(keys))

    curve_data: dict = {
        "key_count": key_count,
    }
    for key in ("pre_infinity_extrap", "post_infinity_extrap"):
        val = asset_type_data.get(key)
        if val is not None:
            curve_data[key] = val

    cov.track("curve_data", key_count > 0)

    result: dict = {"standalone": {"curve_data": curve_data}}
    if keys:
        result["standalone"]["curve_data"]["keys"] = keys
    return result


def _build_foliage_type(asset_type_data: dict, cov) -> dict:
    props: dict = {}
    for key in ("mesh_ref", "material_refs", "density", "scaling",
                "scale_min", "scale_max", "collision_radius",
                "height_range_min", "height_range_max"):
        val = asset_type_data.get(key)
        if val is not None:
            props[key] = val
    cov.track("foliage_properties", len(props) > 0)
    return {"standalone": {"foliage_properties": props}}


def build_standalone_content(
    package_ir: "PackageIR",
    export_ir: "ExportIR",
    coverage_model,
    evidence_list,
) -> dict:
    asset_type_data = getattr(export_ir, "asset_type_data", None)
    object_class = getattr(export_ir, "object_class", "") or ""

    if not asset_type_data or not isinstance(asset_type_data, dict):
        coverage_model.track("profile_properties", False)
        return {}

    if object_class == "SubsurfaceProfile":
        return _build_subsurface_profile(asset_type_data, coverage_model)
    elif object_class in ("CurveFloat", "CurveLinearColor", "CurveVector"):
        return _build_curve(asset_type_data, coverage_model)
    elif object_class in ("FoliageType", "FoliageType_InstancedStaticMesh"):
        return _build_foliage_type(asset_type_data, coverage_model)
    else:
        coverage_model.track("profile_properties", False)
        return {}
