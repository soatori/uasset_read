"""SoundWave 资产基础属性提取器。

仅提取音频元数据属性（时长、采样率、声道数、格式等），
跳过 BulkData 中的原始音频数据。
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict

if TYPE_CHECKING:
    from uasset_read.archive import FArchive


# UE SoundFormat 枚举映射
_SOUND_FORMAT_NAMES = {
    0: "PCM",
    1: "ADPCM",
    2: "Opus",
    3: "Bink Audio",
    4: "PCM_Procedural",
}


def parse_sound_wave(archive: FArchive, name_map: list[str]) -> dict[str, Any]:
    """解析 SoundWave 资产的基础音频属性。

    参考 USoundWave 序列化格式：
    - num_channels (int32)
    - sample_rate (int32)
    - sound_format (int32 enum)
    - duration (float)
    - bStreaming (bool) — 流式音频

    跳过 BulkData 中的原始音频数据。
    """
    result: Dict[str, Any] = {}
    start = archive.tell()

    # num_channels: 声道数
    result["num_channels"] = archive.read_i32()

    # sample_rate: 采样率 (Hz)
    result["sample_rate"] = archive.read_i32()

    # sound_format: 音频格式枚举
    sf_value = archive.read_i32()
    result["sound_format"] = _SOUND_FORMAT_NAMES.get(sf_value, f"Unknown({sf_value})")
    result["sound_format_raw"] = sf_value

    # duration: 音频时长（秒）
    result["duration"] = archive.read_float()

    # bStreaming: 是否为流式音频
    b_streaming = archive.read_u8() == 1
    result["b_streaming"] = b_streaming

    # 标记状态
    result["parse_status"] = "metadata_only"
    result["note"] = "Raw audio data skipped (BulkData)"

    result["raw_offset"] = start
    result["raw_size"] = archive.tell() - start

    return result
