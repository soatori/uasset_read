"""Texture2D 资产属性提取器。

参考 UTexture2D.cs:
  ImportedSize → AddressX/Y → bCooked → PixelFormat → BulkData per MIP
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict

if TYPE_CHECKING:
    from uasset_read.archive import FArchive


def parse_texture2d(archive: FArchive, name_map: list[str]) -> dict[str, Any]:
    """解析 Texture2D 资产的核心属性。"""
    result: Dict[str, Any] = {}

    # ImportedSize (FIntPoint)
    result["imported_size_x"] = archive.read_i32()
    result["imported_size_y"] = archive.read_i32()

    # AddressX, AddressY (纹理寻址模式)
    result["address_x"] = archive.read_i32()
    result["address_y"] = archive.read_i32()

    # bCooked
    b_cooked = archive.read_u8() == 1
    result["b_cooked"] = b_cooked

    if not b_cooked:
        return result

    # 每个像素格式块
    format_count = archive.read_i32()
    result["format_count"] = format_count

    for _ in range(format_count):
        # PixelFormat enum
        pf_value = archive.read_i32()
        result["pixel_format"] = pf_value

        # bIsSrgb
        b_srgb = archive.read_u8() == 1
        result["b_srgb"] = b_srgb

    return result
