"""N2CNodeDefinition 单元测试。"""
from uasset_read.n2c.definitions import N2CNodeDefinition
from uasset_read.n2c.node_types import N2CNodeType


def test_definition_creation():
    """所有字段可设置。"""
    definition = N2CNodeDefinition(
        node_id="TestNode_001",
        node_type=N2CNodeType.CallFunction,
        position=(100, 200),
        comment="Test comment",
        input_pins=[{"name": "InputA", "type": "exec"}],
        output_pins=[{"name": "OutputA", "type": "exec"}],
        extra_data={"function_name": "TestFunc"},
    )
    assert definition.node_id == "TestNode_001"
    assert definition.node_type == N2CNodeType.CallFunction
    assert definition.position == (100, 200)
    assert definition.comment == "Test comment"
    assert len(definition.input_pins) == 1
    assert len(definition.output_pins) == 1
    assert definition.extra_data == {"function_name": "TestFunc"}


def test_definition_defaults():
    """extra_data 默认为空 dict。"""
    definition = N2CNodeDefinition(
        node_id="TestNode",
        node_type=N2CNodeType.Event,
        position=(0, 0),
    )
    assert definition.comment == ""
    assert definition.input_pins == []
    assert definition.output_pins == []
    assert definition.extra_data == {}


def test_definition_to_dict_basic():
    """to_dict() 包含必需键。"""
    definition = N2CNodeDefinition(
        node_id="TestNode",
        node_type=N2CNodeType.Branch,
        position=(42, 99),
        comment="Branch node",
        input_pins=[{"name": "Execute"}],
        output_pins=[{"name": "True"}, {"name": "False"}],
    )
    result = definition.to_dict()
    assert result["node_name"] == "TestNode"
    assert result["node_type"] == "Branch"
    assert result["position"] == {"x": 42, "y": 99}
    assert result["node_comment"] == "Branch node"
    assert len(result["pins"]) == 3


def test_definition_to_dict_extra_data():
    """extra_data 合并到输出中。"""
    definition = N2CNodeDefinition(
        node_id="CallFunc",
        node_type=N2CNodeType.CallFunction,
        position=(0, 0),
        extra_data={"function_name": "MyFunc", "is_pure": True},
    )
    result = definition.to_dict()
    assert result["function_name"] == "MyFunc"
    assert result["is_pure"] is True
    assert "node_name" in result
    assert "node_type" in result
