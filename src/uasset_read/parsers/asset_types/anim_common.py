"""Shared animation parsing module

Extracted from anim_blueprint.py / anim_montage.py / anim_sequence.py duplicate logic:
- parse_anim_notifies: animation notify array parsing
- parse_float_curve_names: float curve name parsing
- ensure_custom_data: export.custom_data initialization
"""

from typing import Any

from uasset_read.models.ir import AnimNotifyIR
from uasset_read.parsers.asset_types.property_extractor import (
    extract_object_ref,
    parse_dict_list,
)


def parse_anim_notifies(data: Any) -> list[AnimNotifyIR]:
    """Parse animation notify array (full field version)

    Extracts all AnimNotifyIR fields, including LinkedMontage / LinkedSequence object references.
    Shared implementation across three animation parsers.
    """

    def _parse_notify(notify_data: dict) -> AnimNotifyIR:
        notify = AnimNotifyIR(
            notify_name=notify_data.get("NotifyName", ""),
            trigger_time_offset=notify_data.get("TriggerTimeOffset", 0.0),
            end_trigger_time_offset=notify_data.get("EndTriggerTimeOffset", 0.0),
            trigger_weight_threshold=notify_data.get("TriggerWeightThreshold", 0.0),
            duration=notify_data.get("Duration", 0.0),
            notify_class=notify_data.get("NotifyClass"),
            notify_state_class=notify_data.get("NotifyStateClass"),
            montage_tick_type=notify_data.get("MontageTickType"),
            notify_trigger_chance=notify_data.get("NotifyTriggerChance", 1.0),
            notify_filter_type=notify_data.get("NotifyFilterType"),
            notify_filter_lod=notify_data.get("NotifyFilterLOD", 0),
            b_converted_from_branching_point=notify_data.get(
                "bConvertedFromBranchingPoint", False
            ),
            track_index=notify_data.get("TrackIndex", 0),
        )
        extract_object_ref(notify_data, "LinkedMontage", notify, "linked_montage")
        extract_object_ref(notify_data, "LinkedSequence", notify, "linked_sequence")
        return notify

    return parse_dict_list(data, _parse_notify)


def parse_float_curve_names(data: Any) -> list[str]:
    """Parse float curve name list

    Extracts the Name field from FloatCurves in the RawCurveData property.
    Shared implementation between anim_montage and anim_sequence.
    """

    def _parse_curve(curve: dict) -> str | None:
        name_data = curve.get("Name", {})
        if isinstance(name_data, dict):
            curve_name = name_data.get("Name", "")
            if curve_name:
                return curve_name
        return None

    if not isinstance(data, dict):
        return []

    float_curves = data.get("FloatCurves", [])
    return [name for name in parse_dict_list(float_curves, _parse_curve) if name]


def ensure_custom_data(export: Any) -> dict:
    """Ensure export has custom_data attribute and return it

    Initializes custom_data to an empty dict if not yet set on the export.
    Used by animation and MovieScene handlers to store parse results.
    """
    if not hasattr(export, "custom_data"):
        export.custom_data = {}
    return export.custom_data
