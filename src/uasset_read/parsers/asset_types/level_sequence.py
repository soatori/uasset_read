"""ULevelSequence 资产类型处理器

解析 ULevelSequence 的 custom serialization 数据：
- MovieScene: int32（opaque pointer，指向 UMovieScene 对象）
- MovieSceneSource: int32（TSoftObjectPtr，资产源引用）
- MovieSceneLicense: FString（许可证字符串）
- DisplayRate: FFrameRate（显示帧率，Numerator + Denominator 各 int32）
- TickResolution: FFrameRate（Tick 分辨率，Numerator + Denominator 各 int32）

格式参考：
- Engine/Source/Runtime/LevelSequence/Classes/LevelSequence.h
- Engine/Source/Runtime/LevelSequence/Private/LevelSequence.cpp
"""
from __future__ import annotations

import logging
import struct
from typing import Any, Dict, List

from uasset_read.exceptions import ParseError

logger = logging.getLogger(__name__)


def parse_level_sequence(archive: Any, name_map: List[str]) -> Dict[str, Any]:
    """解析 ULevelSequence 资产的 custom serialization 数据。

    Args:
        archive: FArchive 实例（已定位到 export 的 serial_offset）
        name_map: 名称表

    Returns:
        解析结果字典，包含 movie_scene、movie_scene_source、movie_scene_license、
        display_rate、tick_resolution 等字段
    """
    result: Dict[str, Any] = {
        "parse_status": "success",
    }

    try:
        # 1. MovieScene: int32 — opaque pointer to UMovieScene
        #    LevelSequence.cpp: ULevelSequence::Serialize 序列化 MovieScene 指针
        result["movie_scene"] = archive.read_i32("LevelSequence.MovieScene")

        # 2. MovieSceneSource: TSoftObjectPtr — 资产源引用（序列化为 int32 对象索引）
        result["movie_scene_source"] = archive.read_i32("LevelSequence.MovieSceneSource")

        # 3. MovieSceneLicense: FString — 许可证字符串
        result["movie_scene_license"] = archive.read_fstring("LevelSequence.MovieSceneLicense")

        # 4. DisplayRate: FFrameRate — 显示帧率
        display_rate_num = archive.read_i32("LevelSequence.DisplayRate.Numerator")
        display_rate_den = archive.read_i32("LevelSequence.DisplayRate.Denominator")
        result["display_rate"] = {
            "numerator": display_rate_num,
            "denominator": display_rate_den,
        }

        # 5. TickResolution: FFrameRate — Tick 分辨率
        tick_resolution_num = archive.read_i32("LevelSequence.TickResolution.Numerator")
        tick_resolution_den = archive.read_i32("LevelSequence.TickResolution.Denominator")
        result["tick_resolution"] = {
            "numerator": tick_resolution_num,
            "denominator": tick_resolution_den,
        }

    except (struct.error, OSError, ValueError, ParseError) as e:
        logger.debug("LevelSequence handler 解析失败: %s", e)
        result["parse_status"] = "failed"
        result["error"] = str(e)

    return result
