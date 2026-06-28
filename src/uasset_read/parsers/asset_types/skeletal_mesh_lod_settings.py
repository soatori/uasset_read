"""USkeletalMeshLODSettings 资产类型处理器（opaque partial metadata）。

USkeletalMeshLODSettings 使用标准 UPROPERTY 序列化，包含骨骼网格 LOD 配置。
Handler 提供类型识别。
"""
from __future__ import annotations

from typing import Any


def parse_skeletal_mesh_lod_settings(archive: Any, name_map: list[str]) -> dict[str, Any]:
    """提取 SkeletalMeshLODSettings 原始字节样本（opaque partial metadata）。"""
    start = archive.tell()
    remaining = max(0, archive.total_size() - start)
    sample = archive.read(min(remaining, 256))
    return {
        "raw_offset": start,
        "sample_size": len(sample),
        "parse_status": "partial_metadata",
    }
