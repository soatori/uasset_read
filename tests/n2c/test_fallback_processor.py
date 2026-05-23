"""FallbackProcessor 测试。"""
import pytest

from uasset_read.n2c.definitions import N2CNodeDefinition
from uasset_read.n2c.node_types import N2CNodeType
from uasset_read.n2c.processors import register_all_processors
from uasset_read.n2c.processors.fallback import FallbackProcessor


class TestFallbackProcessor:
    def test_sets_fallback_flag(self, mock_node, reset_registry):
        """fallback=True 在 extra_data 中。"""
        register_all_processors()
        mock_node.class_name = "K2Node_UnknownWeirdNode"
        processor = FallbackProcessor()
        definition = N2CNodeDefinition(
            node_id="test", node_type=N2CNodeType.Unknown, position=(0, 0)
        )
        processor.process(mock_node, definition)
        assert definition.extra_data["fallback"] is True

    def test_records_original_class_name(self, mock_node, reset_registry):
        """original_class_name = node.class_name。"""
        register_all_processors()
        mock_node.class_name = "K2Node_SomeCustomNode"
        processor = FallbackProcessor()
        definition = N2CNodeDefinition(
            node_id="test", node_type=N2CNodeType.Unknown, position=(0, 0)
        )
        processor.process(mock_node, definition)
        assert definition.extra_data["original_class_name"] == "K2Node_SomeCustomNode"
