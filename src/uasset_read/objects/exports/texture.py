"""纹理资产类型"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from uasset_read.objects.uobject import UObject
from uasset_read.objects.registry import global_registry


@global_registry.register("Texture2D")
@dataclass
class UTexture2D(UObject):
    """2D 纹理

    等价实现 UTexture2D.cs
    """
    # 纹理属性
    size_x: int = 0
    size_y: int = 0
    format: int = 0  # EPixelFormat

    # Mip 数据
    mip_levels: List[Dict[str, Any]] = field(default_factory=list)

    # 偏移表
    platform_data: Optional[Dict[str, Any]] = None

    def deserialize(self, archive: 'FArchive', offset: int, size: int) -> None:
        """反序列化 2D 纹理"""
        # TODO: 实现完整的 Texture2D 反序列化
        pass


@global_registry.register("TextureCube")
@dataclass
class UTextureCube(UObject):
    """立方体纹理"""

    def deserialize(self, archive: 'FArchive', offset: int, size: int) -> None:
        """反序列化立方体纹理"""
        # TODO: 实现
        pass
