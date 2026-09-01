"""Animation semantic content extractor (#557f).

Dispatches on object_class for AnimSequence, AnimMontage, PoseAsset, AnimCurveCompressionSettings.
"""

from __future__ import annotations

from uasset_read.semantic.asset_data import class_extractor, key


def _tracks(data: dict) -> dict:
    """Collect translation/rotation/scale track dicts under their track type."""
    tracks: dict = {}
    for track_type in ("translation", "rotation", "scale"):
        track_data = data.get(f"{track_type}_tracks") or data.get(track_type)
        if track_data and isinstance(track_data, dict):
            tracks[track_type] = track_data
    return tracks


# (out_key, source, coverage key, mode) section tables per class; see asset_data.
_ANIM_SEQUENCE = (
    (
        "anim_summary",
        (
            "frame_count",
            "frame_rate",
            "duration",
            "bone_track_count",
            "curve_count",
            "motion_extractor_count",
            "has_additive_animation",
            "has_root_motion",
        ),
        "anim_summary",
        "summary",
    ),
    ("tracks", _tracks, "tracks", "section"),
    ("compression", key("compression"), "compression", "section"),
)

_ANIM_MONTAGE = (
    (
        "montage_summary",
        ("slot_count", "section_count", "branching_point_count", "blend_in_time", "blend_out_time", "duration"),
        "montage_summary",
        "summary",
    ),
    ("", ("slots", "sections", "branching_points"), None, "raw"),
)

_POSE_ASSET = (
    ("pose_summary", ("pose_count", "blend_pose_count", "has_scale"), "pose_summary", "summary"),
    ("poses", key("poses", []), "poses", "section"),
)

_COMPRESSION_SETTINGS = (
    ("compression_settings", ("codec_class", "max_curve_count", "error_threshold"), "compression_settings", "summary"),
)


build_anim_content = class_extractor(
    "anim",
    {
        "AnimSequence": _ANIM_SEQUENCE,
        "AnimMontage": _ANIM_MONTAGE,
        "PoseAsset": _POSE_ASSET,
        "AnimCurveCompressionSettings": _COMPRESSION_SETTINGS,
    },
)
