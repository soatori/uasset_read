"""EventProcessor 测试。"""
import pytest

from uasset_read.n2c.definitions import N2CNodeDefinition
from uasset_read.n2c.node_types import N2CNodeType
from uasset_read.n2c.processors import register_all_processors
from uasset_read.n2c.processors.event import EventProcessor


class TestEventProcessor:
    def test_extracts_event_reference(self, mock_node, reset_registry):
        """从 node_data 提取事件引用。"""
        register_all_processors()
        mock_node.node_data = {
            "event_reference": {
                "member_name": "BeginPlay",
                "member_parent": "/Game/MyActor",
            }
        }
        processor = EventProcessor()
        definition = N2CNodeDefinition(
            node_id="test", node_type=N2CNodeType.Event, position=(0, 0)
        )
        processor.process(mock_node, definition)
        assert definition.extra_data["event_name"] == "BeginPlay"
        assert definition.extra_data["event_parent"] == "/Game/MyActor"

    def test_handles_none_node_data(self, mock_node, reset_registry):
        """node_data=None 不崩溃。"""
        register_all_processors()
        mock_node.node_data = None
        processor = EventProcessor()
        definition = N2CNodeDefinition(
            node_id="test", node_type=N2CNodeType.Event, position=(0, 0)
        )
        processor.process(mock_node, definition)
        assert "event_name" not in definition.extra_data

    def test_handles_custom_event_type(self, mock_node, reset_registry):
        """CustomEvent 类型也能正确提取。"""
        register_all_processors()
        mock_node.node_data = {
            "event_reference": {
                "member_name": "MyCustomEvent",
                "member_parent": "/Game/MyBP",
            }
        }
        processor = EventProcessor()
        definition = N2CNodeDefinition(
            node_id="test", node_type=N2CNodeType.CustomEvent, position=(0, 0)
        )
        processor.process(mock_node, definition)
        assert definition.extra_data["event_name"] == "MyCustomEvent"
        assert definition.extra_data["event_parent"] == "/Game/MyBP"
