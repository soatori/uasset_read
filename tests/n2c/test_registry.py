"""N2CProcessorRegistry 单元测试。"""
import pytest

from uasset_read.n2c.node_types import N2CNodeType
from uasset_read.n2c.processor_base import N2CNodeProcessor
from uasset_read.n2c.definitions import N2CNodeDefinition
from uasset_read.n2c.processor_registry import N2CProcessorRegistry


class _TestProcessor(N2CNodeProcessor):
    """用于测试的具体处理器。"""

    def __init__(self, types):
        self._types = types

    @property
    def node_types(self):
        return self._types

    def process(self, node, definition):
        definition.extra_data["processed_by"] = type(self).__name__


class _AnotherProcessor(N2CNodeProcessor):
    """另一个测试用处理器。"""

    @property
    def node_types(self):
        return [N2CNodeType.VariableGet]

    def process(self, node, definition):
        definition.extra_data["processed_by"] = "AnotherProcessor"


class _FailingProcessor(N2CNodeProcessor):
    """总是失败的处理器。"""

    @property
    def node_types(self):
        return [N2CNodeType.MathExpression]

    def process(self, node, definition):
        raise RuntimeError("Intentional failure")


class _FallbackProcessor(N2CNodeProcessor):
    """Fallback 处理器。"""

    @property
    def node_types(self):
        return []

    def process(self, node, definition):
        definition.extra_data["fallback"] = True


def test_singleton_creation():
    """get_instance() 返回同一实例。"""
    r1 = N2CProcessorRegistry.get_instance()
    r2 = N2CProcessorRegistry.get_instance()
    assert r1 is r2


def test_reset_clears_singleton():
    """reset() 后 get_instance() 返回新实例。"""
    r1 = N2CProcessorRegistry.get_instance()
    N2CProcessorRegistry.reset()
    r2 = N2CProcessorRegistry.get_instance()
    assert r1 is not r2


def test_register_and_get_processor():
    """注册后可以获取。"""
    registry = N2CProcessorRegistry.get_instance()
    proc = _TestProcessor([N2CNodeType.CallFunction])
    registry.register(proc)
    assert registry.get_processor(N2CNodeType.CallFunction) is proc


def test_duplicate_registration_raises():
    """重复注册抛出 ValueError。"""
    registry = N2CProcessorRegistry.get_instance()
    proc1 = _TestProcessor([N2CNodeType.CallFunction])
    proc2 = _TestProcessor([N2CNodeType.CallFunction])
    registry.register(proc1)
    with pytest.raises(ValueError, match="already registered"):
        registry.register(proc2)


def test_get_processor_unknown_type():
    """未知类型返回 None（无 fallback 时）。"""
    registry = N2CProcessorRegistry.get_instance()
    assert registry.get_processor(N2CNodeType.Unknown) is None


def test_fallback_processor_used():
    """未知类型使用 fallback。"""
    registry = N2CProcessorRegistry.get_instance()
    fallback = _FallbackProcessor()
    registry.set_fallback(fallback)
    assert registry.get_processor(N2CNodeType.Unknown) is fallback


def test_process_node_success():
    """process_node 成功调用处理器。"""
    registry = N2CProcessorRegistry.get_instance()
    proc = _TestProcessor([N2CNodeType.CallFunction])
    registry.register(proc)

    definition = N2CNodeDefinition(
        node_id="TestNode",
        node_type=N2CNodeType.CallFunction,
        position=(0, 0),
    )
    result = registry.process_node(None, N2CNodeType.CallFunction, definition)
    assert result is True
    assert definition.extra_data.get("processed_by") == "_TestProcessor"


def test_process_node_no_processor():
    """没有处理器时返回 False。"""
    registry = N2CProcessorRegistry.get_instance()
    definition = N2CNodeDefinition(
        node_id="TestNode",
        node_type=N2CNodeType.CallFunction,
        position=(0, 0),
    )
    result = registry.process_node(None, N2CNodeType.CallFunction, definition)
    assert result is False
