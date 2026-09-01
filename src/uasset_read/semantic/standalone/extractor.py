"""Standalone types semantic content extractor (#557h).

Dispatches on object_class for SubsurfaceProfile, CurveFloat, and FoliageType.
"""

from __future__ import annotations

from uasset_read.semantic.asset_data import class_extractor, pick

_SUBSURFACE_KEYS = (
    "surface_albedo",
    "mean_free_path",
    "mean_free_path_dist",
    "subsurface_color",
    "boundary_color_bleed",
    "extinction_scale",
    "normal_scale",
    "custom_profile_curve",
)
_FOLIAGE_KEYS = (
    "mesh_ref",
    "material_refs",
    "density",
    "scaling",
    "scale_min",
    "scale_max",
    "collision_radius",
    "height_range_min",
    "height_range_max",
)


def _build_curve(data: dict, cov, _object_class: str) -> dict:
    keys = data.get("keys", [])
    key_count = data.get("key_count", len(keys))

    curve_data: dict = {"key_count": key_count, **pick(data, ("pre_infinity_extrap", "post_infinity_extrap"))}
    cov.track("curve_data", key_count > 0)

    if keys:
        curve_data["keys"] = keys
    return {"standalone": {"curve_data": curve_data}}


# (out_key, source, coverage key, mode) section tables per class; see asset_data.
_CLASSES = {
    "SubsurfaceProfile": (("profile_properties", _SUBSURFACE_KEYS, "profile_properties", "summary"),),
    "FoliageType": (("foliage_properties", _FOLIAGE_KEYS, "foliage_properties", "summary"),),
    "FoliageType_InstancedStaticMesh": (("foliage_properties", _FOLIAGE_KEYS, "foliage_properties", "summary"),),
    "CurveFloat": _build_curve,
    "CurveLinearColor": _build_curve,
    "CurveVector": _build_curve,
}

build_standalone_content = class_extractor("standalone", _CLASSES)
