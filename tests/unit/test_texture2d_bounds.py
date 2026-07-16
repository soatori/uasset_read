# tests/unit/test_texture2d_bounds.py
"""Texture2D PlatformData 覆盖后的尺寸范围校验测试 (#403)"""
import pytest
from unittest.mock import MagicMock

from uasset_read.objects.exports.texture import UTexture2D, _MAX_TEXTURE_DIMENSION


def _make_texture(**props) -> UTexture2D:
    """构造带指定 properties 的 UTexture2D 实例"""
    tex = UTexture2D(name="TestTexture")
    for k, v in props.items():
        tex.set_property(k, v)
    return tex


def _make_archive() -> MagicMock:
    """构造最小 mock archive"""
    archive = MagicMock()
    archive.tell.return_value = 0
    archive.total_size.return_value = 1024
    return archive


class TestPlatformDataBounds:
    """PlatformData 覆盖尺寸后重新校验"""

    def test_platformdata_negative_sizex_clamped(self):
        """PlatformData 中 SizeX 为负值时应置为 0"""
        tex = _make_texture(
            PlatformData={"SizeX": -100, "SizeY": 256, "PixelFormat": 1, "Mips": []},
        )
        tex.deserialize(_make_archive(), offset=0, size=100)
        assert tex.size_x == 0
        assert tex.size_y == 256

    def test_platformdata_negative_sizey_clamped(self):
        """PlatformData 中 SizeY 为负值时应置为 0"""
        tex = _make_texture(
            PlatformData={"SizeX": 256, "SizeY": -50, "PixelFormat": 1, "Mips": []},
        )
        tex.deserialize(_make_archive(), offset=0, size=100)
        assert tex.size_x == 256
        assert tex.size_y == 0

    def test_platformdata_oversized_sizex_clamped(self):
        """PlatformData 中 SizeX 超过上限时应置为 0"""
        tex = _make_texture(
            PlatformData={"SizeX": _MAX_TEXTURE_DIMENSION + 1, "SizeY": 128, "PixelFormat": 1, "Mips": []},
        )
        tex.deserialize(_make_archive(), offset=0, size=100)
        assert tex.size_x == 0
        assert tex.size_y == 128

    def test_platformdata_oversized_sizey_clamped(self):
        """PlatformData 中 SizeY 超过上限时应置为 0"""
        tex = _make_texture(
            PlatformData={"SizeX": 64, "SizeY": _MAX_TEXTURE_DIMENSION + 999, "PixelFormat": 1, "Mips": []},
        )
        tex.deserialize(_make_archive(), offset=0, size=100)
        assert tex.size_x == 64
        assert tex.size_y == 0

    def test_platformdata_both_invalid_clamped(self):
        """PlatformData 中 SizeX/SizeY 均非法时均置为 0"""
        tex = _make_texture(
            PlatformData={"SizeX": -1, "SizeY": _MAX_TEXTURE_DIMENSION + 1, "PixelFormat": 1, "Mips": []},
        )
        tex.deserialize(_make_archive(), offset=0, size=100)
        assert tex.size_x == 0
        assert tex.size_y == 0

    def test_platformdata_valid_values_preserved(self):
        """合法的 PlatformData 尺寸不应被篡改"""
        tex = _make_texture(
            PlatformData={"SizeX": 1024, "SizeY": 2048, "PixelFormat": 2, "Mips": []},
        )
        tex.deserialize(_make_archive(), offset=0, size=100)
        assert tex.size_x == 1024
        assert tex.size_y == 2048

    def test_imported_invalid_overridden_by_valid_platformdata(self):
        """初始 SizeX 非法但 PlatformData 合法时，PlatformData 覆盖后保留合法值"""
        tex = _make_texture(
            SizeX=99999, SizeY=99999,
            PlatformData={"SizeX": 512, "SizeY": 512, "PixelFormat": 1, "Mips": []},
        )
        tex.deserialize(_make_archive(), offset=0, size=100)
        # 初始校验将 99999 置为 0，PlatformData 再覆盖为 512
        assert tex.size_x == 512
        assert tex.size_y == 512

    def test_imported_valid_overridden_by_invalid_platformdata(self):
        """初始 SizeX 合法但 PlatformData 非法时，PlatformData 覆盖后应置为 0"""
        tex = _make_texture(
            SizeX=256, SizeY=256,
            PlatformData={"SizeX": -10, "SizeY": _MAX_TEXTURE_DIMENSION + 1, "PixelFormat": 1, "Mips": []},
        )
        tex.deserialize(_make_archive(), offset=0, size=100)
        assert tex.size_x == 0
        assert tex.size_y == 0

    def test_no_platformdata_keeps_imported_bounds(self):
        """无 PlatformData 时，初始校验结果应保留"""
        tex = _make_texture(SizeX=200, SizeY=300)
        tex.deserialize(_make_archive(), offset=0, size=100)
        assert tex.size_x == 200
        assert tex.size_y == 300

    def test_zero_boundary_values(self):
        """边界值 0 和 _MAX_TEXTURE_DIMENSION 应被接受"""
        tex = _make_texture(
            PlatformData={"SizeX": 0, "SizeY": _MAX_TEXTURE_DIMENSION, "PixelFormat": 1, "Mips": []},
        )
        tex.deserialize(_make_archive(), offset=0, size=100)
        assert tex.size_x == 0
        assert tex.size_y == _MAX_TEXTURE_DIMENSION
