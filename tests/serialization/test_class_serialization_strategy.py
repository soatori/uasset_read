"""类序列化策略与 Handler Registry 测试。

合并来源:
- test_class_serialization_strategy.py — 类序列化策略表
- test_class_registry.py — Class Handler Registry
"""
import pytest
from uasset_read.parsers.class_serialization_strategy import (
    SerializationStrategy,
    CLASS_STRATEGY_TABLE,
    get_serialization_strategy,
    should_skip_class,
    is_opaque_class,
)
from uasset_read.parsers.class_registry import (
    ClassHandlerRegistry,
    ClassHandler,
    HandlerResult,
    FallbackPolicy,
)


class TestSerializationStrategy:
    """SerializationStrategy 枚举测试。"""

    def test_enum_values(self):
        """枚举值正确定义。"""
        assert SerializationStrategy.TAGGED_PROPERTIES_ONLY.value == "tagged_properties_only"
        assert SerializationStrategy.OPAQUE_CLASS_PAYLOAD.value == "opaque_class_payload"
        assert SerializationStrategy.SKIP_UNSUPPORTED.value == "skip_unsupported"

    def test_enum_is_string(self):
        """枚举继承 str，可直接比较。"""
        assert isinstance(SerializationStrategy.TAGGED_PROPERTIES_ONLY, str)
        assert SerializationStrategy.TAGGED_PROPERTIES_ONLY == "tagged_properties_only"


class TestClassStrategyTable:
    """CLASS_STRATEGY_TABLE 映射表测试。"""

    def test_table_not_empty(self):
        """策略表非空。"""
        assert len(CLASS_STRATEGY_TABLE) > 0

    def test_tagged_properties_classes(self):
        """Tagged properties 类正确映射。"""
        tagged_classes = [
            "BlueprintGeneratedClass",
            "WidgetBlueprintGeneratedClass",
            "Function",
            "UserDefinedStruct",
            "UserDefinedEnum",
            "EdGraph",
            "EdGraphNode",
            "K2Node",
        ]
        for cls in tagged_classes:
            assert cls in CLASS_STRATEGY_TABLE, f"{cls} 未在策略表中"
            assert CLASS_STRATEGY_TABLE[cls] == SerializationStrategy.TAGGED_PROPERTIES_ONLY

    def test_opaque_classes(self):
        """Opaque payload 类正确映射。"""
        opaque_classes = [
            "StaticMesh",
            "SkeletalMesh",
            "Texture2D",
            "TextureCube",
            "Material",
            "MaterialInstanceConstant",
            "AnimSequence",
            "AnimMontage",
            "SoundWave",
            "SoundCue",
            "ParticleSystem",
            "NiagaraSystem",
        ]
        for cls in opaque_classes:
            assert cls in CLASS_STRATEGY_TABLE, f"{cls} 未在策略表中"
            assert CLASS_STRATEGY_TABLE[cls] == SerializationStrategy.OPAQUE_CLASS_PAYLOAD

    def test_skip_classes(self):
        """Skip 类正确映射。"""
        skip_classes = [
            "NiagaraGraph",
            "NiagaraScript",
            "NiagaraDataInterface",
        ]
        for cls in skip_classes:
            assert cls in CLASS_STRATEGY_TABLE, f"{cls} 未在策略表中"
            assert CLASS_STRATEGY_TABLE[cls] == SerializationStrategy.SKIP_UNSUPPORTED


class TestGetSerializationStrategy:
    """get_serialization_strategy() 函数测试。"""

    def test_known_tagged_class(self):
        """已知 tagged properties 类返回正确策略。"""
        strategy = get_serialization_strategy("BlueprintGeneratedClass")
        assert strategy == SerializationStrategy.TAGGED_PROPERTIES_ONLY

    def test_known_opaque_class(self):
        """已知 opaque 类返回正确策略。"""
        strategy = get_serialization_strategy("StaticMesh")
        assert strategy == SerializationStrategy.OPAQUE_CLASS_PAYLOAD

    def test_known_skip_class(self):
        """已知 skip 类返回正确策略。"""
        strategy = get_serialization_strategy("NiagaraGraph")
        assert strategy == SerializationStrategy.SKIP_UNSUPPORTED

    def test_unknown_class_defaults_to_tagged(self):
        """未知类默认返回 TAGGED_PROPERTIES_ONLY。"""
        strategy = get_serialization_strategy("UnknownCustomClass")
        assert strategy == SerializationStrategy.TAGGED_PROPERTIES_ONLY

    def test_empty_string(self):
        """空字符串返回默认策略。"""
        strategy = get_serialization_strategy("")
        assert strategy == SerializationStrategy.TAGGED_PROPERTIES_ONLY


class TestShouldSkipClass:
    """should_skip_class() 函数测试。"""

    def test_skip_class_returns_true(self):
        """Skip 类返回 True。"""
        assert should_skip_class("NiagaraGraph") is True
        assert should_skip_class("NiagaraScript") is True
        assert should_skip_class("NiagaraDataInterface") is True

    def test_opaque_class_returns_false(self):
        """Opaque 类返回 False（不是 skip，是 opaque）。"""
        assert should_skip_class("StaticMesh") is False
        assert should_skip_class("Texture2D") is False

    def test_tagged_class_returns_false(self):
        """Tagged properties 类返回 False。"""
        assert should_skip_class("BlueprintGeneratedClass") is False
        assert should_skip_class("Function") is False

    def test_unknown_class_returns_false(self):
        """未知类返回 False（默认尝试解析）。"""
        assert should_skip_class("SomeUnknownClass") is False


class TestIsOpaqueClass:
    """is_opaque_class() 函数测试。"""

    def test_opaque_class_returns_true(self):
        """Opaque 类返回 True。"""
        assert is_opaque_class("StaticMesh") is True
        assert is_opaque_class("SkeletalMesh") is True
        assert is_opaque_class("Texture2D") is True
        assert is_opaque_class("Material") is True
        assert is_opaque_class("AnimSequence") is True

    def test_skip_class_returns_false(self):
        """Skip 类返回 False（不是 opaque，是 skip）。"""
        assert is_opaque_class("NiagaraGraph") is False
        assert is_opaque_class("NiagaraScript") is False

    def test_tagged_class_returns_false(self):
        """Tagged properties 类返回 False。"""
        assert is_opaque_class("BlueprintGeneratedClass") is False
        assert is_opaque_class("Function") is False

    def test_unknown_class_returns_false(self):
        """未知类返回 False。"""
        assert is_opaque_class("SomeUnknownClass") is False


class TestStrategyConsistency:
    """策略一致性测试。"""

    def test_no_overlap_between_categories(self):
        """三个类别无重叠。"""
        tagged = {cls for cls, s in CLASS_STRATEGY_TABLE.items()
                  if s == SerializationStrategy.TAGGED_PROPERTIES_ONLY}
        opaque = {cls for cls, s in CLASS_STRATEGY_TABLE.items()
                  if s == SerializationStrategy.OPAQUE_CLASS_PAYLOAD}
        skip = {cls for cls, s in CLASS_STRATEGY_TABLE.items()
                if s == SerializationStrategy.SKIP_UNSUPPORTED}

        # 无交集
        assert len(tagged & opaque) == 0
        assert len(tagged & skip) == 0
        assert len(opaque & skip) == 0

    def test_all_entries_valid_strategy(self):
        """所有映射值均为有效策略。"""
        valid_strategies = set(SerializationStrategy)
        for cls, strategy in CLASS_STRATEGY_TABLE.items():
            assert strategy in valid_strategies, f"{cls} 映射到无效策略 {strategy}"


class TestLinkerIntegration:
    """linker.preload() 集成测试。"""

    def _create_mock_export_instance(self, class_name: str, serial_size: int = 100):
        """创建 mock export instance。"""
        from unittest.mock import MagicMock
        inst = MagicMock()
        inst.object_class = class_name
        inst.object_name = "TestObject"
        inst.serial_size = serial_size
        inst.serial_offset = 0
        inst._preloaded = False
        return inst

    def test_linker_preload_marks_skip_class_as_skipped(self):
        """SKIP_UNSUPPORTED 类在 preload 中被标记为 skipped。"""
        from uasset_read.parsers.class_serialization_strategy import (
            should_skip_class,
            is_opaque_class,
        )
        # NiagaraGraph 是 SKIP_UNSUPPORTED
        assert should_skip_class("NiagaraGraph") is True
        assert is_opaque_class("NiagaraGraph") is False

    def test_linker_preload_marks_opaque_class_as_opaque(self):
        """OPAQUE_CLASS_PAYLOAD 类在 preload 中被标记为 opaque。"""
        from uasset_read.parsers.class_serialization_strategy import (
            should_skip_class,
            is_opaque_class,
        )
        # StaticMesh 是 OPAQUE_CLASS_PAYLOAD
        assert should_skip_class("StaticMesh") is False
        assert is_opaque_class("StaticMesh") is True

    def test_linker_preload_continues_for_tagged_class(self):
        """TAGGED_PROPERTIES_ONLY 类在 preload 中继续正常解析。"""
        from uasset_read.parsers.class_serialization_strategy import (
            get_serialization_strategy,
            SerializationStrategy,
        )
        # BlueprintGeneratedClass 是 TAGGED_PROPERTIES_ONLY
        strategy = get_serialization_strategy("BlueprintGeneratedClass")
        assert strategy == SerializationStrategy.TAGGED_PROPERTIES_ONLY

    def test_linker_preload_defaults_for_unknown_class(self):
        """未知 class 默认使用 TAGGED_PROPERTIES_ONLY 策略。"""
        from uasset_read.parsers.class_serialization_strategy import (
            get_serialization_strategy,
            SerializationStrategy,
        )
        strategy = get_serialization_strategy("SomeUnknownClass")
        assert strategy == SerializationStrategy.TAGGED_PROPERTIES_ONLY


# ---------------------------------------------------------------------------
# Class Handler Registry 测试 — 原 test_class_registry.py
# ---------------------------------------------------------------------------


class MockHandler(ClassHandler):
    """测试用 mock handler"""

    def __init__(self, name: str, can_handle_names: list[str]):
        self._name = name
        self._can_handle = set(can_handle_names)

    def can_handle(self, class_name: str) -> bool:
        return class_name in self._can_handle

    @property
    def handler_name(self) -> str:
        return self._name

    @property
    def fallback_policy(self) -> FallbackPolicy:
        return FallbackPolicy.GENERIC_UOBJECT

    def parse(self, export, archive, context) -> HandlerResult:
        return HandlerResult(
            success=True,
            properties=[],
            data={"handled_by": self._name},
        )


class TestClassHandlerRegistry:
    """ClassHandlerRegistry 注册与查找测试。"""

    def test_registry_register_and_lookup(self):
        """注册和精确查找"""
        reg = ClassHandlerRegistry()
        handler = MockHandler("TestHandler", ["MyClass", "MyOtherClass"])
        reg.register(handler)

        found = reg.find_handler("MyClass")
        assert found is not None
        assert found.handler_name == "TestHandler"

    def test_registry_unknown_class_returns_none(self):
        """未知 class 无 handler"""
        reg = ClassHandlerRegistry()
        reg.register(MockHandler("TestHandler", ["KnownClass"]))

        found = reg.find_handler("UnknownClass")
        assert found is None

    def test_registry_multiple_handlers(self):
        """多个 handler 独立注册"""
        reg = ClassHandlerRegistry()
        h1 = MockHandler("H1", ["ClassA"])
        h2 = MockHandler("H2", ["ClassB", "ClassC"])
        reg.register(h1)
        reg.register(h2)

        assert reg.find_handler("ClassA").handler_name == "H1"
        assert reg.find_handler("ClassB").handler_name == "H2"
        assert reg.find_handler("ClassC").handler_name == "H2"
        assert reg.find_handler("ClassD") is None

    def test_registry_get_registered_handlers(self):
        """获取已注册 handler 列表"""
        reg = ClassHandlerRegistry()
        reg.register(MockHandler("H1", ["A"]))
        reg.register(MockHandler("H2", ["B"]))

        names = [h.handler_name for h in reg.get_registered_handlers()]
        assert "H1" in names
        assert "H2" in names

    def test_registry_clear(self):
        """清空 registry"""
        reg = ClassHandlerRegistry()
        reg.register(MockHandler("H1", ["A"]))
        reg.clear()
        assert len(reg.get_registered_handlers()) == 0
        assert reg.find_handler("A") is None

    def test_registry_cache_hits(self):
        """缓存命中返回同一对象"""
        reg = ClassHandlerRegistry()
        handler = MockHandler("H1", ["CachedClass"])
        reg.register(handler)

        first = reg.find_handler("CachedClass")
        second = reg.find_handler("CachedClass")
        assert first is second

    def test_registry_cache_cleared_on_register(self):
        """新注册后缓存失效，新 class 能被正确查找"""
        reg = ClassHandlerRegistry()
        h1 = MockHandler("H1", ["ClassA"])
        reg.register(h1)
        assert reg.find_handler("ClassA").handler_name == "H1"

        # 注册一个能处理 ClassB 的 handler
        h2 = MockHandler("H2", ["ClassB"])
        reg.register(h2)
        assert reg.find_handler("ClassB").handler_name == "H2"
        # ClassA 仍然指向 H1（先注册优先）
        assert reg.find_handler("ClassA").handler_name == "H1"


class TestHandlerResult:
    """HandlerResult 数据类测试。"""

    def test_handler_result_success(self):
        """HandlerResult 成功结果"""
        result = HandlerResult(
            success=True,
            properties=["prop1", "prop2"],
            data={"key": "value"},
        )
        assert result.success is True
        assert len(result.properties) == 2
        assert result.data["key"] == "value"

    def test_handler_result_failure(self):
        """HandlerResult 失败结果"""
        result = HandlerResult(
            success=False,
            error_message="Not applicable",
            fallback_policy=FallbackPolicy.SKIP,
        )
        assert result.success is False
        assert result.fallback_policy == FallbackPolicy.SKIP


class TestFallbackPolicyEnum:
    """FallbackPolicy 枚举值测试。"""

    def test_fallback_policy_enum(self):
        """FallbackPolicy 枚举值"""
        assert FallbackPolicy.GENERIC_UOBJECT == "generic_uobject"
        assert FallbackPolicy.SKIP == "skip"
        assert FallbackPolicy.RAISE == "raise"
        assert FallbackPolicy.PROPERTY_FALLBACK == "property_fallback"


class TestClassRegistrySingleton:
    """全局单例 registry 测试。"""

    def test_get_class_registry_singleton(self):
        """全局单例 registry"""
        from uasset_read.parsers.class_registry import get_class_registry, reset_class_registry

        reset_class_registry()
        r1 = get_class_registry()
        r2 = get_class_registry()
        assert r1 is r2

    def test_reset_class_registry(self):
        """重置单例"""
        from uasset_read.parsers.class_registry import get_class_registry, reset_class_registry

        r1 = get_class_registry()
        reset_class_registry()
        r2 = get_class_registry()
        assert r1 is not r2


class TestSkipPolicyIntegration:
    """handler SKIP fallback policy 集成测试。"""

    def test_skip_policy_handler_integration(self):
        """handler 的 SKIP fallback policy 与 should_skip_export_for_tolerant_parsing 集成"""
        from unittest.mock import MagicMock
        from uasset_read.parsers.class_registry import (
            get_class_registry,
            reset_class_registry,
        )
        from uasset_read.parsers.class_specific_skip import should_skip_export_for_tolerant_parsing

        reset_class_registry()
        reg = get_class_registry()

        # 注册一个 SKIP policy 的 handler
        class SkipHandler(ClassHandler):
            def can_handle(self, class_name: str) -> bool:
                return class_name == "SkipMeClass"

            @property
            def handler_name(self) -> str:
                return "SkipHandler"

            @property
            def fallback_policy(self) -> FallbackPolicy:
                return FallbackPolicy.SKIP

            def parse(self, export, archive, context) -> HandlerResult:
                return HandlerResult(success=True)

        reg.register(SkipHandler())

        export = MagicMock()
        export.object_name = "SomeObject"

        # 通过 registry SKIP policy 触发跳过
        assert should_skip_export_for_tolerant_parsing(export, "SkipMeClass") is True

        # 不在 skip list 中的 class 不跳过
        assert should_skip_export_for_tolerant_parsing(export, "SomeRandomClass") is False

        reset_class_registry()
