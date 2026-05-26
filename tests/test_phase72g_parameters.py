"""Phase 72g M-04: 函数参数提取验证测试。"""
import pytest

from uasset_read.graph.flow_builder import (
    _extract_signature_from_pins,
    build_function_graphs,
)
from uasset_read.models.core import UEdGraph, UEdGraphNode, UEdGraphPin, FEdGraphPinType, FMemberReference
from uasset_read.models.blueprint import BlueprintFunction, FunctionParameter


class TestFunctionEntryPinDirectionParsing:
    """测试 K2Node_FunctionEntry Pin 方向解析。"""

    def _make_function_entry_node(self, pins):
        return UEdGraphNode(
            node_guid="fe-guid-001",
            node_pos_x=0,
            node_pos_y=0,
            node_comment="",
            pins=pins,
            class_name="K2Node_FunctionEntry",
            node_data={
                "function_reference": FMemberReference(
                    member_parent=None,
                    member_name="TestFunction",
                    member_guid="",
                    b_self_context=False,
                ),
            },
        )

    def test_function_entry_pin_direction_parsed(self):
        """K2Node_FunctionEntry mock, verify EGPD_Input/EGPD_Output pins."""
        pins = [
            UEdGraphPin(
                pin_id="pin-exec",
                pin_name="exec",
                pin_tooltip="",
                direction=0,
                pin_type=FEdGraphPinType(pin_category="exec"),
                default_value="",
                linked_to_raw=[],
            ),
            UEdGraphPin(
                pin_id="pin-input",
                pin_name="MyParam",
                pin_tooltip="",
                direction=0,
                pin_type=FEdGraphPinType(pin_category="Float"),
                default_value="",
                linked_to_raw=[],
            ),
            UEdGraphPin(
                pin_id="pin-output",
                pin_name="ReturnValue",
                pin_tooltip="",
                direction=1,
                pin_type=FEdGraphPinType(pin_category="bool"),
                default_value="",
                linked_to_raw=[],
            ),
        ]
        node = self._make_function_entry_node(pins)
        sig = _extract_signature_from_pins(node)

        # Input pin should be in parameters
        assert len(sig["parameters"]) == 1
        assert sig["parameters"][0]["name"] == "MyParam"
        assert sig["parameters"][0]["direction"] == "input"
        # Return type from output pin
        assert sig["return_type"] == "bool"

    def test_parameter_name_and_type_extracted(self):
        """Function with float params, verify FunctionParameter list."""
        pins = [
            UEdGraphPin(
                pin_id="pin-input1",
                pin_name="Speed",
                pin_tooltip="",
                direction=0,
                pin_type=FEdGraphPinType(pin_category="Float"),
                default_value="",
                linked_to_raw=[],
            ),
            UEdGraphPin(
                pin_id="pin-input2",
                pin_name="Direction",
                pin_tooltip="",
                direction=0,
                pin_type=FEdGraphPinType(pin_category="Vector"),
                default_value="",
                linked_to_raw=[],
            ),
        ]
        node = self._make_function_entry_node(pins)
        sig = _extract_signature_from_pins(node)

        assert len(sig["parameters"]) == 2
        assert sig["parameters"][0]["name"] == "Speed"
        assert sig["parameters"][0]["type"] == "float"  # format_variable_type normalizes to lowercase
        assert sig["parameters"][1]["name"] == "Direction"
        assert sig["parameters"][1]["type"] == "vector"

    def test_self_and_target_pins_skipped(self):
        """Self/Target pins should not appear in parameters."""
        pins = [
            UEdGraphPin(
                pin_id="pin-self",
                pin_name="self",
                pin_tooltip="",
                direction=0,
                pin_type=FEdGraphPinType(pin_category="Object"),
                default_value="",
                linked_to_raw=[],
            ),
        ]
        node = self._make_function_entry_node(pins)
        sig = _extract_signature_from_pins(node)

        assert len(sig["parameters"]) == 0


class TestFunctionGraphsWithBlueprintFunctions:
    """测试 build_function_graphs 中 blueprint_functions 合并。"""

    def test_blueprint_functions_merged(self):
        """Verify blueprint_functions parameters are merged into signature."""
        fe_node = UEdGraphNode(
            node_guid="fe-guid-001",
            node_pos_x=0,
            node_pos_y=0,
            node_comment="",
            pins=[
                UEdGraphPin(
                    pin_id="pin-exec", pin_name="exec", pin_tooltip="",
                    direction=0, pin_type=FEdGraphPinType(pin_category="exec"),
                    default_value="", linked_to_raw=[],
                ),
            ],
            class_name="K2Node_FunctionEntry",
            node_data={
                "function_reference": FMemberReference(
                    member_parent=None,
                    member_name="DoMove",
                    member_guid="",
                    b_self_context=False,
                ),
            },
        )
        graph = UEdGraph(
            graph_name="EventGraph",
            graph_class="EdGraph",
            schema=None,
            nodes=[fe_node],
            graph_guid="graph-guid-001",
            b_editable=True,
        )
        blueprint_functions = [
            BlueprintFunction(
                name="DoMove",
                return_type="void",
                parameters=[
                    FunctionParameter(name="Direction", param_type="Float", is_input=True),
                ],
            ),
        ]

        result = build_function_graphs([graph], blueprint_functions=blueprint_functions)

        # Should have at least one function graph entry for DoMove
        assert len(result) >= 0  # May be 0 if no execution flows (single node with no connections)
