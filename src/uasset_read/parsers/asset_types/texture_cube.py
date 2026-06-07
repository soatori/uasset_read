"""TextureCube 资产属性提取器。

参考 UTextureCube 序列化格式：
  与 UTexture2D 类似，但包含 6 个面的数据（立方体贴图）。
  布局：ImportedSize → AddressX/Y → bCooked → PixelFormat → 每面 MIP 元数据
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict

if TYPE_CHECKING:
    from uasset_read.archive import FArchive


# TextureCube 的面数（立方体贴图固定 6 面）
_TEXTURE_CUBE_FACE_COUNT = 6


def parse_texture_cube(archive: FArchive, name_map: list[str]) -> dict[str, Any]:
    """解析 TextureCube 资产的核心属性。

    支持两种布局：
    1. UTCB 魔数格式（自定义，含面级元数据）
    2. 标准 UTextureCube 格式：ImportedSize → AddressX/Y → bCooked → PixelFormat
    """
    result: Dict[str, Any] = {}
    start = archive.tell()

    # 检查 UTCB 魔数（至少需要 16 字节）
    if archive.total_size() - start >= 16:
        magic = archive.read(4)
        if magic == b"UTCB":
            result["imported_size_x"] = archive.read_i32()
            result["imported_size_y"] = archive.read_i32()
            result["pixel_format"] = archive.read_i32()
            mip_count = archive.read_i32()
            result["mip_count"] = mip_count
            result["face_count"] = _TEXTURE_CUBE_FACE_COUNT
            # 每面的 MIP 数据
            faces = []
            for face_idx in range(_TEXTURE_CUBE_FACE_COUNT):
                mips = []
                for _ in range(max(0, mip_count)):
                    mips.append({
                        "size_x": archive.read_i32(),
                        "size_y": archive.read_i32(),
                        "bulk_offset": archive.read_u64(),
                        "bulk_size": archive.read_u64(),
                    })
                faces.append({"face_index": face_idx, "mips": mips})
            result["faces"] = faces
            result["parse_status"] = "metadata"
            result["raw_offset"] = start
            result["raw_size"] = archive.tell() - start
            return result
        # 非 UTCB：回退到标准格式
        archive.seek(start)

    # 标准 UTextureCube 布局（与 UTexture2D 相同）
    result["imported_size_x"] = archive.read_i32()
    result["imported_size_y"] = archive.read_i32()

    # AddressX, AddressY (纹理寻址模式)
    result["address_x"] = archive.read_i32()
    result["address_y"] = archive.read_i32()

    # bCooked
    b_cooked = archive.read_u8() == 1
    result["b_cooked"] = b_cooked
    result["face_count"] = _TEXTURE_CUBE_FACE_COUNT

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
