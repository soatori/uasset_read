"""SoftObjectPath 索引解析测试（UE5.7+）。

验证当 SoftObjectPathList 存在时，SoftObjectProperty 应读取 int32 索引
而非 FString 对。

参考：LinkerLoad.cpp:6450
"""
import struct
from io import BytesIO
from unittest.mock import MagicMock

import pytest

from uasset_read.parsers.property_types import (
    parse_soft_object_property,
    parse_soft_class_property,
)
from uasset_read.models.properties import PropertyTag, SoftObjectPathValue


class MockArchive:
    """模拟 FArchive 用于测试。"""

    def __init__(self, data: bytes):
        self._stream = BytesIO(data)

    def read_i32(self) -> int:
        return struct.unpack('<i', self._stream.read(4))[0]

    def read_fstring(self) -> str:
        length = struct.unpack('<i', self._stream.read(4))[0]
        if length == 0:
            return ""
        data = self._stream.read(length - 1)  # -1 for null terminator
        self._stream.read(1)  # skip null terminator
        return data.decode('utf-8')

    def tell(self) -> int:
        return self._stream.tell()

    def seek(self, pos: int):
        self._stream.seek(pos)


def _fname(s: str) -> bytes:
    """序列化 FName（长度前缀 + 数据 + null 终止符）。"""
    encoded = s.encode('utf-8')
    return struct.pack('<i', len(encoded) + 1) + encoded + b'\x00'


def _fstring(s: str) -> bytes:
    """序列化 FString（长度前缀 + 数据 + null 终止符）。"""
    if not s:
        return struct.pack('<i', 0)
    encoded = s.encode('utf-8')
    return struct.pack('<i', len(encoded) + 1) + encoded + b'\x00'


# ============================================================================
# Tests for index-based resolution (UE5.7+)
# ============================================================================

class TestIndexBasedResolution:
    """测试索引化 SoftObjectProperty 解析。"""

    def test_valid_index_resolution(self):
        """有效索引应正确解析到 SoftObjectPathList 条目。"""
        tag = PropertyTag(name="Test", type="SoftObjectProperty", size=4)
        soft_list = [
            {"asset_path": "/Game/Content/MyAsset", "sub_path": "SubPath"},
            {"asset_path": "/Engine/Content/Other", "sub_path": ""},
        ]
        # Index 1 (second entry)
        archive = MockArchive(struct.pack('<i', 1))

        result = parse_soft_object_property(tag, archive, [], soft_list)

        assert isinstance(result, SoftObjectPathValue)
        assert result.index == 1
        assert result.asset_path == "/Engine/Content/Other"
        assert result.sub_path == ""
        assert result.error is None

    def test_index_out_of_bounds(self):
        """越界索引应返回错误诊断。"""
        tag = PropertyTag(name="Test", type="SoftObjectProperty", size=4)
        soft_list = [{"asset_path": "/Game/Asset", "sub_path": ""}]
        # Index 5 but list has only 1 entry
        archive = MockArchive(struct.pack('<i', 5))

        result = parse_soft_object_property(tag, archive, [], soft_list)

        assert isinstance(result, SoftObjectPathValue)
        assert result.index == 5
        assert result.asset_path == ""
        assert result.error is not None
        assert "out of bounds" in result.error

    def test_negative_index(self):
        """负数索引应返回错误诊断。"""
        tag = PropertyTag(name="Test", type="SoftObjectProperty", size=4)
        soft_list = [{"asset_path": "/Game/Asset", "sub_path": ""}]
        archive = MockArchive(struct.pack('<i', -1))

        result = parse_soft_object_property(tag, archive, [], soft_list)

        assert isinstance(result, SoftObjectPathValue)
        assert result.index == -1
        assert result.error is not None

    def test_zero_index(self):
        """索引 0 应正确解析第一个条目。"""
        tag = PropertyTag(name="Test", type="SoftObjectProperty", size=4)
        soft_list = [
            {"asset_path": "/First/Asset", "sub_path": "FirstSub"},
            {"asset_path": "/Second/Asset", "sub_path": ""},
        ]
        archive = MockArchive(struct.pack('<i', 0))

        result = parse_soft_object_property(tag, archive, [], soft_list)

        assert result.index == 0
        assert result.asset_path == "/First/Asset"
        assert result.sub_path == "FirstSub"
        assert result.error is None


# ============================================================================
# Tests for legacy FString-based resolution
# ============================================================================

class TestLegacyFStringResolution:
    """测试传统 FString 格式解析。"""

    def test_legacy_format_with_empty_list(self):
        """空列表应回退到 FString 格式。"""
        tag = PropertyTag(name="Test", type="SoftObjectProperty", size=20)
        archive = MockArchive(_fstring("/Game/Legacy") + _fstring("SubPath"))

        result = parse_soft_object_property(tag, archive, [], [])

        assert isinstance(result, SoftObjectPathValue)
        assert result.index is None
        assert result.asset_path == "/Game/Legacy"
        assert result.sub_path == "SubPath"

    def test_legacy_format_with_none_list(self):
        """None 列表应使用 FString 格式。"""
        tag = PropertyTag(name="Test", type="SoftObjectProperty", size=20)
        archive = MockArchive(_fstring("/Game/Legacy") + _fstring(""))

        result = parse_soft_object_property(tag, archive, [], None)

        assert isinstance(result, SoftObjectPathValue)
        assert result.index is None
        assert result.asset_path == "/Game/Legacy"
        assert result.sub_path == ""

    def test_legacy_format_empty_strings(self):
        """传统格式可以有空字符串。"""
        tag = PropertyTag(name="Test", type="SoftObjectProperty", size=8)
        archive = MockArchive(_fstring("") + _fstring(""))

        result = parse_soft_object_property(tag, archive, [], None)

        assert result.asset_path == ""
        assert result.sub_path == ""


# ============================================================================
# Tests for SoftClassProperty
# ============================================================================

class TestSoftClassProperty:
    """测试 SoftClassProperty 解析（与 SoftObjectProperty 相同逻辑）。"""

    def test_index_based_soft_class_property(self):
        """SoftClassProperty 也应支持索引解析。"""
        tag = PropertyTag(name="TestClass", type="SoftClassProperty", size=4)
        soft_list = [
            {"asset_path": "/Game/Classes/MyClass", "sub_path": ""},
        ]
        archive = MockArchive(struct.pack('<i', 0))

        result = parse_soft_class_property(tag, archive, [], soft_list)

        assert isinstance(result, SoftObjectPathValue)
        assert result.index == 0
        assert result.asset_path == "/Game/Classes/MyClass"
        assert result.raw_kind == "SoftClassProperty"

    def test_legacy_soft_class_property(self):
        """SoftClassProperty 传统格式。"""
        tag = PropertyTag(name="TestClass", type="SoftClassProperty", size=20)
        archive = MockArchive(_fstring("/Game/LegacyClass") + _fstring(""))

        result = parse_soft_class_property(tag, archive, [], None)

        assert result.asset_path == "/Game/LegacyClass"
        assert result.index is None


# ============================================================================
# Integration-level tests
# ============================================================================

class TestIntegration:
    """集成级别测试。"""

    def test_soft_object_path_value_structure(self):
        """验证 SoftObjectPathValue 结构包含所有字段。"""
        value = SoftObjectPathValue(
            raw_kind="SoftObjectProperty",
            asset_path="/Game/Asset",
            sub_path="Sub",
            index=3,
            error=None,
        )
        assert value.raw_kind == "SoftObjectProperty"
        assert value.asset_path == "/Game/Asset"
        assert value.sub_path == "Sub"
        assert value.index == 3
        assert value.error is None

    def test_empty_soft_object_path_list_uses_legacy(self):
        """空的 soft_object_path_list 应使用传统格式。"""
        tag = PropertyTag(name="Test", type="SoftObjectProperty", size=16)
        archive = MockArchive(_fstring("/Fallback") + _fstring("Path"))

        # Empty list triggers legacy mode
        result = parse_soft_object_property(tag, archive, [], [])

        assert result.index is None
        assert result.asset_path == "/Fallback"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
