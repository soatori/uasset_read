"""AnimSequence 资产基础属性提取器。

仅提取元数据属性（总骨骼数、帧数、序列长度等），
跳过 BulkData 中的压缩骨骼数据。
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict

if TYPE_CHECKING:
    from uasset_read.archive import FArchive


def parse_anim_sequence(archive: FArchive, name_map: list[str]) -> dict[str, Any]:
    """解析 AnimSequence 资产的基础元数据。

    参考 UAnimSequence 序列化格式：
    - num_frames (int32)
    - sequence_length (float)
    - rate_scale (float)
    - bIsCompressed (bool) — 如果为 True，跳过 BulkData

    不解析压缩骨骼数据（需要 AnimCodec 支持）。
    """
    result: Dict[str, Any] = {}
    start = archive.tell()

    # num_frames: 动画帧数
    result["num_frames"] = archive.read_i32()

    # sequence_length: 序列长度（秒）
    result["sequence_length"] = archive.read_float()

    # rate_scale: 播放速率
    result["rate_scale"] = archive.read_float()

    # bIsCompressed: 是否压缩
    b_compressed = archive.read_u8() == 1
    result["b_is_compressed"] = b_compressed

    if b_compressed:
        # 压缩数据需要 AnimCodec 支持，跳过
        result["parse_status"] = "metadata_only"
        result["note"] = "Compressed bone data skipped (requires AnimCodec)"
    else:
        # 未压缩：可以继续读取 raw bone data 头部
        result["parse_status"] = "metadata"

    result["raw_offset"] = start
    result["raw_size"] = archive.tell() - start

    return result
