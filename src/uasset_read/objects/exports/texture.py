"""纹理资产类型"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from uasset_read.objects.uobject import UObject
from uasset_read.objects.registry import global_registry
from uasset_read.objects.exports.helpers import as_list, as_mapping, prop_value


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
    parse_status: str = "opaque"
    raw_offset: int = 0
    raw_size: int = 0

    def deserialize(self, archive: 'FArchive', offset: int, size: int) -> None:
        """Populate lightweight Texture2D metadata.

        This intentionally stops at structured metadata; pixel conversion and
        full platform payload decoding belong to a later exporter layer.
        """
        self.size_x = int(prop_value(self, "SizeX", "ImportedSizeX", "size_x", default=self.size_x) or 0)
        self.size_y = int(prop_value(self, "SizeY", "ImportedSizeY", "size_y", default=self.size_y) or 0)
        self.format = prop_value(self, "PixelFormat", "Format", "format", default=self.format)

        platform_data = prop_value(self, "PlatformData", "CookedPlatformData", "platform_data")
        pdata = as_mapping(platform_data)
        if pdata:
            self.platform_data = pdata
            self.size_x = int(prop_value(pdata, "SizeX", "size_x", default=self.size_x) or 0)
            self.size_y = int(prop_value(pdata, "SizeY", "size_y", default=self.size_y) or 0)
            self.format = prop_value(pdata, "PixelFormat", "Format", "format", default=self.format)
            mips = as_list(prop_value(pdata, "Mips", "mips"))
            self.mip_levels = [_normalize_mip(mip) for mip in mips]

        if not self.mip_levels:
            mips = as_list(prop_value(self, "Mips", "mip_levels"))
            self.mip_levels = [_normalize_mip(mip) for mip in mips]

        if not self.platform_data and any((self.size_x, self.size_y, self.format, self.mip_levels)):
            self.platform_data = {
                "SizeX": self.size_x,
                "SizeY": self.size_y,
                "PixelFormat": self.format,
                "MipCount": len(self.mip_levels),
            }
        self.raw_offset = offset
        self.raw_size = size
        self.parse_status = "metadata" if self.platform_data else "opaque"


@global_registry.register("TextureCube")
@dataclass
class UTextureCube(UObject):
    """立方体纹理"""

    def deserialize(self, archive: 'FArchive', offset: int, size: int) -> None:
        """反序列化立方体纹理"""
        return None


def _normalize_mip(mip: Any) -> Dict[str, Any]:
    data = as_mapping(mip)
    if not data:
        data = {"value": mip}
    return {
        "size_x": prop_value(data, "SizeX", "size_x", default=0),
        "size_y": prop_value(data, "SizeY", "size_y", default=0),
        "bulk_data": prop_value(data, "BulkData", "bulk_data"),
        "data_size": prop_value(data, "DataSize", "data_size", "SizeOnDisk", default=0),
        "raw": data,
    }
