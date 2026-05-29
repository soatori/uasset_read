"""测试无符号整数属性类型"""
import pytest
from unittest.mock import MagicMock


def test_parse_uint16_property():
    """测试 UInt16Property 解析"""
    from uasset_read.parsers.property_types import parse_uint16_property

    archive = MagicMock()
    archive.read_u16.return_value = 65535

    tag = MagicMock()
    tag.type = "UInt16Property"

    result = parse_uint16_property(tag, archive)
    assert result == 65535
    archive.read_u16.assert_called_once()


def test_parse_uint32_property():
    """测试 UInt32Property 解析"""
    from uasset_read.parsers.property_types import parse_uint32_property

    archive = MagicMock()
    archive.read_u32.return_value = 4294967295

    tag = MagicMock()
    tag.type = "UInt32Property"

    result = parse_uint32_property(tag, archive)
    assert result == 4294967295
    archive.read_u32.assert_called_once()


def test_parse_uint64_property():
    """测试 UInt64Property 解析"""
    from uasset_read.parsers.property_types import parse_uint64_property

    archive = MagicMock()
    archive.read_u64.return_value = 18446744073709551615

    tag = MagicMock()
    tag.type = "UInt64Property"

    result = parse_uint64_property(tag, archive)
    assert result == 18446744073709551615
    archive.read_u64.assert_called_once()
