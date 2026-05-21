"""CallFunctionProcessor 测试。"""
import pytest

from uasset_read.models.core import FEdGraphPinType, UEdGraphPin
from uasset_read.n2c.definitions import N2CNodeDefinition
from uasset_read.n2c.node_types import N2CNodeType
from uasset_read.n2c.processors import register_all_processors
from uasset_read.n2c.processors.call_function import CallFunctionProcessor


class TestCallFunctionProcessorDictData:
    def test_extracts_function_reference(self, mock_node, reset_registry):
        """从 dict 格式的 node_data 提取函数引用。"""
        register_all_processors()
        mock_node.node_data = {
            "function_reference": {
                "member_name": "SomeFunction",
                "member_parent": "/Game/MyClass",
                "b_self_context": True,
            }
        }
        processor = CallFunctionProcessor()
        definition = N2CNodeDefinition(
            node_id="test", node_type=N2CNodeType.CallFunction, position=(0, 0)
        )
        processor.process(mock_node, definition)
        assert definition.extra_data["member_name"] == "SomeFunction"
        assert definition.extra_data["member_parent"] == "/Game/MyClass"
        assert definition.extra_data["b_self_context"] is True

    def test_detects_pure_function(self, reset_registry):
        """无 exec 引脚 → pure=True。"""
        register_all_processors()
        non_exec_pin = UEdGraphPin(
            pin_id="pin-1",
            pin_name="Value",
            direction=0,
            pin_type=FEdGraphPinType(pin_category="float"),
            default_value=None,
        )
        from uasset_read.models.core import UEdGraphNode

        node = UEdGraphNode(
            node_guid="guid-1",
            node_pos_x=0,
            node_pos_y=0,
            pins=[non_exec_pin],
        )
        node.node_data = {
            "function_reference": {
                "member_name": "PureFunc",
                "member_parent": None,
                "b_self_context": False,
            }
        }
        processor = CallFunctionProcessor()
        definition = N2CNodeDefinition(
            node_id="test", node_type=N2CNodeType.CallFunction, position=(0, 0)
        )
        processor.process(node, definition)
        assert definition.extra_data["pure"] is True

    def test_detects_non_pure(self, mock_node, reset_registry):
        """有 exec 引脚 → pure 不设置。"""
        register_all_processors()
        processor = CallFunctionProcessor()
        definition = N2CNodeDefinition(
            node_id="test", node_type=N2CNodeType.CallFunction, position=(0, 0)
        )
        processor.process(mock_node, definition)
        assert "pure" not in definition.extra_data

    def test_handles_none_node_data(self, mock_node, reset_registry):
        """node_data=None 不崩溃。"""
        register_all_processors()
        mock_node.node_data = None
        processor = CallFunctionProcessor()
        definition = N2CNodeDefinition(
            node_id="test", node_type=N2CNodeType.CallFunction, position=(0, 0)
        )
        processor.process(mock_node, definition)
        # Should not crash; exec pin exists so pure not set
        assert "pure" not in definition.extra_data

    def test_handles_missing_function_reference(self, mock_node, reset_registry):
        """node_data 存在但无 function_reference 键。"""
        register_all_processors()
        mock_node.node_data = {"some_other_key": "value"}
        processor = CallFunctionProcessor()
        definition = N2CNodeDefinition(
            node_id="test", node_type=N2CNodeType.CallFunction, position=(0, 0)
        )
        processor.process(mock_node, definition)
        assert "member_name" not in definition.extra_data


class TestCallFunctionProcessorDataclass:
    def test_extracts_function_reference_dataclass(self, reset_registry):
        """从 dataclass/object 格式的 node_data 提取函数引用。"""
        register_all_processors()

        # Create a simple mock object with function_reference attribute
        class MockMemberRef:
            member_name = "DataclassFunc"
            member_parent = "/Game/MyClass2"
            b_self_context = False

        class MockNodeData:
            function_reference = MockMemberRef()

        from uasset_read.models.core import UEdGraphNode

        node = UEdGraphNode(
            node_guid="guid-dc",
            node_pos_x=0,
            node_pos_y=0,
            node_data=MockNodeData(),
        )
        processor = CallFunctionProcessor()
        definition = N2CNodeDefinition(
            node_id="test-dc", node_type=N2CNodeType.CallFunction, position=(0, 0)
        )
        processor.process(node, definition)
        assert definition.extra_data["member_name"] == "DataclassFunc"
        assert definition.extra_data["member_parent"] == "/Game/MyClass2"
        assert definition.extra_data["b_self_context"] is False
