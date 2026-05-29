"""测试委托、特殊和 Verse 语言属性类型"""
import pytest
from unittest.mock import MagicMock


def test_parse_multicast_delegate_property():
    """测试 MulticastDelegateProperty 解析"""
    from uasset_read.parsers.property_types import parse_multicast_delegate_property

    archive = MagicMock()
    archive.read_i32.return_value = 2
    archive.read_fstring.return_value = "TestFunc"

    tag = MagicMock()
    tag.type = "MulticastDelegateProperty"

    result = parse_multicast_delegate_property(tag, archive)
    assert result is not None
    assert len(result) == 2


def test_parse_multicast_inline_delegate_property():
    """测试 MulticastInlineDelegateProperty 解析"""
    from uasset_read.parsers.property_types import parse_multicast_inline_delegate_property

    archive = MagicMock()
    archive.read_i32.return_value = 1
    archive.read_fstring.return_value = "InlineFunc"

    tag = MagicMock()
    tag.type = "MulticastInlineDelegateProperty"

    result = parse_multicast_inline_delegate_property(tag, archive)
    assert result is not None


def test_parse_multicast_sparse_delegate_property():
    """测试 MulticastSparseDelegateProperty 解析"""
    from uasset_read.parsers.property_types import parse_multicast_sparse_delegate_property

    archive = MagicMock()
    archive.read_i32.return_value = 1
    archive.read_fstring.return_value = "SparseFunc"

    tag = MagicMock()
    tag.type = "MulticastSparseDelegateProperty"

    result = parse_multicast_sparse_delegate_property(tag, archive)
    assert result is not None


def test_parse_interface_property():
    """测试 InterfaceProperty 解析"""
    from uasset_read.parsers.property_types import parse_interface_property

    archive = MagicMock()
    archive.read_i32.return_value = 20

    tag = MagicMock()
    tag.type = "InterfaceProperty"

    result = parse_interface_property(tag, archive)
    assert result == 20
    archive.read_i32.assert_called_once()


def test_parse_field_path_property():
    """测试 FieldPathProperty 解析"""
    from uasset_read.parsers.property_types import parse_field_path_property

    archive = MagicMock()
    archive.read_i32.return_value = 2
    archive.read_fstring.side_effect = ["Path1", "Path2"]

    tag = MagicMock()
    tag.type = "FieldPathProperty"

    result = parse_field_path_property(tag, archive)
    assert result == {"path": ["Path1", "Path2"]}


def test_parse_optional_property():
    """测试 OptionalProperty 解析"""
    from uasset_read.parsers.property_types import parse_optional_property

    archive = MagicMock()
    archive.read_bool.return_value = False

    tag = MagicMock()
    tag.type = "OptionalProperty"

    result = parse_optional_property(tag, archive)
    assert result == {"has_value": False, "value": None}


def test_parse_verse_string_property():
    """测试 VerseStringProperty 解析"""
    from uasset_read.parsers.property_types import parse_verse_string_property

    archive = MagicMock()
    archive.read_fstring.return_value = "Verse String"

    tag = MagicMock()
    tag.type = "VerseStringProperty"

    result = parse_verse_string_property(tag, archive)
    assert result == "Verse String"
    archive.read_fstring.assert_called_once()


def test_parse_verse_class_property():
    """测试 VerseClassProperty 解析"""
    from uasset_read.parsers.property_types import parse_verse_class_property

    archive = MagicMock()
    archive.read_i32.return_value = 25

    tag = MagicMock()
    tag.type = "VerseClassProperty"

    result = parse_verse_class_property(tag, archive)
    assert result == 25
    archive.read_i32.assert_called_once()


def test_parse_verse_function_property():
    """测试 VerseFunctionProperty 解析"""
    from uasset_read.parsers.property_types import parse_verse_function_property

    archive = MagicMock()
    archive.read_i32.return_value = 30

    tag = MagicMock()
    tag.type = "VerseFunctionProperty"

    result = parse_verse_function_property(tag, archive)
    assert result == 30
    archive.read_i32.assert_called_once()


def test_parse_verse_dynamic_property():
    """测试 VerseDynamicProperty 解析"""
    from uasset_read.parsers.property_types import parse_verse_dynamic_property

    archive = MagicMock()
    archive.read_i32.return_value = 35

    tag = MagicMock()
    tag.type = "VerseDynamicProperty"

    result = parse_verse_dynamic_property(tag, archive)
    assert result == 35
    archive.read_i32.assert_called_once()
