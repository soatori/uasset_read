"""USoundWave 资产类型处理器

解析 USoundWave 的 custom serialization 数据：
- Flags: uint32 — bit-packed (CookedFlag, HasOwnerLoadingBehaviorFlag, LoadingBehavior)
- 条件字段根据 Flags 和版本号读取

同时从已解析的 UPROPERTY 标签属性中提取语义元数据：
- SampleRate, NumChannels, Duration, Volume, Pitch
- SoundAssetCompressionType, CompressionQuality
- bLooping, bStreaming, SoundGroup

格式参考：
- Engine/Source/Runtime/Engine/Classes/Sound/SoundWave.h
- Engine/Source/Runtime/Engine/Private/Sound/SoundWave.cpp (USoundWave::Serialize)
"""

import logging
import struct
from typing import Any, Dict, List, Optional

from uasset_read.exceptions import ParseError

logger = logging.getLogger(__name__)

# --- Flags bit definitions (SoundWave.cpp:1269-1276) ---
_COOKED_FLAG = 1 << 0
_HAS_OWNER_LOADING_BEHAVIOR_FLAG = 1 << 1
_LOADING_BEHAVIOR_SHIFT = 2
_LOADING_BEHAVIOR_MASK = 0b00000111

# Compression type enum values (SoundWave.h:348-366)
_COMPRESSION_TYPE_NAMES = {
    0: "BinkAudio",
    1: "ADPCM",
    2: "PCM",
    3: "Opus",
    4: "PlatformSpecific",
    5: "ProjectDefined",
    6: "RADAudio",
}

# Loading behavior enum values (SoundWaveLoadingBehavior.h:22-37)
_LOADING_BEHAVIOR_NAMES = {
    0: "Inherited",
    1: "RetainOnLoad",
    2: "PrimeOnLoad",
    3: "LoadOnDemand",
    4: "ForceInline",
    0xFF: "Uninitialized",
}

# Sound group enum values (SoundGroups.h)
_SOUND_GROUP_NAMES = {
    0: "Default",
    1: "UI",
    2: "Ambient",
    3: "ForceMono",
    4: "SFX",
    5: "Music",
}


def _extract_property(properties: List[Any], name: str) -> Optional[Any]:
    """从已解析的属性列表中提取指定名称的属性值。

    Args:
        properties: PropertyValue 列表（来自 property parser）
        name: 属性名（如 "SampleRate"）

    Returns:
        属性值或 None
    """
    for prop in properties:
        if hasattr(prop, "name") and prop.name == name:
            return getattr(prop, "value", None)
    return None


def _extract_bool(properties: List[Any], name: str) -> bool:
    """从属性列表中提取布尔值。"""
    val = _extract_property(properties, name)
    if val is None:
        return False
    if isinstance(val, bool):
        return val
    if isinstance(val, int):
        return val != 0
    return bool(val)


def _extract_int(properties: List[Any], name: str) -> Optional[int]:
    """从属性列表中提取 int 值。"""
    val = _extract_property(properties, name)
    if val is None:
        return None
    if isinstance(val, int):
        return val
    return None


def _extract_float(properties: List[Any], name: str) -> Optional[float]:
    """从属性列表中提取 float 值。"""
    val = _extract_property(properties, name)
    if val is None:
        return None
    if isinstance(val, (int, float)):
        return float(val)
    return None


def _extract_enum(properties: List[Any], name: str, enum_map: Dict[int, str]) -> Optional[str]:
    """从属性列表中提取枚举值的名称。"""
    val = _extract_property(properties, name)
    if val is None:
        return None
    # EnumValue wrapper
    if hasattr(val, "value_name"):
        return val.value_name
    if isinstance(val, int):
        return enum_map.get(val, f"Unknown({val})")
    if isinstance(val, str):
        return val
    return None


def parse_sound_wave(
    archive: Any,
    name_map: List[str],
    export: Optional[Any] = None,
) -> Dict[str, Any]:
    """解析 USoundWave 资产的 custom serialization 数据。

    Args:
        archive: FArchive 实例（已定位到 Super::Serialize 之后的自定义 payload 起始位置）
        name_map: 名称表
        export: ObjectExport 实例（可选，用于提取已解析的 UPROPERTY 属性）

    Returns:
        解析结果字典，包含 sound 语义元数据
    """
    result: Dict[str, Any] = {
        "parse_status": "success",
    }

    # === Custom Serialize data (after Super::Serialize / tagged properties) ===
    # SoundWave.cpp:1278-1302 — Flags uint32
    try:
        flags = archive.read_u32("SoundWave.Flags")
    except (struct.error, OSError, ParseError) as e:
        logger.debug("SoundWave: failed to read Flags: %s", e)
        result["parse_status"] = "partial"
        result["error"] = f"Failed to read Flags: {e}"
        return result

    is_cooked = bool(flags & _COOKED_FLAG)
    has_owner_loading_behavior = bool(flags & _HAS_OWNER_LOADING_BEHAVIOR_FLAG)
    loading_behavior_value = (flags >> _LOADING_BEHAVIOR_SHIFT) & _LOADING_BEHAVIOR_MASK

    handler_data: Dict[str, Any] = {
        "flags": flags,
        "is_cooked": is_cooked,
        "has_owner_loading_behavior": has_owner_loading_behavior,
    }

    if has_owner_loading_behavior:
        handler_data["owner_loading_behavior"] = _LOADING_BEHAVIOR_NAMES.get(
            loading_behavior_value, f"Unknown({loading_behavior_value})"
        )

    result.update(handler_data)

    # === 构建 sound 语义元数据（从 UPROPERTY 属性提取） ===
    properties: List[Any] = []
    if export is not None:
        properties = getattr(export, "properties", [])

    if properties:
        sound_metadata = build_sound_metadata(handler_data, properties)
        if sound_metadata:
            result["sound"] = sound_metadata
            result["format"] = "uasset_read.sound_semantic"
        else:
            # 属性存在但没有可用的 sound 字段
            result["format"] = "uasset_read.sound_partial"
    else:
        # 无属性可用 — 仅 flags 信息
        result["format"] = "uasset_read.sound_flags_only"

    return result


def build_sound_metadata(
    handler_data: Dict[str, Any],
    properties: List[Any],
) -> Dict[str, Any]:
    """从 handler 数据和已解析的 UPROPERTY 属性中构建 sound 语义元数据。

    这是 sound_semantic 格式的核心：确保 output 总是包含非空的 sound 块。

    Args:
        handler_data: parse_sound_wave() 返回的 custom serialize 数据
        properties: 已解析的 UPROPERTY tagged properties

    Returns:
        sound 语义元数据字典（保证非空）
    """
    sound: Dict[str, Any] = {}

    # --- 从 UPROPERTY 标签属性提取语义字段 ---

    # 基础音频属性 (SoundWave.h:791-822)
    sample_rate = _extract_int(properties, "SampleRate")
    if sample_rate is not None:
        sound["sample_rate"] = sample_rate

    imported_sample_rate = _extract_int(properties, "ImportedSampleRate")
    if imported_sample_rate is not None:
        sound["imported_sample_rate"] = imported_sample_rate

    num_channels = _extract_int(properties, "NumChannels")
    if num_channels is not None:
        sound["num_channels"] = num_channels

    duration = _extract_float(properties, "Duration")
    if duration is not None:
        sound["duration"] = duration

    # 播放控制 (SoundWave.h:782-788)
    volume = _extract_float(properties, "Volume")
    if volume is not None:
        sound["volume"] = volume

    pitch = _extract_float(properties, "Pitch")
    if pitch is not None:
        sound["pitch"] = pitch

    # 压缩格式 (SoundWave.h:424-468)
    compression_type = _extract_enum(
        properties, "SoundAssetCompressionType", _COMPRESSION_TYPE_NAMES
    )
    if compression_type is not None:
        sound["compression_type"] = compression_type

    compression_quality = _extract_int(properties, "CompressionQuality")
    if compression_quality is not None:
        sound["compression_quality"] = compression_quality

    # 播放标志 (SoundWave.h:446-455) — 只在 True 时输出
    b_looping = _extract_bool(properties, "bLooping")
    if b_looping:
        sound["looping"] = True

    b_streaming = _extract_bool(properties, "bStreaming")
    if b_streaming:
        sound["streaming"] = True

    b_procedural = _extract_bool(properties, "bProcedural")
    if b_procedural:
        sound["procedural"] = True

    # Sound group (SoundWave.h:442)
    sound_group = _extract_enum(properties, "SoundGroup", _SOUND_GROUP_NAMES)
    if sound_group is not None:
        sound["sound_group"] = sound_group

    # Subtitle properties (SoundWave.h:685-779)
    subtitle_priority = _extract_float(properties, "SubtitlePriority")
    if subtitle_priority is not None:
        sound["subtitle_priority"] = subtitle_priority

    b_mature = _extract_bool(properties, "bMature")
    if b_mature:
        sound["mature"] = True

    # Loading behavior from UPROPERTY (SoundWave.h:760-761)
    loading_behavior = _extract_enum(
        properties, "LoadingBehavior", _LOADING_BEHAVIOR_NAMES
    )
    if loading_behavior is not None:
        sound["loading_behavior"] = loading_behavior

    # --- 从 custom serialize 数据补充 ---
    if handler_data.get("is_cooked") is not None:
        sound["is_cooked"] = handler_data["is_cooked"]

    if handler_data.get("owner_loading_behavior") is not None:
        sound["owner_loading_behavior"] = handler_data["owner_loading_behavior"]

    # 派生信息
    if sample_rate is not None and duration is not None and duration > 0:
        sound["estimated_frame_count"] = int(sample_rate * duration)

    # 通道描述
    if num_channels is not None:
        if num_channels == 1:
            sound["channel_layout"] = "mono"
        elif num_channels == 2:
            sound["channel_layout"] = "stereo"
        elif num_channels == 5:
            sound["channel_layout"] = "5.1"
        elif num_channels == 7:
            sound["channel_layout"] = "7.1"
        else:
            sound["channel_layout"] = f"{num_channels}ch"

    return sound
