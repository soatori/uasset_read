"""N2C 测试 fixtures。"""
import pytest

from uasset_read.models.core import UEdGraphPin, UEdGraphNode, FEdGraphPinType
from uasset_read.n2c.processor_registry import N2CProcessorRegistry


@pytest.fixture
def mock_pin():
    """创建 UEdGraphPin 测试实例。"""
    return UEdGraphPin(
        pin_id="test-pin-001",
        pin_name="TestPin",
        direction=0,
        pin_type=FEdGraphPinType(pin_category="exec"),
        default_value=None,
    )


@pytest.fixture
def mock_node(mock_pin):
    """创建 UEdGraphNode 测试实例。"""
    node = UEdGraphNode(
        node_guid="test-guid-001",
        node_pos_x=100,
        node_pos_y=200,
        node_comment="Test Node",
    )
    node.pins.append(mock_pin)
    return node


@pytest.fixture(autouse=True)
def reset_registry():
    """每个测试前后重置注册表单例，确保测试隔离。"""
    N2CProcessorRegistry.reset()
    yield
    N2CProcessorRegistry.reset()
