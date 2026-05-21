"""FlowControlProcessor 测试。"""
import pytest

from uasset_read.n2c.definitions import N2CNodeDefinition
from uasset_read.n2c.node_types import N2CNodeType
from uasset_read.n2c.processors import register_all_processors
from uasset_read.n2c.processors.flow_control import FlowControlProcessor


class TestFlowControlProcessor:
    def test_sets_branch_type_if_then_else(self, mock_node, reset_registry):
        """K2Node_IfThenElse → branch_type 来自 BRANCH_TYPE_MAP。"""
        register_all_processors()
        mock_node.class_name = "K2Node_IfThenElse"
        processor = FlowControlProcessor()
        definition = N2CNodeDefinition(
            node_id="test", node_type=N2CNodeType.Branch, position=(0, 0)
        )
        processor.process(mock_node, definition)
        assert definition.extra_data["branch_type"] == "if_then_else"

    def test_sets_branch_type_switch(self, mock_node, reset_registry):
        """K2Node_SwitchInteger → branch_type 来自 BRANCH_TYPE_MAP。"""
        register_all_processors()
        mock_node.class_name = "K2Node_SwitchInteger"
        processor = FlowControlProcessor()
        definition = N2CNodeDefinition(
            node_id="test", node_type=N2CNodeType.SwitchInt, position=(0, 0)
        )
        processor.process(mock_node, definition)
        assert definition.extra_data["branch_type"] == "switch_integer"

    def test_sets_stops_execution(self, mock_node, reset_registry):
        """stops_execution 始终为 True。"""
        register_all_processors()
        mock_node.class_name = "K2Node_IfThenElse"
        processor = FlowControlProcessor()
        definition = N2CNodeDefinition(
            node_id="test", node_type=N2CNodeType.Branch, position=(0, 0)
        )
        processor.process(mock_node, definition)
        assert definition.extra_data["stops_execution"] is True

    def test_unknown_class_name_defaults(self, mock_node, reset_registry):
        """未知 class_name → branch_type 为 'unknown'。"""
        register_all_processors()
        mock_node.class_name = "K2Node_UnknownSomething"
        processor = FlowControlProcessor()
        definition = N2CNodeDefinition(
            node_id="test", node_type=N2CNodeType.Branch, position=(0, 0)
        )
        processor.process(mock_node, definition)
        assert definition.extra_data["branch_type"] == "unknown"
        assert definition.extra_data["stops_execution"] is True
