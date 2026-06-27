"""tests/test_class_registry.py — Class Handler Registry 测试"""
from uasset_read.parsers.class_registry import (
    ClassHandlerRegistry,
    ClassHandler,
    HandlerResult,
    FallbackPolicy,
)


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


def test_registry_register_and_lookup():
    """注册和精确查找"""
    reg = ClassHandlerRegistry()
    handler = MockHandler("TestHandler", ["MyClass", "MyOtherClass"])
    reg.register(handler)

    found = reg.find_handler("MyClass")
    assert found is not None
    assert found.handler_name == "TestHandler"


def test_registry_unknown_class_returns_none():
    """未知 class 无 handler"""
    reg = ClassHandlerRegistry()
    reg.register(MockHandler("TestHandler", ["KnownClass"]))

    found = reg.find_handler("UnknownClass")
    assert found is None


def test_registry_multiple_handlers():
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


def test_handler_result_success():
    """HandlerResult 成功结果"""
    result = HandlerResult(
        success=True,
        properties=["prop1", "prop2"],
        data={"key": "value"},
    )
    assert result.success is True
    assert len(result.properties) == 2
    assert result.data["key"] == "value"


def test_handler_result_failure():
    """HandlerResult 失败结果"""
    result = HandlerResult(
        success=False,
        error_message="Not applicable",
        fallback_policy=FallbackPolicy.SKIP,
    )
    assert result.success is False
    assert result.fallback_policy == FallbackPolicy.SKIP


def test_fallback_policy_enum():
    """FallbackPolicy 枚举值"""
    assert FallbackPolicy.GENERIC_UOBJECT == "generic_uobject"
    assert FallbackPolicy.SKIP == "skip"
    assert FallbackPolicy.RAISE == "raise"
    assert FallbackPolicy.PROPERTY_FALLBACK == "property_fallback"


def test_registry_get_registered_handlers():
    """获取已注册 handler 列表"""
    reg = ClassHandlerRegistry()
    reg.register(MockHandler("H1", ["A"]))
    reg.register(MockHandler("H2", ["B"]))

    names = [h.handler_name for h in reg.get_registered_handlers()]
    assert "H1" in names
    assert "H2" in names


def test_registry_clear():
    """清空 registry"""
    reg = ClassHandlerRegistry()
    reg.register(MockHandler("H1", ["A"]))
    reg.clear()
    assert len(reg.get_registered_handlers()) == 0
    assert reg.find_handler("A") is None


def test_registry_cache_hits():
    """缓存命中返回同一对象"""
    reg = ClassHandlerRegistry()
    handler = MockHandler("H1", ["CachedClass"])
    reg.register(handler)

    first = reg.find_handler("CachedClass")
    second = reg.find_handler("CachedClass")
    assert first is second


def test_registry_cache_cleared_on_register():
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


def test_get_class_registry_singleton():
    """全局单例 registry"""
    from uasset_read.parsers.class_registry import get_class_registry, reset_class_registry

    reset_class_registry()
    r1 = get_class_registry()
    r2 = get_class_registry()
    assert r1 is r2


def test_reset_class_registry():
    """重置单例"""
    from uasset_read.parsers.class_registry import get_class_registry, reset_class_registry

    r1 = get_class_registry()
    reset_class_registry()
    r2 = get_class_registry()
    assert r1 is not r2


def test_skip_policy_handler_integration():
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
