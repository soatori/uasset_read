"""SkeletalMesh 属性提取测试。"""
import pytest
from uasset_read import parse_uasset_with_linker
from uasset_read.parsers.asset_types.skeletal_mesh import parse_skeletal_mesh

FIRSTPERSON_DIR = "E:/Develop/lib/UnrealEngine/Samples/FirstPerson/Content/Weapons/GrenadeLauncher/Meshes"


def test_skeletal_mesh_basic():
    """SKM_GrenadeLauncher 应成功解析并提取基本信息。"""
    result = parse_uasset_with_linker(f"{FIRSTPERSON_DIR}/SKM_GrenadeLauncher.uasset", tolerant=True)
    assert result.is_success


def test_skeletal_mesh_parser_importable():
    """parse_skeletal_mesh 函数应可导入。"""
    assert callable(parse_skeletal_mesh)


def test_skeletal_mesh_parser_returns_dict():
    """parse_skeletal_mesh 应返回字典。"""
    # 创建一个简单的 mock 来测试解析器
    class MockArchive:
        def __init__(self, data):
            self._data = data
            self._pos = 0

        def read_u8(self):
            val = self._data[self._pos]
            self._pos += 1
            return val

        def read_i32(self):
            import struct
            val = struct.unpack('<i', self._data[self._pos:self._pos+4])[0]
            self._pos += 4
            return val

    # 测试未 cooked 的情况
    mock = MockArchive(b'\x00')  # b_cooked = False
    result = parse_skeletal_mesh(mock, [])
    assert isinstance(result, dict)
    assert result.get("b_cooked") is False

    # 测试 cooked 的情况（简化数据）
    # b_cooked=1, bone_count=0, lod_count=0
    import struct
    data = b'\x01' + struct.pack('<i', 0) + struct.pack('<i', 0)
    mock = MockArchive(data)
    result = parse_skeletal_mesh(mock, [])
    assert isinstance(result, dict)
    assert result.get("b_cooked") is True
    assert result.get("bone_count") == 0
    assert result.get("lod_count") == 0
