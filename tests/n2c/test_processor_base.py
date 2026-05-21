"""N2CNodeProcessor 基类单元测试。"""
import pytest

from uasset_read.n2c.node_types import N2CNodeType
from uasset_read.n2c.processor_base import N2CNodeProcessor
from uasset_read.n2c.definitions import N2CNodeDefinition


def test_cannot_instantiate_abstract():
    """抽象基类不可直接实例化。"""
    with pytest.raises(TypeError):
        N2CNodeProcessor()


def test_concrete_implementation_works():
    """具体子类可正常实例化和使用。"""

    class ConcreteProcessor(N2CNodeProcessor):
        @property
        def node_types(self):
            return [N2CNodeType.Event]

        def process(self, node, definition):
            definition.extra_data["handled"] = True

    proc = ConcreteProcessor()
    assert proc.can_process(N2CNodeType.Event) is True
    assert proc.can_process(N2CNodeType.CallFunction) is False

    definition = N2CNodeDefinition(
        node_id="TestNode",
        node_type=N2CNodeType.Event,
        position=(0, 0),
    )
    proc.process(None, definition)
    assert definition.extra_data.get("handled") is True
