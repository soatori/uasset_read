"""Material 属性提取测试。"""
import pytest
import struct
from uasset_read.parsers.asset_types.material import parse_material


def test_material_parser_importable():
    """parse_material 函数应可导入。"""
    assert callable(parse_material)


def test_material_parser_returns_dict():
    """parse_material 应返回字典。"""
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

    # used_with_static_lighting=1, blend_mode=0, shading_model=0, expression_count=5
    data = b'\x01' + struct.pack('<iii', 0, 0, 5)
    mock = MockArchive(data)
    result = parse_material(mock, [])
    assert isinstance(result, dict)
    assert result.get("used_with_static_lighting") is True
    assert result.get("blend_mode") == 0
    assert result.get("shading_model") == 0
    assert result.get("expression_count") == 5
