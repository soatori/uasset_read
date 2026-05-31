"""网格体资产类型"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from uasset_read.objects.uobject import UObject
from uasset_read.objects.registry import global_registry


@global_registry.register("StaticMesh")
@dataclass
class UStaticMesh(UObject):
    """静态网格体

    等价实现 UStaticMesh.cs
    """
    # LOD 数据
    lod_groups: List[Any] = field(default_factory=list)

    # 渲染数据
    render_data: Optional[Dict[str, Any]] = None

    # 光照贴图
    lightmap_resolution: int = 0

    def deserialize(self, archive: 'FArchive', offset: int, size: int) -> None:
        """反序列化静态网格体"""
        # TODO: 实现完整的 StaticMesh 反序列化
        pass


@global_registry.register("SkeletalMesh")
@dataclass
class USkeletalMesh(UObject):
    """骨骼网格体

    等价实现 USkeletalMesh.cs
    """
    # 骨骼信息
    ref_skeleton: Optional[Dict[str, Any]] = None

    # LOD 数据
    lod_models: List[Any] = field(default_factory=list)

    def deserialize(self, archive: 'FArchive', offset: int, size: int) -> None:
        """反序列化骨骼网格体"""
        # TODO: 实现完整的 SkeletalMesh 反序列化
        pass
