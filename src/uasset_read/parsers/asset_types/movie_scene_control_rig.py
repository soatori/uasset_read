"""MovieSceneControlRigParameterTrack 资产类型处理器

解析 UMovieSceneControlRigParameterTrack 和 UMovieSceneControlRigParameterSection：
- TrackName: FName（轨道名称）
- ControlRig: TObjectPtr<UControlRig>（Control Rig 引用）
- PriorityOrder: int32（优先级顺序）
- ControlsRotationOrder: TMap<FName, FControlRotationOrder>（控制旋转顺序）
- Section 数量和参数信息

格式参考：
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
    """从对象引用属性值中提取 object_path（dict 或 fallback 到 str）"""
    if isinstance(value, dict):
        return value.get("object_path")
    return str(value)


def _resolve_class_name(value: Any) -> Any:
    """从对象引用属性值中提取 class_name（dict 或 fallback 到 str）"""
    if isinstance(value, dict):
        return value.get("class_name")
    return str(value)


def _as_list(value: Any) -> list:
    """确保值为列表（非列表返回空列表）"""
    return value if isinstance(value, list) else []


class MovieSceneControlRigParameterTrackHandler:
    """MovieSceneControlRigParameterTrack 资产类型处理器"""

    # 反射注册元数据
    export_type: str = "MovieSceneControlRigParameterTrack"
    priority: int = 100

    def handle(self, export: Any, context: Any) -> ParseStatus:
        """处理 MovieSceneControlRigParameterTrack export

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

            # 构建 ControlRig Track 元数据
            ns = SimpleNamespace(
                type="MovieSceneControlRigParameterTrack",
                track_name=None,
                control_rig=None,
                priority_order=None,
                section_count=0,
                controls_rotation_order={},
                controls_mask_count=0,
            )

            # 简单属性
            extract_property(properties, "TrackName", ns, "track_name")
            extract_property(properties, "PriorityOrder", ns, "priority_order")

            # 对象引用（ControlRig）
            extract_property(properties, "ControlRig", ns, "control_rig", transform=_resolve_object_path)

            # Sections 数组（仅计数）
            ns.section_count = len(extract_array_property(properties, "Sections", _as_list))

            # ControlsRotationOrder（TMap<FName, FControlRotationOrder>）
            if "ControlsRotationOrder" in properties:
                rotation_order = properties["ControlsRotationOrder"]
                if isinstance(rotation_order, dict):
                    ns.controls_rotation_order = rotation_order
                elif isinstance(rotation_order, list):
                    for item in rotation_order:
                        if isinstance(item, dict) and "key" in item and "value" in item:
                            ns.controls_rotation_order[str(item["key"])] = item["value"]

            # 存储到 export 的自定义数据
            ensure_custom_data(export)["movie_scene_control_rig_track"] = vars(ns)

            return ParseStatus.SUCCESS

        except (KeyError, TypeError, ValueError) as e:
            logger.debug("MovieSceneControlRigParameterTrack 解析错误: %s", e)
            if hasattr(context, "warnings"):
                context.warnings.append(f"MovieSceneControlRigParameterTrack 解析错误: {e}")
            return ParseStatus.PARTIAL


class MovieSceneControlRigParameterSectionHandler:
    """MovieSceneControlRigParameterSection 资产类型处理器"""

    # 反射注册元数据
    export_type: str = "MovieSceneControlRigParameterSection"
    priority: int = 100

    # 参数数组属性名 → parameter_counts 键的映射
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
        """处理 MovieSceneControlRigParameterSection export

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

            # 构建 ControlRig Section 元数据
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

            # 对象引用
            extract_property(properties, "ControlRig", ns, "control_rig", transform=_resolve_object_path)
            extract_property(properties, "ControlRigClass", ns, "control_rig_class", transform=_resolve_class_name)

            # 简单属性
            extract_property(properties, "TransformMask", ns, "transform_mask")

            # Weight 曲线存在性
            if "Weight" in properties:
                ns.has_weight_curve = True

            # 数组计数：ControlsMask、ControlNameMask、SpaceChannels、ConstraintsChannels
            ns.controls_mask_count = len(extract_array_property(properties, "ControlsMask", _as_list))
            ns.control_name_mask_count = len(extract_array_property(properties, "ControlNameMask", _as_list))
            ns.space_channel_count = len(extract_array_property(properties, "SpaceChannels", _as_list))
            ns.constraint_channel_count = len(extract_array_property(properties, "ConstraintsChannels", _as_list))

            # 参数数组计数
            for prop_name, key in self._PARAM_ARRAY_FIELDS:
                ns.parameter_counts[key] = len(extract_array_property(properties, prop_name, _as_list))

            # 存储到 export 的自定义数据
            ensure_custom_data(export)["movie_scene_control_rig_section"] = vars(ns)

            return ParseStatus.SUCCESS

        except (KeyError, TypeError, ValueError) as e:
            logger.debug("MovieSceneControlRigParameterSection 解析错误: %s", e)
            if hasattr(context, "warnings"):
                context.warnings.append(f"MovieSceneControlRigParameterSection 解析错误: {e}")
            return ParseStatus.PARTIAL
