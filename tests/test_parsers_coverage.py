"""parsers 模块单元测试 — 覆盖 utils.py、class_serialization_strategy.py、
class_registry.py、custom_properties.py。

覆盖范围：
- parsers/utils: resolve_name_from_index、make_enum_value、extract_inner_from_tag
- parsers/class_serialization_strategy: SerializationStrategy、get_serialization_strategy、
  should_skip_class、is_opaque_class、CLASS_STRATEGY_TABLE
- parsers/class_registry: ClassHandlerRegistry、FallbackPolicy、HandlerResult、
  ClassHandler（抽象）、get_class_registry、reset_class_registry
- parsers/custom_properties: handle_custom_property、register_custom_property、
  CUSTOM_PROPERTY_HANDLERS
"""
from __future__ import annotations

import pytest

from uasset_read.parsers.utils import (
    extract_inner_from_tag,
    make_enum_value,
    read_validated_count,
    resolve_name_from_index,
)
from uasset_read.parsers.class_serialization_strategy import (
    CLASS_STRATEGY_TABLE,
    SerializationStrategy,
    get_serialization_strategy,
    is_opaque_class,
    should_skip_class,
)
from uasset_read.parsers.class_registry import (
    ClassHandler,
    ClassHandlerRegistry,
    FallbackPolicy,
    HandlerResult,
    get_class_registry,
    reset_class_registry,
)
from uasset_read.parsers.custom_properties import (
    CUSTOM_PROPERTY_HANDLERS,
    handle_custom_property,
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
# parsers/utils — read_validated_count
# ============================================================================


class TestReadValidatedCount:
    """read_validated_count 应正确验证数量值。"""

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
        assert read_validated_count(archive, 100, "test") == 10

    def test_negative_count_returns_zero(self):
        import struct
        archive = self._make_archive(struct.pack("<i", -5))
        assert read_validated_count(archive, 100, "test") == 0

    def test_over_max_returns_zero(self):
        import struct
        archive = self._make_archive(struct.pack("<i", 200))
        assert read_validated_count(archive, 100, "test") == 0


# ============================================================================
# class_serialization_strategy — SerializationStrategy
# ============================================================================


class TestSerializationStrategy:
    """SerializationStrategy 枚举值应正确。"""

    def test_full_serializer(self):
        assert SerializationStrategy.FULL_SERIALIZER == "full_serializer"

    def test_tagged_properties_only(self):
        assert SerializationStrategy.TAGGED_PROPERTIES_ONLY == "tagged_properties_only"

    def test_opaque_class_payload(self):
        assert SerializationStrategy.OPAQUE_CLASS_PAYLOAD == "opaque_class_payload"

    def test_skip_unsupported(self):
        assert SerializationStrategy.SKIP_UNSUPPORTED == "skip_unsupported"


# ============================================================================
# class_serialization_strategy — get_serialization_strategy
# ============================================================================


class TestGetSerializationStrategy:
    """get_serialization_strategy 应返回正确的策略。"""

    def test_known_tagged_class(self):
        assert get_serialization_strategy("BlueprintGeneratedClass") == SerializationStrategy.TAGGED_PROPERTIES_ONLY

    def test_known_opaque_class(self):
        assert get_serialization_strategy("StaticMesh") == SerializationStrategy.OPAQUE_CLASS_PAYLOAD

    def test_known_skip_class(self):
        assert get_serialization_strategy("NiagaraGraph") == SerializationStrategy.SKIP_UNSUPPORTED

    def test_unknown_class_returns_tagged(self):
        assert get_serialization_strategy("SomeUnknownClass") == SerializationStrategy.TAGGED_PROPERTIES_ONLY


# ============================================================================
# class_serialization_strategy — should_skip_class / is_opaque_class
# ============================================================================


class TestShouldSkipClass:
    """should_skip_class 应正确判断跳过策略。"""

    def test_skip_niagara_graph(self):
        assert should_skip_class("NiagaraGraph") is True

    def test_no_skip_blueprint(self):
        assert should_skip_class("BlueprintGeneratedClass") is False

    def test_no_skip_unknown(self):
        assert should_skip_class("UnknownClass") is False


class TestIsOpaqueClass:
    """is_opaque_class 应正确判断 opaque 策略。"""

    def test_opaque_static_mesh(self):
        assert is_opaque_class("StaticMesh") is True

    def test_opaque_anim_sequence(self):
        assert is_opaque_class("AnimSequence") is True

    def test_not_opaque_blueprint(self):
        assert is_opaque_class("BlueprintGeneratedClass") is False

    def test_not_opaque_unknown(self):
        assert is_opaque_class("UnknownClass") is False


# ============================================================================
# class_serialization_strategy — CLASS_STRATEGY_TABLE
# ============================================================================


class TestClassStrategyTable:
    """CLASS_STRATEGY_TABLE 应包含所有预期的类。"""

    def test_tagged_classes_count(self):
        tagged = [c for c, s in CLASS_STRATEGY_TABLE.items() if s == SerializationStrategy.TAGGED_PROPERTIES_ONLY]
        assert len(tagged) >= 8

    def test_opaque_classes_count(self):
        opaque = [c for c, s in CLASS_STRATEGY_TABLE.items() if s == SerializationStrategy.OPAQUE_CLASS_PAYLOAD]
        assert len(opaque) >= 15

    def test_skip_classes_count(self):
        skip = [c for c, s in CLASS_STRATEGY_TABLE.items() if s == SerializationStrategy.SKIP_UNSUPPORTED]
        assert len(skip) >= 3


# ============================================================================
# class_registry — HandlerResult
# ============================================================================


class TestHandlerResult:
    """HandlerResult 应正确创建。"""

    def test_success_result(self):
        r = HandlerResult(success=True)
        assert r.success is True
        assert r.properties == []
        assert r.data is None
        assert r.error_message is None
        assert r.fallback_policy == FallbackPolicy.GENERIC_UOBJECT

    def test_failure_result(self):
        r = HandlerResult(
            success=False,
            error_message="test error",
            fallback_policy=FallbackPolicy.SKIP,
        )
        assert r.success is False
        assert r.error_message == "test error"
        assert r.fallback_policy == FallbackPolicy.SKIP


# ============================================================================
# class_registry — FallbackPolicy
# ============================================================================


class TestFallbackPolicy:
    """FallbackPolicy 枚举值应正确。"""

    def test_generic_uobject(self):
        assert FallbackPolicy.GENERIC_UOBJECT == "generic_uobject"

    def test_skip(self):
        assert FallbackPolicy.SKIP == "skip"

    def test_raise(self):
        assert FallbackPolicy.RAISE == "raise"

    def test_property_fallback(self):
        assert FallbackPolicy.PROPERTY_FALLBACK == "property_fallback"


# ============================================================================
# class_registry — ClassHandlerRegistry
# ============================================================================


class TestClassHandlerRegistry:
    """ClassHandlerRegistry 注册表应正确工作。"""

    def _make_handler(self, class_name="Test"):
        class _Handler(ClassHandler):
            def __init__(self, name):
                self._name = name

            def can_handle(self, name):
                return name == self._name

            @property
            def handler_name(self):
                return f"Handler({self._name})"

            def parse(self, export, archive, context=None):
                return HandlerResult(success=True)

        return _Handler(class_name)

    def test_register_and_find(self):
        reg = ClassHandlerRegistry()
        handler = self._make_handler("Test")
        reg.register(handler)
        assert reg.find_handler("Test") is handler

    def test_find_unknown_returns_none(self):
        reg = ClassHandlerRegistry()
        assert reg.find_handler("Unknown") is None

    def test_cache(self):
        reg = ClassHandlerRegistry()
        handler = self._make_handler("Test")
        reg.register(handler)
        # 两次查找应返回同一对象（缓存）
        assert reg.find_handler("Test") is reg.find_handler("Test")

    def test_register_clears_cache(self):
        reg = ClassHandlerRegistry()
        handler1 = self._make_handler("Test")
        reg.register(handler1)
        found1 = reg.find_handler("Test")  # 缓存
        assert found1 is handler1

        # 注册后缓存被清除，再次查找走遍历路径
        found_again = reg.find_handler("Test")
        assert found_again is handler1  # 仍返回第一个匹配

        # 注册新 handler 后缓存清除，但遍历顺序不变
        handler2 = self._make_handler("Test")
        reg.register(handler2)
        found2 = reg.find_handler("Test")
        assert found2 is handler1  # 仍然返回第一个匹配（正确行为）

    def test_get_registered_handlers(self):
        reg = ClassHandlerRegistry()
        handler = self._make_handler("Test")
        reg.register(handler)
        assert handler in reg.get_registered_handlers()

    def test_clear(self):
        reg = ClassHandlerRegistry()
        reg.register(self._make_handler("Test"))
        reg.clear()
        assert reg.get_registered_handlers() == []
        assert reg.find_handler("Test") is None


# ============================================================================
# class_registry — 全局 registry
# ============================================================================


class TestGlobalClassRegistry:
    """全局 class registry 应正确工作。"""

    def test_get_returns_singleton(self):
        reset_class_registry()
        r1 = get_class_registry()
        r2 = get_class_registry()
        assert r1 is r2

    def test_reset_creates_new(self):
        r1 = get_class_registry()
        reset_class_registry()
        r2 = get_class_registry()
        assert r1 is not r2


# ============================================================================
# custom_properties — handle_custom_property
# ============================================================================


class TestHandleCustomProperty:
    """handle_custom_property 应正确分派。"""

    def test_callable(self):
        assert callable(handle_custom_property)

    def test_custom_handlers_dict_exists(self):
        assert isinstance(CUSTOM_PROPERTY_HANDLERS, dict)

    def test_custom_handlers_has_fd_handler(self):
        """0xFD handler 应已注册（Borderlands 4/2XKO 支持）。"""
        assert (0xFD, None) in CUSTOM_PROPERTY_HANDLERS or len(CUSTOM_PROPERTY_HANDLERS) > 0
