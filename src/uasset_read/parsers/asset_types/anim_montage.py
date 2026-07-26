"""AnimMontage Asset type handler

Parse UAnimMontage animation-specific data:
- BlendModeIn/Out (blend mode)
- SyncGroup (sync group)
- AnimNotifies (animation notifies)
- RateScale (rate scale)
"""

import logging
from typing import Any

from uasset_read.models.fallback import ExportParseStatus as ParseStatus
from uasset_read.models.ir import AnimMontageIR
from uasset_read.parsers.asset_types.anim_common import (
    ensure_custom_data,
    parse_anim_notifies,
    parse_float_curve_names,
)
from uasset_read.parsers.asset_types.property_extractor import (
    build_properties_dict,
    extract_array_property,
    extract_object_ref,
    extract_property,
    parse_dict_list,
)

logger = logging.getLogger(__name__)


class AnimMontageHandler:
    """AnimMontage Asset type handler"""

    # Reflection registration metadata
    export_type: str = "AnimMontage"
    priority: int = 100

    def handle(self, export: Any, context: Any) -> ParseStatus:
        """Handle AnimMontage export

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

            anim_ir = AnimMontageIR()

            # Extract blend parameters
            extract_property(properties, "BlendModeIn", anim_ir, "blend_mode_in")
            extract_property(properties, "BlendModeOut", anim_ir, "blend_mode_out")
            extract_property(properties, "BlendInAlpha", anim_ir, "blend_in_alpha")
            extract_property(properties, "BlendOutAlpha", anim_ir, "blend_out_alpha")
            extract_property(properties, "BlendOutTriggerTime", anim_ir, "blend_out_trigger_time")

            # Extract sync group
            extract_property(properties, "SyncGroup", anim_ir, "sync_group")
            extract_property(properties, "SyncSlotIndex", anim_ir, "sync_slot_index")

            # Extract other parameters
            extract_property(properties, "bEnableAutoBlendOut", anim_ir, "b_enable_auto_blend_out")
            extract_property(properties, "RateScale", anim_ir, "rate_scale")

            # Extract AnimNotifies
            anim_ir.notifies = extract_array_property(
                properties, "AnimNotifies", parse_anim_notifies
            )

            # Extract CompositeSections
            anim_ir.composite_sections = extract_array_property(
                properties, "CompositeSections", self._parse_composite_sections
            )

            # Extract SlotAnimTracks
            anim_ir.slot_anim_tracks = extract_array_property(
                properties, "SlotAnimTracks", self._parse_slot_anim_tracks
            )

            # Extract BranchingPointMarkers
            anim_ir.branching_point_markers = extract_array_property(
                properties, "BranchingPointMarkers", self._parse_branching_point_markers
            )

            # Extract BlendInOption/BlendOutOption
            extract_object_ref(properties, "BlendInOption", anim_ir, "blend_in_option", "BlendOption")
            extract_object_ref(properties, "BlendOutOption", anim_ir, "blend_out_option", "BlendOption")

            # Extract FloatCurveNames
            if "RawCurveData" in properties:
                anim_ir.float_curve_names = parse_float_curve_names(
                    properties["RawCurveData"]
                )

            ensure_custom_data(export)["anim_montage"] = anim_ir

            return ParseStatus.SUCCESS

        except (KeyError, TypeError, ValueError) as e:
            logger.warning("AnimMontage parse error: %s", e)
            return ParseStatus.PARTIAL

    def _parse_composite_sections(self, data: Any) -> list[dict]:
        """Parse CompositeSections array"""

        def _parse_section(section: dict) -> dict:
            return {
                "section_name": section.get("SectionName", ""),
                "next_section_name": section.get("NextSectionName", ""),
            }

        return parse_dict_list(data, _parse_section)

    def _parse_slot_anim_tracks(self, data: Any) -> list[dict]:
        """Parse SlotAnimTracks array"""

        def _parse_track(track: dict) -> dict:
            return {
                "slot_node_name": track.get("SlotNodeName", ""),
            }

        return parse_dict_list(data, _parse_track)

    def _parse_branching_point_markers(self, data: Any) -> list[dict]:
        """Parse BranchingPointMarkers array"""

        def _parse_marker(marker: dict) -> dict:
            return {
                "notify_index": marker.get("NotifyIndex", -1),
                "trigger_time": marker.get("TriggerTime", 0.0),
            }

        return parse_dict_list(data, _parse_marker)

