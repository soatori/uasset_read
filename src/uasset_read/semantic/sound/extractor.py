"""Sound semantic content extractor (#557c).

Dispatches on object_class to build content for SoundWave, SoundCue, or SoundAttenuation.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from uasset_read.models.ir import PackageIR, ExportIR

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


def _build_sound_wave(asset_type_data: dict, cov) -> dict:
    resource: dict = {}
    for key in _WAVE_RESOURCE_KEYS:
        val = asset_type_data.get(key)
        if val is not None:
            resource[key] = val
    cov.track("resource_properties", len(resource) > 0)

    bulk: dict = {}
    for key in _WAVE_BULK_KEYS:
        val = asset_type_data.get(key)
        if val is not None:
            bulk[key] = val
    cov.track("bulk_summary", len(bulk) > 0)

    result: dict = {"sound": {}}
    if resource:
        result["sound"]["resource_properties"] = resource
    if bulk:
        result["sound"]["bulk_summary"] = bulk
    return result


def _build_sound_cue(asset_type_data: dict, cov) -> dict:
    cov.track("resource_properties", False)
    meta: dict = {"class_name": "SoundCue"}
    for key in _CUE_META_KEYS:
        val = asset_type_data.get(key)
        if val is not None:
            meta[key] = val
    cov.track("graph_metadata", True)
    return {"sound": {"graph_metadata": meta}}


def _build_sound_attenuation(asset_type_data: dict, cov) -> dict:
    cov.track("resource_properties", False)
    props: dict = {}
    for key in _ATTEN_KEYS:
        val = asset_type_data.get(key)
        if val is not None:
            props[key] = val
    cov.track("attenuation_properties", len(props) > 0)
    return {"sound": {"attenuation_properties": props}}


def build_sound_content(
    package_ir: "PackageIR",
    export_ir: "ExportIR",
    coverage_model,
    evidence_list,
) -> dict:
    asset_type_data = getattr(export_ir, "asset_type_data", None)
    object_class = getattr(export_ir, "object_class", "") or ""

    if not asset_type_data or not isinstance(asset_type_data, dict):
        coverage_model.track("resource_properties", False)
        return {}

    if object_class == "SoundWave":
        return _build_sound_wave(asset_type_data, coverage_model)
    elif object_class == "SoundCue":
        return _build_sound_cue(asset_type_data, coverage_model)
    elif object_class == "SoundAttenuation":
        return _build_sound_attenuation(asset_type_data, coverage_model)
    else:
        coverage_model.track("resource_properties", False)
        return {}
