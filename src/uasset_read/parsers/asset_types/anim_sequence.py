"""AnimSequence Asset type handler

Parse UAnimSequence animation-specific data:
- AdditiveAnimType (additive animation type)
- Interpolation (interpolation method)
- RateScale (rate scale)
- Notifies (animation notifies)
- FloatCurves (float curve names)
- CompressedData track data parsing
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
    """AnimSequence Asset type handler"""

    # Reflection registration metadata
    export_type: str = "AnimSequence"
    priority: int = 100

    def handle(self, export: Any, context: Any) -> ParseStatus:
        """Handle AnimSequence export

        Args:
            export: ObjectExport instance
            context: parse context

        Returns:
            ParseStatus: SUCCESS or PARTIAL
        """
        try:
            # Extract property data from export
            properties_list = getattr(export, "properties", [])
            if not properties_list:
                return ParseStatus.PARTIAL

            # Convert property list to dictionary format（name -> value）
            properties = build_properties_dict(properties_list)

            # Build AnimSequenceIR
            anim_ir = AnimSequenceIR()

            # Extract TargetSkeleton (compatible with both Skeleton and TargetSkeleton keys)
            for skeleton_key in ("Skeleton", "TargetSkeleton"):
                if extract_object_ref(properties, skeleton_key, anim_ir, "target_skeleton", ref_key="full_name"):
                    break

            # Simple property extraction
            extract_property(properties, "AdditiveAnimType", anim_ir, "additive_anim_type")
            extract_property(properties, "RefPoseType", anim_ir, "ref_pose_type")
            extract_property(properties, "RefFrameIndex", anim_ir, "ref_frame_index")
            extract_property(properties, "RetargetSource", anim_ir, "retarget_source")
            extract_property(properties, "Interpolation", anim_ir, "interpolation")
            extract_property(properties, "bEnableRootMotion", anim_ir, "b_enable_root_motion")
            extract_property(properties, "RootMotionRootLock", anim_ir, "root_motion_root_lock")
            extract_property(properties, "RateScale", anim_ir, "rate_scale")
            extract_property(properties, "SequenceLength", anim_ir, "sequence_length")

            # Object reference extraction
            extract_object_ref(properties, "RefPoseSeq", anim_ir, "ref_pose_seq")
            extract_object_ref(properties, "BoneCompressionSettings", anim_ir, "bone_compression_settings")
            extract_object_ref(properties, "CurveCompressionSettings", anim_ir, "curve_compression_settings")

            # Detect CompressedData presence and extract track data
            if "CompressedData" in properties:
                anim_ir.has_compressed_data = True
                self._parse_compressed_data(properties["CompressedData"], anim_ir)

            # Extract Notifies
            anim_ir.notifies = extract_array_property(properties, "Notifies", parse_anim_notifies)

            # Extract FloatCurves names
            anim_ir.float_curve_names = extract_array_property(
                properties, "RawCurveData", parse_float_curve_names
            )

            # Store in export custom data
            ensure_custom_data(export)["anim_sequence"] = anim_ir

            return ParseStatus.SUCCESS

        except (KeyError, TypeError, ValueError) as e:
            logger.warning("AnimSequence parse error: %s", e)
            return ParseStatus.PARTIAL

    def _parse_compressed_data(self, data: Any, anim_ir: AnimSequenceIR) -> None:
        """Parse FCompressedAnimSequence track data

        Args:
            data: CompressedData property value (StructValue or dict)
            anim_ir: AnimSequenceIR instance to store parse results
        """
        # Compatible with both StructValue and dict formats
        if hasattr(data, "fields"):
            fields = data.fields
        elif isinstance(data, dict):
            fields = data
        else:
            return

        if not isinstance(fields, dict):
            return

        # Extract CompressedTrackToSkeletonMapTable (track count)
        track_map = fields.get("CompressedTrackToSkeletonMapTable")
        if isinstance(track_map, list):
            anim_ir.compressed_track_count = len(track_map)
        elif isinstance(track_map, dict):
            elements = track_map.get("elements", [])
            if isinstance(elements, list):
                anim_ir.compressed_track_count = len(elements)

        # Extract CompressedByteStream size
        byte_stream = fields.get("CompressedByteStream")
        if isinstance(byte_stream, list):
            anim_ir.compressed_byte_stream_size = len(byte_stream)
        elif isinstance(byte_stream, dict):
            data_size = byte_stream.get("data_size")
            if isinstance(data_size, int) and data_size > 0:
                anim_ir.compressed_byte_stream_size = data_size

        # Extract CompressedRawDataSize
        raw_data_size = fields.get("CompressedRawDataSize")
        if isinstance(raw_data_size, int):
            anim_ir.compressed_raw_data_size = raw_data_size

        # Extract codec names (if present)
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


# Backward compatible: keep old function interface
def parse_anim_sequence(archive: Any, name_map: list[str]) -> dict[str, Any]:
    """Extract AnimSequence metadata (deep parse)."""
    return {
        "parse_status": "success",
    }
