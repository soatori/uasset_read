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

    def handle(self, export: Any, context: Any) -> ParseStatus:
        """处理 AnimMontage export

        Args:
            export: ObjectExport 实例
            context: 解析上下文

        Returns:
            ParseStatus: SUCCESS 或 PARTIAL
        """
        try:
            # 从 export.instance 提取动画数据
            instance = getattr(export, "instance", None)
            if instance is None:
                return ParseStatus.PARTIAL

            properties = getattr(instance, "properties", {})
            if not properties:
                return ParseStatus.PARTIAL

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

            # 存储到 export 的自定义数据
            if not hasattr(export, "custom_data"):
                export.custom_data = {}
            export.custom_data["anim_montage"] = anim_ir

            return ParseStatus.SUCCESS

        except Exception as e:
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
