"""Movie semantic content extractor (#557i).

Reads from ExportIR.asset_type_data for MovieScene and LevelSequence assets.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from uasset_read.models.ir import PackageIR, ExportIR


def build_movie_content(
    package_ir: "PackageIR",
    export_ir: "ExportIR",
    coverage_model,
    evidence_list,
) -> dict:
    """Build the Movie domain content dict."""
    asset_type_data = getattr(export_ir, "asset_type_data", None)

    if not asset_type_data or not isinstance(asset_type_data, dict):
        coverage_model.track("scene_summary", False)
        return {}

    # MovieSceneHandler stores data under "movie_scene" key
    scene_data = asset_type_data.get("movie_scene", asset_type_data)

    summary: dict = {}
    for key in ("track_count", "spawnable_count", "possessable_count", "binding_count", "marked_frame_count"):
        val = scene_data.get(key)
        if val is not None:
            summary[key] = val

    # Frame rate from MovieSceneHandler
    display_rate = scene_data.get("display_rate")
    if display_rate and isinstance(display_rate, dict):
        num = display_rate.get("numerator", 0)
        den = display_rate.get("denominator", 1)
        if den > 0:
            summary["frame_rate"] = round(num / den, 2)

    coverage_model.track("scene_summary", len(summary) > 0)

    # Track classes
    track_classes = scene_data.get("track_classes", [])
    coverage_model.track("tracks", len(track_classes) > 0)

    result: dict = {"movie": {"scene_summary": summary}}
    if track_classes:
        result["movie"]["tracks"] = [{"type": tc} for tc in track_classes]

    return result
