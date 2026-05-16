"""Phase 49: K2Node_CallFunction 参数提取单元测试。"""
import pytest

from uasset_read.models.core import UEdGraphPin, UEdGraphNode, FEdGraphPinType
from uasset_read.formatters.json_formatter import _extract_call_function_parameters


def _make_pin(pin_name, pin_category, pin_subcategory="", direction=0, default_value=None, is_reference=False):
    return UEdGraphPin(
        pin_id=f"pin_{pin_name}",
        pin_name=pin_name,
        direction=direction,
        pin_type=FEdGraphPinType(
            pin_category=pin_category,
            pin_subcategory=pin_subcategory,
            is_reference=is_reference,
        ),
        default_value=default_value,
    )


def _make_node(pins):
    return UEdGraphNode(
        node_guid="test-guid",
        class_name="K2Node_CallFunction",
        pins=pins,
    )


class TestExtractCallFunctionParameters:
    def test_function_with_input_and_output_params(self):
        node = _make_node([
            _make_pin("execute", "exec", direction=0),
            _make_pin("then", "exec", direction=1),
            _make_pin("Target", "Object", "FirstPersonCharacterCharacter", direction=0),
            _make_pin("Speed", "Float", direction=0, default_value="1.0"),
            _make_pin("ReturnValue", "Struct", "Vector", direction=1),
        ])
        result = _extract_call_function_parameters(node)

        assert len(result["input_params"]) == 2
        assert result["input_params"][0]["name"] == "Target"
        assert result["input_params"][0]["pin_category"] == "Object"
        assert result["input_params"][0]["pin_subcategory"] == "FirstPersonCharacterCharacter"
        assert result["input_params"][1]["name"] == "Speed"
        assert result["input_params"][1]["default_value"] == "1.0"

        assert len(result["output_params"]) == 1
        assert result["output_params"][0]["name"] == "ReturnValue"
        assert result["output_params"][0]["pin_category"] == "Struct"

    def test_pure_function_no_exec_pins(self):
        node = _make_node([
            _make_pin("A", "Float", direction=0, default_value="0.0"),
            _make_pin("B", "Float", direction=0, default_value="0.0"),
            _make_pin("ReturnValue", "Float", direction=1),
        ])
        result = _extract_call_function_parameters(node)

        assert len(result["input_params"]) == 2
        assert len(result["output_params"]) == 1
        assert result["output_params"][0]["name"] == "ReturnValue"

    def test_no_parameter_function(self):
        node = _make_node([
            _make_pin("execute", "exec", direction=0),
            _make_pin("then", "exec", direction=1),
        ])
        result = _extract_call_function_parameters(node)

        assert result["input_params"] == []
        assert result["output_params"] == []

    def test_parameter_with_default_value(self):
        node = _make_node([
            _make_pin("Name", "Name", direction=0, default_value="DefaultName"),
            _make_pin("EmptyDefault", "String", direction=0, default_value=""),
            _make_pin("NoneDefault", "String", direction=0, default_value=None),
        ])
        result = _extract_call_function_parameters(node)

        assert "default_value" in result["input_params"][0]
        assert result["input_params"][0]["default_value"] == "DefaultName"
        assert "default_value" not in result["input_params"][1]
        assert "default_value" not in result["input_params"][2]

    def test_exec_pins_filtered(self):
        node = _make_node([
            _make_pin("execute", "exec", direction=0),
            _make_pin("Param", "Int", direction=0),
            _make_pin("then", "exec", direction=1),
        ])
        result = _extract_call_function_parameters(node)

        assert all(p["pin_category"] != "exec" for p in result["input_params"])
        assert all(p["pin_category"] != "exec" for p in result["output_params"])

    def test_reference_parameter(self):
        node = _make_node([
            _make_pin("OutValue", "Float", direction=1, is_reference=True),
        ])
        result = _extract_call_function_parameters(node)

        assert result["output_params"][0].get("is_reference") is True

    def test_empty_pins(self):
        node = _make_node([])
        result = _extract_call_function_parameters(node)

        assert result == {"input_params": [], "output_params": []}
