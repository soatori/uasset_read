"""Texture2D 属性提取测试。"""
import pytest
from uasset_read import parse_uasset_with_linker
from uasset_read.parsers.asset_types.texture2d import parse_texture2d

STARTER_DIR = "E:/Develop/lib/UnrealEngine/Samples/FirstPerson/Content/Weapons/GrenadeLauncher/Meshes"


def test_texture2d_parser_importable():
    """parse_texture2d 函数应可导入。"""
    assert callable(parse_texture2d)


def test_texture2d_parser_returns_dict():
    """parse_texture2d 应返回字典。"""
    import struct

    class MockArchive:
        def __init__(self, data):
            self._data = data
            self._pos = 0

        def read_u8(self):
            val = self._data[self._pos]
            self._pos += 1
            return val

        def read_i32(self):
            val = struct.unpack('<i', self._data[self._pos:self._pos+4])[0]
            self._pos += 4
            return val

    # 测试未 cooked 的情况
    # imported_size_x, imported_size_y, address_x, address_y, b_cooked=0
    data = struct.pack('<iiii', 512, 512, 0, 0) + b'\x00'
    mock = MockArchive(data)
    result = parse_texture2d(mock, [])
    assert isinstance(result, dict)
    assert result.get("b_cooked") is False
    assert result.get("imported_size_x") == 512
    assert result.get("imported_size_y") == 512

    # 测试 cooked 的情况
    # imported_size_x, imported_size_y, address_x, address_y, b_cooked=1, format_count=1, pf_value=4, b_srgb=1
    data = struct.pack('<iiii', 1024, 1024, 0, 0) + b'\x01' + struct.pack('<i', 1) + struct.pack('<i', 4) + b'\x01'
    mock = MockArchive(data)
    result = parse_texture2d(mock, [])
    assert isinstance(result, dict)
    assert result.get("b_cooked") is True
    assert result.get("imported_size_x") == 1024
    assert result.get("format_count") == 1
    assert result.get("pixel_format") == 4
    assert result.get("b_srgb") is True
