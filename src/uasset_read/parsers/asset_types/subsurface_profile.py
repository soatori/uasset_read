"""USubsurfaceProfile 资产类型处理器（opaque partial metadata）。

纯 UPROPERTY 序列化，无自定义 Serialize()。
定义次表面散射材质配置参数。
"""
from __future__ import annotations

from typing import Any


def parse_subsurface_profile(archive: Any, name_map: list[str]) -> dict[str, Any]:
    """提取 SubsurfaceProfile 原始字节样本（opaque partial metadata）。"""
    start = archive.tell()
    remaining = max(0, archive.total_size() - start)
    sample = archive.read(min(remaining, 256))
    return {
        "raw_offset": start,
        "sample_size": len(sample),
        "parse_status": "partial_metadata",
    }
