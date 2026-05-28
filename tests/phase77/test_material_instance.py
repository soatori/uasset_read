"""MaterialInstanceConstant 属性提取测试。"""
import pytest
import struct
from uasset_read.parsers.asset_types.material_instance import parse_material_instance


def test_material_instance_parser_importable():
    """parse_material_instance 函数应可导入。"""
    assert callable(parse_material_instance)


def test_material_instance_parser_returns_dict():
    """parse_material_instance 应返回字典。"""
    class MockArchive:
        def __init__(self, data):
            self._data = data
            self._pos = 0

        def read_i32(self):
            val = struct.unpack('<i', self._data[self._pos:self._pos+4])[0]
            self._pos += 4
            return val

        def read_f32(self):
            val = struct.unpack('<f', self._data[self._pos:self._pos+4])[0]
            self._pos += 4
            return val

    # parent_idx=5, scalar_count=1, scalar_name_idx=0, scalar_value=1.0
    # vector_count=0, texture_count=0
    name_map = ["BaseColor"]
    data = struct.pack('<i', 5)  # parent_idx
    data += struct.pack('<i', 1)  # scalar_count
    data += struct.pack('<i', 0)  # param_name_idx
    data += struct.pack('<f', 1.0)  # param_value
    data += struct.pack('<i', 0)  # vector_count
    data += struct.pack('<i', 0)  # texture_count
    mock = MockArchive(data)
    result = parse_material_instance(mock, name_map)
    assert isinstance(result, dict)
    assert result.get("parent_material_index") == 5
    assert result.get("override_count") == 1
    assert result.get("parameter_overrides", {}).get("scalar", {}).get("BaseColor") == 1.0
