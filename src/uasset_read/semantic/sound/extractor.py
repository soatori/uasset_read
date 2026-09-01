"""Sound semantic content extractor (#557c).

Dispatches on object_class to build content for SoundWave, SoundCue, or SoundAttenuation.
"""

from __future__ import annotations

from uasset_read.semantic.asset_data import class_extractor, pick

_WAVE_RESOURCE_KEYS = (
    "duration",
    "sample_rate",
    "channel_count",
    "format",
    "compression_quality",
    "sound_group",
    "loading_behavior",
)
_WAVE_BULK_KEYS = ("total_pcm_bytes", "compressed_bytes", "chunk_count", "is_streaming")
_CUE_META_KEYS = ("node_count", "mixer_node_count", "wave_player_count")
_ATTEN_KEYS = (
    "attenuation_shape",
    "attenuation_radius",
    "falloff_function",
    "spatialization_algorithm",
    "battenuate_over_distance",
    "battenuate_over_time",
    "distance_algorithm",
)


def _build_sound_cue(data: dict, cov, _object_class: str) -> dict:
    cov.track("resource_properties", False)
    meta: dict = {"class_name": "SoundCue", **pick(data, _CUE_META_KEYS)}
    cov.track("graph_metadata", True)
    return {"sound": {"graph_metadata": meta}}


def _build_sound_attenuation(data: dict, cov, _object_class: str) -> dict:
    # Callable spec (not a section table) because the original also tracks
    # resource_properties=False unconditionally before building the section.
    cov.track("resource_properties", False)
    props = pick(data, _ATTEN_KEYS)
    cov.track("attenuation_properties", len(props) > 0)
    return {"sound": {"attenuation_properties": props}}


# (out_key, source, coverage key, mode) section tables per class; see asset_data.
build_sound_content = class_extractor(
    "sound",
    {
        "SoundWave": (
            ("resource_properties", _WAVE_RESOURCE_KEYS, "resource_properties", "section"),
            ("bulk_summary", _WAVE_BULK_KEYS, "bulk_summary", "section"),
        ),
        "SoundCue": _build_sound_cue,
        "SoundAttenuation": _build_sound_attenuation,
    },
    miss_cov="resource_properties",
)
