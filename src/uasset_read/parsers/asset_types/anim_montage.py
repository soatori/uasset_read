"""AnimMontage 资产类型处理器

解析 UAnimMontage 的动画特有数据：
- BlendModeIn/Out（混合模式）
- SyncGroup（同步组）
- AnimNotifies（动画通知）
- RateScale（速率缩放）
"""

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


class AnimMontageHandler:
    """AnimMontage 资产类型处理器"""

    # 反射注册元数据
    export_type: str = "AnimMontage"
    priority: int = 100

    def handle(self, export: Any, context: Any) -> ParseStatus:
        """处理 AnimMontage export

        Args:
            export: ObjectExport 实例
            context: 解析上下文

        Returns:
            ParseStatus: SUCCESS 或 PARTIAL
        """
        try:
            properties_list = getattr(export, "properties", [])
            if not properties_list:
                return ParseStatus.PARTIAL

            properties = build_properties_dict(properties_list)

            anim_ir = AnimMontageIR()

            # 提取混合参数
            extract_property(properties, "BlendModeIn", anim_ir, "blend_mode_in")
            extract_property(properties, "BlendModeOut", anim_ir, "blend_mode_out")
            extract_property(properties, "BlendInAlpha", anim_ir, "blend_in_alpha")
            extract_property(properties, "BlendOutAlpha", anim_ir, "blend_out_alpha")
            extract_property(properties, "BlendOutTriggerTime", anim_ir, "blend_out_trigger_time")

            # 提取同步组
            extract_property(properties, "SyncGroup", anim_ir, "sync_group")
            extract_property(properties, "SyncSlotIndex", anim_ir, "sync_slot_index")

            # 提取其他参数
            extract_property(properties, "bEnableAutoBlendOut", anim_ir, "b_enable_auto_blend_out")
            extract_property(properties, "RateScale", anim_ir, "rate_scale")

            # 提取 AnimNotifies
            anim_ir.notifies = extract_array_property(
                properties, "AnimNotifies", parse_anim_notifies
            )

            # 提取 CompositeSections
            anim_ir.composite_sections = extract_array_property(
                properties, "CompositeSections", self._parse_composite_sections
            )

            # 提取 SlotAnimTracks
            anim_ir.slot_anim_tracks = extract_array_property(
                properties, "SlotAnimTracks", self._parse_slot_anim_tracks
            )

            # 提取 BranchingPointMarkers
            anim_ir.branching_point_markers = extract_array_property(
                properties, "BranchingPointMarkers", self._parse_branching_point_markers
            )

            # 提取 BlendInOption/BlendOutOption
            extract_object_ref(properties, "BlendInOption", anim_ir, "blend_in_option", "BlendOption")
            extract_object_ref(properties, "BlendOutOption", anim_ir, "blend_out_option", "BlendOption")

            # 提取 FloatCurveNames
            if "RawCurveData" in properties:
                anim_ir.float_curve_names = parse_float_curve_names(
                    properties["RawCurveData"]
                )

            ensure_custom_data(export)["anim_montage"] = anim_ir

            return ParseStatus.SUCCESS

        except (KeyError, TypeError, ValueError) as e:
            if hasattr(context, "warnings"):
                context.warnings.append(f"AnimMontage 解析错误: {e}")
            return ParseStatus.PARTIAL

    def _parse_composite_sections(self, data: Any) -> list[dict]:
        """解析 CompositeSections 数组"""

        def _parse_section(section: dict) -> dict:
            return {
                "section_name": section.get("SectionName", ""),
                "next_section_name": section.get("NextSectionName", ""),
            }

        return parse_dict_list(data, _parse_section)

    def _parse_slot_anim_tracks(self, data: Any) -> list[dict]:
        """解析 SlotAnimTracks 数组"""

        def _parse_track(track: dict) -> dict:
            return {
                "slot_node_name": track.get("SlotNodeName", ""),
            }

        return parse_dict_list(data, _parse_track)

    def _parse_branching_point_markers(self, data: Any) -> list[dict]:
        """解析 BranchingPointMarkers 数组"""

        def _parse_marker(marker: dict) -> dict:
            return {
                "notify_index": marker.get("NotifyIndex", -1),
                "trigger_time": marker.get("TriggerTime", 0.0),
            }

        return parse_dict_list(data, _parse_marker)

