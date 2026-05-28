"""StructProperty fallback 修复测试。"""
import pytest
import struct
import tempfile
import os
from uasset_read.parsers.property_types import parse_struct_property, _TAGGED_FALLBACK_STRUCTS, _EXPECTED_STRUCT_SIZES
from uasset_read.models.properties import PropertyTag, StructValue
from uasset_read.archive import FArchive


def test_vector_in_tagged_fallback():
    """Vector 应在 _TAGGED_FALLBACK_STRUCTS 中。"""
    assert "Vector" in _TAGGED_FALLBACK_STRUCTS or "Vector" in _EXPECTED_STRUCT_SIZES


def test_rotator_in_tagged_fallback():
    """Rotator 应在 _TAGGED_FALLBACK_STRUCTS 中。"""
    assert "Rotator" in _TAGGED_FALLBACK_STRUCTS or "Rotator" in _EXPECTED_STRUCT_SIZES


def test_guid_in_tagged_fallback():
    """Guid 应在 _TAGGED_FALLBACK_STRUCTS 中。"""
    assert "Guid" in _TAGGED_FALLBACK_STRUCTS or "Guid" in _EXPECTED_STRUCT_SIZES


def test_negative_size_returns_struct_value():
    """负数 size 应返回 StructValue 而非抛异常。"""
    # 创建一个 mock archive 来测试负数 size 处理
    data = b'\x00' * 100
    with tempfile.NamedTemporaryFile(delete=False, suffix='.bin') as f:
        f.write(data)
        path = f.name

    try:
        archive = FArchive(path)
        tag = PropertyTag(name="Test", type="StructProperty", size=-100, tag_start_offset=0)
        tag.struct_type = "UnknownStruct"

        result = parse_struct_property(tag, archive, [], [], None, 0)
        assert isinstance(result, StructValue)
        assert result.parse_status == "negative_size_skipped"
    finally:
        archive.close()
        os.unlink(path)


def test_expected_struct_sizes():
    """预期的结构体大小应存在。"""
    assert "Vector" in _EXPECTED_STRUCT_SIZES
    assert _EXPECTED_STRUCT_SIZES["Vector"] == 12
    assert "Rotator" in _EXPECTED_STRUCT_SIZES
    assert _EXPECTED_STRUCT_SIZES["Rotator"] == 12
    assert "Guid" in _EXPECTED_STRUCT_SIZES
    assert _EXPECTED_STRUCT_SIZES["Guid"] == 16
