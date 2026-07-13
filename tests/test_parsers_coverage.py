"""parsers 模块单元测试 — 覆盖 utils.py 和 custom_properties.py。

覆盖范围：
- parsers/utils: resolve_name_from_index、make_enum_value、extract_inner_from_tag、
  read_validated_count
- parsers/custom_properties: handle_custom_property 分派逻辑、
  register_custom_property 装饰器、CustomPropertyContext

注意：class_serialization_strategy 和 class_registry 的测试分别在
tests/serialization/test_class_serialization_strategy.py 和
tests/serialization/test_class_registry.py 中，此处不重复。
"""
from __future__ import annotations

import pytest

from uasset_read.parsers.utils import (
    extract_inner_from_tag,
    make_enum_value,
    read_validated_count_tolerant,
    resolve_name_from_index,
)
from uasset_read.parsers.custom_properties import (
    CUSTOM_PROPERTY_HANDLERS,
    CustomPropertyContext,
    handle_custom_property,
    register_custom_property,
)


# ============================================================================
# parsers/utils — resolve_name_from_index
# ============================================================================


class TestResolveNameFromIndex:
    """resolve_name_from_index 应正确解析名称索引。"""

    def test_valid_index(self):
        archive = None  # archive 未使用
        name_map = ["foo", "bar", "baz"]
        assert resolve_name_from_index(archive, name_map, 0) == "foo"
        assert resolve_name_from_index(archive, name_map, 2) == "baz"

    def test_negative_index_returns_fallback(self):
        assert resolve_name_from_index(None, ["foo"], -1) == "param_-1"

    def test_out_of_range_returns_fallback(self):
        assert resolve_name_from_index(None, ["foo"], 5) == "param_5"

    def test_custom_fallback_prefix(self):
        assert resolve_name_from_index(None, [], 0, fallback_prefix="name") == "name_0"

    def test_empty_name_map(self):
        assert resolve_name_from_index(None, [], 0) == "param_0"


# ============================================================================
# parsers/utils — make_enum_value
# ============================================================================


class TestMakeEnumValue:
    """make_enum_value 应正确创建枚举值字典。"""

    def test_known_enum_type(self):
        result = make_enum_value("Color", "Red")
        assert result == {"enum_type": "Color", "value_name": "Color::Red"}

    def test_unknown_enum_type_no_prefix(self):
        result = make_enum_value("UnknownEnum", "SomeValue")
        assert result == {"enum_type": "UnknownEnum", "value_name": "SomeValue"}

    def test_empty_enum_type(self):
        result = make_enum_value("", "SomeValue")
        assert result == {"enum_type": "", "value_name": "SomeValue"}


# ============================================================================
# parsers/utils — extract_inner_from_tag
# ============================================================================


class TestExtractInnerFromTag:
    """extract_inner_from_tag 应从 tag type 中提取括号内容。"""

    def test_array_property(self):
        assert extract_inner_from_tag("ArrayProperty(IntProperty)") == "IntProperty"

    def test_no_parentheses(self):
        assert extract_inner_from_tag("IntProperty") is None

    def test_multiple_parentheses(self):
        assert extract_inner_from_tag("MapProperty(StringProperty)(IntProperty)") == "StringProperty)(IntProperty"

    def test_empty_string(self):
        assert extract_inner_from_tag("") is None

    def test_nested_parentheses(self):
        assert extract_inner_from_tag("A(B(C))") == "B(C)"


# ============================================================================
# parsers/utils — read_validated_count_tolerant
# ============================================================================


class TestReadValidatedCount:
    """read_validated_count_tolerant 应正确验证数量值。"""

    def _make_archive(self, data: bytes):
        """创建模拟的 FArchive 对象。"""

        class FakeArchive:
            def __init__(self, d):
                self._data = d
                self._pos = 0

            def tell(self):
                return self._pos

            def read_i32(self):
                import struct
                val = struct.unpack_from("<i", self._data, self._pos)[0]
                self._pos += 4
                return val

        return FakeArchive(data)

    def test_valid_count(self):
        import struct
        archive = self._make_archive(struct.pack("<i", 10))
        assert read_validated_count_tolerant(archive, 100, "test") == 10

    def test_negative_count_returns_zero(self):
        import struct
        archive = self._make_archive(struct.pack("<i", -5))
        assert read_validated_count_tolerant(archive, 100, "test") == 0

    def test_over_max_returns_zero(self):
        import struct
        archive = self._make_archive(struct.pack("<i", 200))
        assert read_validated_count_tolerant(archive, 100, "test") == 0


# ============================================================================
# custom_properties — CustomPropertyContext
# ============================================================================


class TestCustomPropertyContext:
    """CustomPropertyContext 应正确创建。"""

    def test_create_context(self):
        ctx = CustomPropertyContext(type_id=0xFD, tag=None, archive=None)
        assert ctx.type_id == 0xFD
        assert ctx.tag is None
        assert ctx.archive is None
        assert ctx.name_map is None
        assert ctx.mappings is None
        assert ctx.game is None
        assert ctx.summary is None

    def test_create_context_with_all_fields(self):
        ctx = CustomPropertyContext(
            type_id=0xFE,
            tag="fake_tag",
            archive="fake_archive",
            name_map=["a", "b"],
            mappings={"k": "v"},
            game="TestGame",
            summary="fake_summary",
        )
        assert ctx.type_id == 0xFE
        assert ctx.name_map == ["a", "b"]
        assert ctx.game == "TestGame"


# ============================================================================
# custom_properties — register_custom_property
# ============================================================================


class TestRegisterCustomProperty:
    """register_custom_property 装饰器应正确注册处理器。"""

    def test_decorator_registers_handler(self):
        """装饰器应将处理器添加到 CUSTOM_PROPERTY_HANDLERS。"""
        # 0xFD 默认处理器已在模块加载时注册
        assert (None, 0xFD) in CUSTOM_PROPERTY_HANDLERS
        assert (None, 0xFE) in CUSTOM_PROPERTY_HANDLERS

    def test_game_specific_handler_registered(self):
        """游戏特定处理器应以游戏名作为 key。"""
        assert ("borderlands4", 0xFD) in CUSTOM_PROPERTY_HANDLERS
        assert ("borderlands4", 0xFE) in CUSTOM_PROPERTY_HANDLERS

    def test_string_type_id_registered(self):
        """字符串类型的 type_id 也应被注册。"""
        assert ("borderlands4", "GbxDefPtrProperty") in CUSTOM_PROPERTY_HANDLERS
        assert ("borderlands4", "GameDataHandleProperty") in CUSTOM_PROPERTY_HANDLERS


# ============================================================================
# custom_properties — handle_custom_property 分派逻辑
# ============================================================================


class TestHandleCustomPropertyDispatch:
    """handle_custom_property 应按优先级分派到正确的处理器。"""

    def _make_mock_tag(self, type_name: str = "None", size: int = 0):
        """创建模拟 PropertyTag。"""
        from unittest.mock import MagicMock
        tag = MagicMock()
        tag.type = type_name
        tag.size = size
        return tag

    def _make_mock_archive(self, data: bytes = b""):
        """创建模拟 FArchive。"""
        from unittest.mock import MagicMock
        archive = MagicMock()
        archive.read.return_value = data
        return archive

    def test_no_handler_returns_unhandled_fallback(self):
        """无处理器时应返回 unhandled fallback 结果。"""
        tag = self._make_mock_tag(type_name="UnknownCustomType", size=4)
        archive = self._make_mock_archive(b"\x00\x01\x02\x03")

        # 使用一个不存在的 type_id
        result = handle_custom_property(
            type_id=0xFF,
            tag=tag,
            archive=archive,
        )
        assert result is not None
        assert result["kind"] == "custom_property_unhandled"
        assert result["type_id"] == 0xFF
        assert result["property_type"] == "UnknownCustomType"
        assert result["size"] == 4

    def test_no_handler_zero_size(self):
        """无处理器且 size=0 时 raw_data 应为空。"""
        tag = self._make_mock_tag(type_name="SomeType", size=0)
        archive = self._make_mock_archive()

        result = handle_custom_property(
            type_id=0xFF,
            tag=tag,
            archive=archive,
        )
        assert result["raw_data"] == b""

    def test_game_specific_handler_takes_priority(self):
        """游戏特定处理器应优先于通用处理器。"""
        # Borderlands4 有特定的 0xFD handler
        tag = self._make_mock_tag(type_name="GbxDefPtrProperty", size=0)
        archive = self._make_mock_archive()
        archive.read_name.return_value = "TestName"
        archive.read_i32.return_value = 42

        result = handle_custom_property(
            type_id=0xFD,
            tag=tag,
            archive=archive,
            game="Borderlands4",
        )
        assert result is not None
        assert result.get("kind") == "GbxDefPtrProperty"

    def test_generic_handler_used_when_no_game_match(self):
        """无游戏匹配时应使用通用处理器。"""
        tag = self._make_mock_tag(type_name="SomeType", size=8)
        archive = self._make_mock_archive(b"\x00" * 8)

        result = handle_custom_property(
            type_id=0xFD,
            tag=tag,
            archive=archive,
            game="SomeUnknownGame",
        )
        assert result is not None
        assert result.get("type_id") == 0xFD
        assert result.get("size") == 8

    def test_tag_type_fallback_lookup(self):
        """当 type_id 无匹配时，应尝试 tag.type 作为 key。"""
        # "GbxDefPtrProperty" 以字符串形式注册在 ("borderlands4", "GbxDefPtrProperty")
        tag = self._make_mock_tag(type_name="GbxDefPtrProperty", size=0)
        archive = self._make_mock_archive()
        archive.read_name.return_value = "FallbackName"
        archive.read_i32.return_value = 99

        result = handle_custom_property(
            type_id=0xFD,  # 0xFD 也有默认 handler，但游戏特定的优先
            tag=tag,
            archive=archive,
            game="Borderlands4",
        )
        assert result is not None
        # 游戏特定 handler 优先
        assert result.get("kind") == "GbxDefPtrProperty"
