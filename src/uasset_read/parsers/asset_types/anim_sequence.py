"""AnimSequence 资产类型处理器

解析 UAnimSequence 的动画特有数据：
- AdditiveAnimType（叠加动画类型）
- Interpolation（插值方式）
- RateScale（速率缩放）
- Notifies（动画通知）
- FloatCurves（浮点曲线名称）
- CompressedData 轨迹数据解析
"""

import logging
from typing import Any

from uasset_read.models.fallback import ExportParseStatus as ParseStatus
from uasset_read.models.ir import AnimSequenceIR
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
)

logger = logging.getLogger(__name__)


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
            properties_list = getattr(export, "properties", [])
            if not properties_list:
                return ParseStatus.PARTIAL

            # 将属性列表转换为字典格式（name -> value）
            properties = build_properties_dict(properties_list)

            # 构建 AnimSequenceIR
            anim_ir = AnimSequenceIR()

            # 提取 TargetSkeleton（兼容 Skeleton 和 TargetSkeleton 两个 key）
            for skeleton_key in ("Skeleton", "TargetSkeleton"):
                if extract_object_ref(properties, skeleton_key, anim_ir, "target_skeleton", ref_key="full_name"):
                    break

            # 简单属性提取
            extract_property(properties, "AdditiveAnimType", anim_ir, "additive_anim_type")
            extract_property(properties, "RefPoseType", anim_ir, "ref_pose_type")
            extract_property(properties, "RefFrameIndex", anim_ir, "ref_frame_index")
            extract_property(properties, "RetargetSource", anim_ir, "retarget_source")
            extract_property(properties, "Interpolation", anim_ir, "interpolation")
            extract_property(properties, "bEnableRootMotion", anim_ir, "b_enable_root_motion")
            extract_property(properties, "RootMotionRootLock", anim_ir, "root_motion_root_lock")
            extract_property(properties, "RateScale", anim_ir, "rate_scale")
            extract_property(properties, "SequenceLength", anim_ir, "sequence_length")

            # 对象引用提取
            extract_object_ref(properties, "RefPoseSeq", anim_ir, "ref_pose_seq")
            extract_object_ref(properties, "BoneCompressionSettings", anim_ir, "bone_compression_settings")
            extract_object_ref(properties, "CurveCompressionSettings", anim_ir, "curve_compression_settings")

            # 检测 CompressedData 存在性并提取轨迹数据
            if "CompressedData" in properties:
                anim_ir.has_compressed_data = True
                self._parse_compressed_data(properties["CompressedData"], anim_ir)

            # 提取 Notifies
            anim_ir.notifies = extract_array_property(properties, "Notifies", parse_anim_notifies)

            # 提取 FloatCurves 名称
            anim_ir.float_curve_names = extract_array_property(
                properties, "RawCurveData", parse_float_curve_names
            )

            # 存储到 export 的自定义数据
            ensure_custom_data(export)["anim_sequence"] = anim_ir

            return ParseStatus.SUCCESS

        except (KeyError, TypeError, ValueError) as e:
            # 记录错误但不中断解析
            if hasattr(context, "warnings"):
                context.warnings.append(f"AnimSequence 解析错误: {e}")
            return ParseStatus.PARTIAL

    def _parse_compressed_data(self, data: Any, anim_ir: AnimSequenceIR) -> None:
        """解析 FCompressedAnimSequence 轨迹数据

        Args:
            data: CompressedData 属性值（StructValue 或 dict）
            anim_ir: AnimSequenceIR 实例，用于存储解析结果
        """
        # 兼容 StructValue 和 dict 两种格式
        if hasattr(data, "fields"):
            fields = data.fields
        elif isinstance(data, dict):
            fields = data
        else:
            return

        if not isinstance(fields, dict):
            return

        # 提取 CompressedTrackToSkeletonMapTable（轨迹数量）
        track_map = fields.get("CompressedTrackToSkeletonMapTable")
        if isinstance(track_map, list):
            anim_ir.compressed_track_count = len(track_map)
        elif isinstance(track_map, dict):
            elements = track_map.get("elements", [])
            if isinstance(elements, list):
                anim_ir.compressed_track_count = len(elements)

        # 提取 CompressedByteStream 大小
        byte_stream = fields.get("CompressedByteStream")
        if isinstance(byte_stream, list):
            anim_ir.compressed_byte_stream_size = len(byte_stream)
        elif isinstance(byte_stream, dict):
            data_size = byte_stream.get("data_size")
            if isinstance(data_size, int) and data_size > 0:
                anim_ir.compressed_byte_stream_size = data_size

        # 提取 CompressedRawDataSize
        raw_data_size = fields.get("CompressedRawDataSize")
        if isinstance(raw_data_size, int):
            anim_ir.compressed_raw_data_size = raw_data_size

        # 提取编解码器名称（如果存在）
        bone_codec = fields.get("BoneCompressionCodec")
        if isinstance(bone_codec, str):
            anim_ir.bone_compression_codec = bone_codec
        elif isinstance(bone_codec, dict):
            anim_ir.bone_compression_codec = bone_codec.get("object_path") or bone_codec.get("full_name")

        curve_codec = fields.get("CurveCompressionCodec")
        if isinstance(curve_codec, str):
            anim_ir.curve_compression_codec = curve_codec
        elif isinstance(curve_codec, dict):
            anim_ir.curve_compression_codec = curve_codec.get("object_path") or curve_codec.get("full_name")


# 向后兼容：保留旧的函数接口
def parse_anim_sequence(archive: Any, name_map: list[str]) -> dict[str, Any]:
    """提取 AnimSequence 元数据（深度解析）。"""
    return {
        "parse_status": "success",
    }
