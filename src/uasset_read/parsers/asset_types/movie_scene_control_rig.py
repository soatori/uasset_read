"""MovieSceneControlRigParameterTrack Asset type handler

Parse UMovieSceneControlRigParameterTrack and UMovieSceneControlRigParameterSection:
- TrackName: FName (track name)
- ControlRig: TObjectPtr<UControlRig> (Control Rig reference)
- PriorityOrder: int32 (priority order)
- ControlsRotationOrder: TMap<FName, FControlRotationOrder> (control rotation order)
- Section count and parameter information

Format reference:
- Engine/Plugins/Animation/ControlRig/Source/ControlRig/Public/Sequencer/MovieSceneControlRigParameterTrack.h
- Engine/Plugins/Animation/ControlRig/Source/ControlRig/Public/Sequencer/MovieSceneControlRigParameterSection.h
"""
from __future__ import annotations

import logging
from types import SimpleNamespace
from typing import Any

from uasset_read.models.fallback import ExportParseStatus as ParseStatus
from uasset_read.parsers.asset_types.anim_common import ensure_custom_data
from uasset_read.parsers.asset_types.property_extractor import (
    build_properties_dict,
    extract_array_property,
    extract_property,
)

logger = logging.getLogger(__name__)


def _resolve_object_path(value: Any) -> Any:
    """Extract object_path from object reference property value (dict or fallback to str)."""
    if isinstance(value, dict):
        return value.get("object_path")
    return str(value)


def _resolve_class_name(value: Any) -> Any:
    """Extract class_name from object reference property value (dict or fallback to str)."""
    if isinstance(value, dict):
        return value.get("class_name")
    return str(value)


def _as_list(value: Any) -> list:
    """Ensure value is a list (return empty list if not)."""
    return value if isinstance(value, list) else []


class MovieSceneControlRigParameterTrackHandler:
    """MovieSceneControlRigParameterTrack Asset type handler"""

    # Reflection registration metadata
    export_type: str = "MovieSceneControlRigParameterTrack"
    priority: int = 100

    def handle(self, export: Any, context: Any) -> ParseStatus:
        """Handle MovieSceneControlRigParameterTrack export.

        Args:
            export: ObjectExport instance
            context: parse context

        Returns:
            ParseStatus: SUCCESS or PARTIAL
        """
        try:
            properties_list = getattr(export, "properties", [])
            if not properties_list:
                return ParseStatus.PARTIAL

            properties = build_properties_dict(properties_list)

            # Build ControlRig Track metadata
            ns = SimpleNamespace(
                type="MovieSceneControlRigParameterTrack",
                track_name=None,
                control_rig=None,
                priority_order=None,
                section_count=0,
                controls_rotation_order={},
                controls_mask_count=0,
            )

            # Simple properties
            extract_property(properties, "TrackName", ns, "track_name")
            extract_property(properties, "PriorityOrder", ns, "priority_order")

            # Object reference (ControlRig)
            extract_property(properties, "ControlRig", ns, "control_rig", transform=_resolve_object_path)

            # Sections array (count only)
            ns.section_count = len(extract_array_property(properties, "Sections", _as_list))

            # ControlsRotationOrder (TMap<FName, FControlRotationOrder>)
            if "ControlsRotationOrder" in properties:
                rotation_order = properties["ControlsRotationOrder"]
                if isinstance(rotation_order, dict):
                    ns.controls_rotation_order = rotation_order
                elif isinstance(rotation_order, list):
                    for item in rotation_order:
                        if isinstance(item, dict) and "key" in item and "value" in item:
                            ns.controls_rotation_order[str(item["key"])] = item["value"]

            # Store to export custom data
            ensure_custom_data(export)["movie_scene_control_rig_track"] = vars(ns)

            return ParseStatus.SUCCESS

        except (KeyError, TypeError, ValueError) as e:
            logger.debug("MovieSceneControlRigParameterTrack parse error: %s", e)
            if hasattr(context, "warnings"):
                context.warnings.append(f"MovieSceneControlRigParameterTrack parse error: {e}")
            return ParseStatus.PARTIAL


class MovieSceneControlRigParameterSectionHandler:
    """MovieSceneControlRigParameterSection Asset type handler"""

    # Reflection registration metadata
    export_type: str = "MovieSceneControlRigParameterSection"
    priority: int = 100

    # Parameter array property name -> parameter_counts key mapping
    _PARAM_ARRAY_FIELDS: list[tuple[str, str]] = [
        ("ScalarParameterNamesAndCurves", "scalar"),
        ("BoolParameterNamesAndCurves", "bool"),
        ("VectorParameterNamesAndCurves", "vector"),
        ("Vector2DParameterNamesAndCurves", "vector2d"),
        ("ColorParameterNamesAndCurves", "color"),
        ("TransformParameterNamesAndCurves", "transform"),
        ("EnumParameterNamesAndCurves", "enum"),
        ("IntegerParameterNamesAndCurves", "integer"),
    ]

    def handle(self, export: Any, context: Any) -> ParseStatus:
        """Handle MovieSceneControlRigParameterSection export.

        Args:
            export: ObjectExport instance
            context: parse context

        Returns:
            ParseStatus: SUCCESS or PARTIAL
        """
        try:
            properties_list = getattr(export, "properties", [])
            if not properties_list:
                return ParseStatus.PARTIAL

            properties = build_properties_dict(properties_list)

            # Build ControlRig Section metadata
            ns = SimpleNamespace(
                type="MovieSceneControlRigParameterSection",
                control_rig=None,
                control_rig_class=None,
                controls_mask_count=0,
                control_name_mask_count=0,
                transform_mask=None,
                has_weight_curve=False,
                parameter_counts={
                    "scalar": 0,
                    "bool": 0,
                    "vector": 0,
                    "vector2d": 0,
                    "color": 0,
                    "transform": 0,
                    "enum": 0,
                    "integer": 0,
                },
                space_channel_count=0,
                constraint_channel_count=0,
            )

            # Object references
            extract_property(properties, "ControlRig", ns, "control_rig", transform=_resolve_object_path)
            extract_property(properties, "ControlRigClass", ns, "control_rig_class", transform=_resolve_class_name)

            # Simple properties
            extract_property(properties, "TransformMask", ns, "transform_mask")

            # Weight curve existence
            if "Weight" in properties:
                ns.has_weight_curve = True

            # Array counts: ControlsMask, ControlNameMask, SpaceChannels, ConstraintsChannels
            ns.controls_mask_count = len(extract_array_property(properties, "ControlsMask", _as_list))
            ns.control_name_mask_count = len(extract_array_property(properties, "ControlNameMask", _as_list))
            ns.space_channel_count = len(extract_array_property(properties, "SpaceChannels", _as_list))
            ns.constraint_channel_count = len(extract_array_property(properties, "ConstraintsChannels", _as_list))

            # Parameter array counts
            for prop_name, key in self._PARAM_ARRAY_FIELDS:
                ns.parameter_counts[key] = len(extract_array_property(properties, prop_name, _as_list))

            # Store to export custom data
            ensure_custom_data(export)["movie_scene_control_rig_section"] = vars(ns)

            return ParseStatus.SUCCESS

        except (KeyError, TypeError, ValueError) as e:
            logger.debug("MovieSceneControlRigParameterSection parse error: %s", e)
            if hasattr(context, "warnings"):
                context.warnings.append(f"MovieSceneControlRigParameterSection parse error: {e}")
            return ParseStatus.PARTIAL
