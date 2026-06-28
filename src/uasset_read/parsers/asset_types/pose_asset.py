"""UPoseAsset 资产类型处理器（opaque partial metadata）。

UPoseAsset::Serialize 仅调用 Super::Serialize，数据通过 UPROPERTY 序列化
（PoseNames TArray<FName>、PoseValues TArray<FTransform>）。
Handler 提供类型识别。
"""
from __future__ import annotations

from uasset_read.parsers.asset_types.opaque_stub import make_opaque_stub

parse_pose_asset = make_opaque_stub("PoseAsset")
