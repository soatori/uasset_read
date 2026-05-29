"""测试 Utf8StrProperty 和对象引用属性类型"""
import pytest
from unittest.mock import MagicMock


def test_parse_utf8_str_property():
    """测试 Utf8StrProperty 解析"""
    from uasset_read.parsers.property_types import parse_utf8_str_property

    archive = MagicMock()
    archive.read_fstring.return_value = "Hello UTF-8"

    tag = MagicMock()
    tag.type = "Utf8StrProperty"

    result = parse_utf8_str_property(tag, archive)
    assert result == "Hello UTF-8"
    archive.read_fstring.assert_called_once()


def test_parse_weak_object_property():
    """测试 WeakObjectProperty 解析"""
    from uasset_read.parsers.property_types import parse_weak_object_property

    archive = MagicMock()
    archive.read_i32.return_value = 5

    tag = MagicMock()
    tag.type = "WeakObjectProperty"

    result = parse_weak_object_property(tag, archive)
    assert result == 5
    archive.read_i32.assert_called_once()


def test_parse_lazy_object_property():
    """测试 LazyObjectProperty 解析"""
    from uasset_read.parsers.property_types import parse_lazy_object_property

    archive = MagicMock()
    archive.read_i32.return_value = 10

    tag = MagicMock()
    tag.type = "LazyObjectProperty"

    result = parse_lazy_object_property(tag, archive)
    assert result == 10
    archive.read_i32.assert_called_once()


def test_parse_class_property():
    """测试 ClassProperty 解析"""
    from uasset_read.parsers.property_types import parse_class_property

    archive = MagicMock()
    archive.read_i32.return_value = 15

    tag = MagicMock()
    tag.type = "ClassProperty"

    result = parse_class_property(tag, archive)
    assert result == 15
    archive.read_i32.assert_called_once()


def test_parse_soft_class_property():
    """测试 SoftClassProperty 解析"""
    from uasset_read.parsers.property_types import parse_soft_class_property

    archive = MagicMock()
    archive.read_fstring.side_effect = ["Path", "SubPath"]

    tag = MagicMock()
    tag.type = "SoftClassProperty"

    result = parse_soft_class_property(tag, archive)
    assert result is not None
    assert result["asset_path"] == "Path"
    assert result["sub_path"] == "SubPath"


def test_parse_asset_object_property():
    """测试 AssetObjectProperty 解析"""
    from uasset_read.parsers.property_types import parse_asset_object_property

    archive = MagicMock()
    archive.read_fstring.return_value = "/Game/Assets/MyAsset"

    tag = MagicMock()
    tag.type = "AssetObjectProperty"

    result = parse_asset_object_property(tag, archive)
    assert result == "/Game/Assets/MyAsset"
    archive.read_fstring.assert_called_once()
