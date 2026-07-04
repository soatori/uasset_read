"""UPoseAsset 资产类型处理器（opaque partial metadata）。

UPoseAsset::Serialize 仅调用 Super::Serialize，数据通过 UPROPERTY 序列化
（PoseNames TArray<FName>、PoseValues TArray<FTransform>）。
Handler 提供类型识别。
"""
from __future__ import annotations

from typing import Any


def parse_pose_asset(archive: Any, name_map: list[str]) -> dict[str, Any]:
    """提取 PoseAsset 原始字节样本（opaque partial metadata）。"""
    start = archive.tell()
    remaining = max(0, archive.total_size() - start)
    sample = archive.read(min(remaining, 256))
    return {
        "raw_offset": start,
        "sample_size": len(sample),
        "parse_status": "partial_metadata",
    }
