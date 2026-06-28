"""UFoliageType 资产类型处理器（opaque partial metadata）。

UFoliageType 使用标准 UPROPERTY 序列化，包含植被系统的配置数据。
Handler 提供类型识别。
"""
from __future__ import annotations

from typing import Any


def parse_foliage_type(archive: Any, name_map: list[str]) -> dict[str, Any]:
    """提取 FoliageType 原始字节样本（opaque partial metadata）。"""
    start = archive.tell()
    remaining = max(0, archive.total_size() - start)
    sample = archive.read(min(remaining, 256))
    return {
        "raw_offset": start,
        "sample_size": len(sample),
        "parse_status": "partial_metadata",
    }
