"""UMovieScene 资产类型处理器

解析 UMovieScene 的 tagged properties 数据：
- DisplayRate: FFrameRate（显示帧率，Numerator + Denominator）
- TickResolution: FFrameRate（Tick 分辨率，Numerator + Denominator）
- EvaluationType: EMovieSceneEvaluationType（求值类型）
- ClockSource: EUpdateClockSource（时钟源）
- Tracks: TArray<UMovieSceneTrack>（轨道列表，提取类名）
- Spawnables: TArray<FMovieSceneSpawnable>（可生成对象）
- Possessables: TArray<FMovieScenePossessable>（可持有对象）

格式参考：
- Engine/Source/Runtime/MovieScene/Public/MovieScene.h
- Engine/Source/Runtime/MovieScene/Private/MovieScene.cpp
"""
from __future__ import annotations

import logging
from typing import Any

from uasset_read.models.fallback import ExportParseStatus as ParseStatus
from uasset_read.parsers.asset_types.anim_common import ensure_custom_data
from uasset_read.parsers.asset_types.property_extractor import (
    build_properties_dict,
    extract_array_property,
    extract_property,
)

logger = logging.getLogger(__name__)


def _parse_frame_rate(value: Any) -> dict | None:
    """解析 FFrameRate 属性值（dict 或 list/tuple）"""
    if isinstance(value, dict):
        return {
            "numerator": value.get("Numerator", 0),
            "denominator": value.get("Denominator", 1),
        }
    if isinstance(value, (list, tuple)) and len(value) >= 2:
        return {
            "numerator": value[0],
            "denominator": value[1],
        }
    return None


def _parse_track_classes(value: Any) -> list[str]:
    """从 Tracks 数组提取轨道类名"""
    if not isinstance(value, list):
        return []
    return [
        cls
        for track in value
        if isinstance(track, dict)
        for cls in [track.get("class_name") or track.get("class")]
        if cls
    ]


class _MovieSceneData:
    """MovieScene 解析结果容器，支持 extract_property 的 setattr 访问"""

    __slots__ = (
        "display_rate", "tick_resolution", "evaluation_type", "clock_source",
        "track_count", "track_classes", "spawnable_count", "possessable_count",
        "binding_count", "marked_frame_count",
    )

    def __init__(self) -> None:
        self.display_rate = None
        self.tick_resolution = None
        self.evaluation_type = None
        self.clock_source = None
        self.track_count = 0
        self.track_classes: list[str] = []
        self.spawnable_count = 0
        self.possessable_count = 0
        self.binding_count = 0
        self.marked_frame_count = 0

    def to_dict(self) -> dict[str, Any]:
        return {"type": "MovieScene", **{slot: getattr(self, slot) for slot in self.__slots__}}


class MovieSceneHandler:
    """UMovieScene 资产类型处理器"""

    # 反射注册元数据
    export_type: str = "MovieScene"
    priority: int = 100

    def handle(self, export: Any, context: Any) -> ParseStatus:
        """处理 MovieScene export

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

            # 构建 MovieScene 元数据
            data = _MovieSceneData()

            # FFrameRate 属性提取
            extract_property(properties, "DisplayRate", data, "display_rate", transform=_parse_frame_rate)
            extract_property(properties, "TickResolution", data, "tick_resolution", transform=_parse_frame_rate)

            # 简单属性提取
            extract_property(properties, "EvaluationType", data, "evaluation_type")
            extract_property(properties, "ClockSource", data, "clock_source")

            # 数组属性提取（Tracks 同时提取类名）
            tracks = extract_array_property(properties, "Tracks", _parse_track_classes)
            data.track_count = len(tracks)
            data.track_classes = tracks

            # 数组长度提取
            data.spawnable_count = len(extract_array_property(properties, "Spawnables", lambda x: x if isinstance(x, list) else []))
            data.possessable_count = len(extract_array_property(properties, "Possessables", lambda x: x if isinstance(x, list) else []))
            data.binding_count = len(extract_array_property(properties, "ObjectBindings", lambda x: x if isinstance(x, list) else []))
            data.marked_frame_count = len(extract_array_property(properties, "MarkedFrames", lambda x: x if isinstance(x, list) else []))

            # 存储到 export 的自定义数据
            ensure_custom_data(export)["movie_scene"] = data.to_dict()

            return ParseStatus.SUCCESS

        except (KeyError, TypeError, ValueError) as e:
            # 记录错误但不中断解析
            logger.debug("MovieScene 解析错误: %s", e)
            if hasattr(context, "warnings"):
                context.warnings.append(f"MovieScene 解析错误: {e}")
            return ParseStatus.PARTIAL
