"""AnimSequence 资产类型处理器

解析 UAnimSequence 的动画特有数据：
- AdditiveAnimType（叠加动画类型）
- Interpolation（插值方式）
- RateScale（速率缩放）
- Notifies（动画通知）
- FloatCurves（浮点曲线名称）
- CompressedData 存在性检测
"""
from __future__ import annotations

from typing import Any

from uasset_read.models.fallback import ExportParseStatus as ParseStatus
from uasset_read.models.ir import AnimNotifyIR, AnimSequenceIR


class AnimSequenceHandler:
    """AnimSequence 资产类型处理器"""

    # 反射注册元数据
    export_type: str = "AnimSequence"
    priority: int = 100

    def handle(self, export: Any, context: Any) -> ParseStatus:
        """处理 AnimSequence export

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

            # 构建 AnimSequenceIR
            anim_ir = AnimSequenceIR()

            # 提取 TargetSkeleton（属性名可能是 Skeleton 或 TargetSkeleton）
            for skeleton_key in ["Skeleton", "TargetSkeleton"]:
                if skeleton_key in properties:
                    skeleton_ref = properties[skeleton_key]
                    if isinstance(skeleton_ref, dict):
                        anim_ir.target_skeleton = skeleton_ref.get("full_name")
                    break

            # 提取 AdditiveAnimType
            if "AdditiveAnimType" in properties:
                anim_ir.additive_anim_type = properties["AdditiveAnimType"]

            # 提取 RefPoseType
            if "RefPoseType" in properties:
                anim_ir.ref_pose_type = properties["RefPoseType"]

            # 提取 RefFrameIndex
            if "RefFrameIndex" in properties:
                anim_ir.ref_frame_index = properties["RefFrameIndex"]

            # 提取 RefPoseSeq
            if "RefPoseSeq" in properties:
                ref_seq = properties["RefPoseSeq"]
                if isinstance(ref_seq, dict):
                    anim_ir.ref_pose_seq = ref_seq.get("object_path")

            # 提取 RetargetSource
            if "RetargetSource" in properties:
                anim_ir.retarget_source = properties["RetargetSource"]

            # 提取 Interpolation
            if "Interpolation" in properties:
                anim_ir.interpolation = properties["Interpolation"]

            # 提取 bEnableRootMotion
            if "bEnableRootMotion" in properties:
                anim_ir.b_enable_root_motion = properties["bEnableRootMotion"]

            # 提取 RootMotionRootLock
            if "RootMotionRootLock" in properties:
                anim_ir.root_motion_root_lock = properties["RootMotionRootLock"]

            # 提取 RateScale
            if "RateScale" in properties:
                anim_ir.rate_scale = properties["RateScale"]

            # 提取 SequenceLength
            if "SequenceLength" in properties:
                anim_ir.sequence_length = properties["SequenceLength"]

            # 提取 BoneCompressionSettings
            if "BoneCompressionSettings" in properties:
                bone_comp = properties["BoneCompressionSettings"]
                if isinstance(bone_comp, dict):
                    anim_ir.bone_compression_settings = bone_comp.get("object_path")

            # 提取 CurveCompressionSettings
            if "CurveCompressionSettings" in properties:
                curve_comp = properties["CurveCompressionSettings"]
                if isinstance(curve_comp, dict):
                    anim_ir.curve_compression_settings = curve_comp.get("object_path")

            # 检测 CompressedData 存在性
            if "CompressedData" in properties:
                anim_ir.has_compressed_data = True

            # 提取 Notifies
            if "Notifies" in properties:
                anim_ir.notifies = self._parse_notifies(properties["Notifies"])

            # 提取 FloatCurves 名称
            if "RawCurveData" in properties:
                anim_ir.float_curve_names = self._parse_float_curve_names(
                    properties["RawCurveData"]
                )

            # 存储到 export 的自定义数据
            if not hasattr(export, "custom_data"):
                export.custom_data = {}
            export.custom_data["anim_sequence"] = anim_ir

            return ParseStatus.SUCCESS

        except (KeyError, TypeError, ValueError) as e:
            # 记录错误但不中断解析
            if hasattr(context, "warnings"):
                context.warnings.append(f"AnimSequence 解析错误: {e}")
            return ParseStatus.PARTIAL

    def _parse_notifies(self, data: Any) -> list[AnimNotifyIR]:
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

            # 解析对象引用
            linked_montage = notify_data.get("LinkedMontage")
            if isinstance(linked_montage, dict):
                notify.linked_montage = linked_montage.get("object_path")

            linked_sequence = notify_data.get("LinkedSequence")
            if isinstance(linked_sequence, dict):
                notify.linked_sequence = linked_sequence.get("object_path")

            result.append(notify)

        return result

    def _parse_float_curve_names(self, data: Any) -> list[str]:
        """解析浮点曲线名称列表"""
        result = []
        if not isinstance(data, dict):
            return result

        # RawCurveData 包含 FloatCurves 数组
        float_curves = data.get("FloatCurves", [])
        if not isinstance(float_curves, list):
            return result

        for curve in float_curves:
            if isinstance(curve, dict):
                # FloatCurve 包含 Name 字段 (FSmartName)
                name_data = curve.get("Name", {})
                if isinstance(name_data, dict):
                    curve_name = name_data.get("Name", "")
                    if curve_name:
                        result.append(curve_name)

        return result


# 向后兼容：保留旧的函数接口
def parse_anim_sequence(archive: Any, name_map: list[str]) -> dict[str, Any]:
    """提取 AnimSequence 元数据（深度解析）。"""
    # 这个函数保留用于向后兼容，实际处理由 AnimSequenceHandler 完成
    return {
        "parse_status": "delegated_to_handler",
    }
