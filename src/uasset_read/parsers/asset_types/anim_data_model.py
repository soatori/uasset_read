"""AnimDataModel 资产元数据提取器（partial metadata）。

UAnimDataModel 使用标准 UPROPERTY 序列化（无自定义 Serialize()），
当前仅提取原始字节样本供诊断使用。
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from uasset_read.archive import FArchive


def parse_anim_data_model(archive: FArchive, name_map: list[str]) -> dict[str, Any]:
    """提取 AnimDataModel 原始字节样本（opaque partial metadata）。"""
    start = archive.tell()
    remaining = max(0, archive.total_size() - start)
    sample = archive.read(min(remaining, 256))
    return {
        "raw_offset": start,
        "sample_size": len(sample),
        "parse_status": "partial_metadata",
    }
