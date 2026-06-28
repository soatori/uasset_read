"""UAnimBoneCompressionSettings 资产类型处理器（opaque partial metadata）。

纯 UPROPERTY 序列化，无自定义 Serialize()。
AnimSequence 使用此类型决定骨骼压缩策略。
"""
from __future__ import annotations

from typing import Any


def parse_anim_bone_compression_settings(archive: Any, name_map: list[str]) -> dict[str, Any]:
    """提取 AnimBoneCompressionSettings 原始字节样本（opaque partial metadata）。"""
    start = archive.tell()
    remaining = max(0, archive.total_size() - start)
    sample = archive.read(min(remaining, 256))
    return {
        "raw_offset": start,
        "sample_size": len(sample),
        "parse_status": "partial_metadata",
    }
