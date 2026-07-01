"""AnimMontage 资产类型处理器

解析 UAnimMontage 的动画特有数据：
- BlendModeIn/Out（混合模式）
- SyncGroup（同步组）
- AnimNotifies（动画通知）
- RateScale（速率缩放）
"""
from __future__ import annotations

from typing import Any

from uasset_read.models.fallback import ExportParseStatus as ParseStatus
from uasset_read.models.ir import AnimMontageIR, AnimNotifyIR


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
            # 从 export 提取属性数据
            # ObjectExport 有 properties 属性（解析后的属性列表）
            properties_list = getattr(export, "properties", [])
            if not properties_list:
                return ParseStatus.PARTIAL

            # 将属性列表转换为字典格式（name -> value）
            properties = {}
            for prop in properties_list:
                if hasattr(prop, "name") and hasattr(prop, "value"):
                    properties[prop.name] = prop.value

            # 构建 AnimMontageIR
            anim_ir = AnimMontageIR()

            # 提取混合参数
            if "BlendModeIn" in properties:
                anim_ir.blend_mode_in = properties["BlendModeIn"]
            if "BlendModeOut" in properties:
                anim_ir.blend_mode_out = properties["BlendModeOut"]
            if "BlendInAlpha" in properties:
                anim_ir.blend_in_alpha = properties["BlendInAlpha"]
            if "BlendOutAlpha" in properties:
                anim_ir.blend_out_alpha = properties["BlendOutAlpha"]
            if "BlendOutTriggerTime" in properties:
                anim_ir.blend_out_trigger_time = properties["BlendOutTriggerTime"]

            # 提取同步组
            if "SyncGroup" in properties:
                anim_ir.sync_group = properties["SyncGroup"]
            if "SyncSlotIndex" in properties:
                anim_ir.sync_slot_index = properties["SyncSlotIndex"]

            # 提取其他参数
            if "bEnableAutoBlendOut" in properties:
                anim_ir.b_enable_auto_blend_out = properties["bEnableAutoBlendOut"]
            if "RateScale" in properties:
                anim_ir.rate_scale = properties["RateScale"]

            # 提取 AnimNotifies
            if "AnimNotifies" in properties:
                anim_ir.notifies = self._parse_anim_notifies(properties["AnimNotifies"])

            # 提取 CompositeSections
            if "CompositeSections" in properties:
                anim_ir.composite_sections = self._parse_composite_sections(
                    properties["CompositeSections"]
                )

            # 提取 SlotAnimTracks
            if "SlotAnimTracks" in properties:
                anim_ir.slot_anim_tracks = self._parse_slot_anim_tracks(
                    properties["SlotAnimTracks"]
                )

            # 提取 BranchingPointMarkers
            if "BranchingPointMarkers" in properties:
                anim_ir.branching_point_markers = self._parse_branching_point_markers(
                    properties["BranchingPointMarkers"]
                )

            # 提取 BlendInOption/BlendOutOption
            if "BlendInOption" in properties:
                blend_in = properties["BlendInOption"]
                if isinstance(blend_in, dict):
                    anim_ir.blend_in_option = blend_in.get("BlendOption")
            if "BlendOutOption" in properties:
                blend_out = properties["BlendOutOption"]
                if isinstance(blend_out, dict):
                    anim_ir.blend_out_option = blend_out.get("BlendOption")

            # 提取 FloatCurveNames
            if "RawCurveData" in properties:
                anim_ir.float_curve_names = self._parse_float_curve_names(
                    properties["RawCurveData"]
                )

            # 存储到 export 的自定义数据
            if not hasattr(export, "custom_data"):
                export.custom_data = {}
            export.custom_data["anim_montage"] = anim_ir

            return ParseStatus.SUCCESS

        except (KeyError, TypeError, ValueError) as e:
            # 记录错误但不中断解析
            if hasattr(context, "warnings"):
                context.warnings.append(f"AnimMontage 解析错误: {e}")
            return ParseStatus.PARTIAL

    def _parse_anim_notifies(self, data: Any) -> list[AnimNotifyIR]:
        """解析动画通知数组"""
        result = []
        if not isinstance(data, list):
            return result

        for notify_data in data:
            if not isinstance(notify_data, dict):
                continue

            notify = AnimNotifyIR(
                notify_name=notify_data.get("NotifyName", ""),
                trigger_time_offset=notify_data.get("TriggerTimeOffset", 0.0),
                duration=notify_data.get("Duration", 0.0),
                notify_class=notify_data.get("NotifyClass"),
                track_index=notify_data.get("TrackIndex", 0),
            )
            result.append(notify)

        return result

    def _parse_composite_sections(self, data: Any) -> list[dict]:
        """解析 CompositeSections 数组"""
        result = []
        if not isinstance(data, list):
            return result
        for section in data:
            if isinstance(section, dict):
                result.append({
                    "section_name": section.get("SectionName", ""),
                    "next_section_name": section.get("NextSectionName", ""),
                })
        return result

    def _parse_slot_anim_tracks(self, data: Any) -> list[dict]:
        """解析 SlotAnimTracks 数组"""
        result = []
        if not isinstance(data, list):
            return result
        for track in data:
            if isinstance(track, dict):
                result.append({
                    "slot_node_name": track.get("SlotNodeName", ""),
                })
        return result

    def _parse_branching_point_markers(self, data: Any) -> list[dict]:
        """解析 BranchingPointMarkers 数组"""
        result = []
        if not isinstance(data, list):
            return result
        for marker in data:
            if isinstance(marker, dict):
                result.append({
                    "notify_index": marker.get("NotifyIndex", -1),
                    "trigger_time": marker.get("TriggerTime", 0.0),
                })
        return result

    def _parse_float_curve_names(self, data: Any) -> list[str]:
        """解析浮点曲线名称列表"""
        result = []
        if not isinstance(data, dict):
            return result
        float_curves = data.get("FloatCurves", [])
        if not isinstance(float_curves, list):
            return result
        for curve in float_curves:
            if isinstance(curve, dict):
                name_data = curve.get("Name", {})
                if isinstance(name_data, dict):
                    curve_name = name_data.get("Name", "")
                    if curve_name:
                        result.append(curve_name)
        return result
