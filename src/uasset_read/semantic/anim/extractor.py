"""Animation semantic content extractor (#557f).

Dispatches on object_class for AnimSequence, AnimMontage, PoseAsset, AnimCurveCompressionSettings.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from uasset_read.models.ir import PackageIR, ExportIR


def _build_anim_sequence(asset_type_data: dict, cov) -> dict:
    summary: dict = {}
    for key in ("frame_count", "frame_rate", "duration", "bone_track_count",
                "curve_count", "motion_extractor_count", "has_additive_animation", "has_root_motion"):
        val = asset_type_data.get(key)
        if val is not None:
            summary[key] = val
    cov.track("anim_summary", len(summary) > 0)

    tracks: dict = {}
    for track_type in ("translation", "rotation", "scale"):
        track_data = asset_type_data.get(f"{track_type}_tracks") or asset_type_data.get(track_type)
        if track_data and isinstance(track_data, dict):
            tracks[track_type] = track_data
    cov.track("tracks", len(tracks) > 0)

    compression = asset_type_data.get("compression")
    cov.track("compression", compression is not None)

    result: dict = {"anim": {"anim_summary": summary}}
    if tracks:
        result["anim"]["tracks"] = tracks
    if compression:
        result["anim"]["compression"] = compression
    return result


def _build_anim_montage(asset_type_data: dict, cov) -> dict:
    summary: dict = {}
    for key in ("slot_count", "section_count", "branching_point_count",
                "blend_in_time", "blend_out_time", "duration"):
        val = asset_type_data.get(key)
        if val is not None:
            summary[key] = val
    cov.track("montage_summary", len(summary) > 0)

    result: dict = {"anim": {"montage_summary": summary}}
    for section in ("slots", "sections", "branching_points"):
        data = asset_type_data.get(section)
        if data:
            result["anim"][section] = data
    return result


def _build_pose_asset(asset_type_data: dict, cov) -> dict:
    summary: dict = {}
    for key in ("pose_count", "blend_pose_count", "has_scale"):
        val = asset_type_data.get(key)
        if val is not None:
            summary[key] = val
    cov.track("pose_summary", len(summary) > 0)

    poses = asset_type_data.get("poses", [])
    cov.track("poses", len(poses) > 0)

    result: dict = {"anim": {"pose_summary": summary}}
    if poses:
        result["anim"]["poses"] = poses
    return result


def _build_compression_settings(asset_type_data: dict, cov) -> dict:
    settings: dict = {}
    for key in ("codec_class", "max_curve_count", "error_threshold"):
        val = asset_type_data.get(key)
        if val is not None:
            settings[key] = val
    cov.track("compression_settings", len(settings) > 0)
    return {"anim": {"compression_settings": settings}}


def build_anim_content(
    package_ir: "PackageIR",
    export_ir: "ExportIR",
    coverage_model,
    evidence_list,
) -> dict:
    asset_type_data = getattr(export_ir, "asset_type_data", None)
    object_class = getattr(export_ir, "object_class", "") or ""

    if not asset_type_data or not isinstance(asset_type_data, dict):
        return {}

    if object_class == "AnimSequence":
        return _build_anim_sequence(asset_type_data, coverage_model)
    elif object_class == "AnimMontage":
        return _build_anim_montage(asset_type_data, coverage_model)
    elif object_class == "PoseAsset":
        return _build_pose_asset(asset_type_data, coverage_model)
    elif object_class == "AnimCurveCompressionSettings":
        return _build_compression_settings(asset_type_data, coverage_model)
    else:
        return {}
