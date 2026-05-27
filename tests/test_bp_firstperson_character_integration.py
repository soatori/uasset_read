from __future__ import annotations

from typing import Dict, Tuple

from uasset_read.formatters import format_blueprint_ue_text


def _pin_lookup(graph) -> Dict[str, Tuple[object, object]]:
    lookup: Dict[str, Tuple[object, object]] = {}
    for node in graph.nodes:
        for pin in node.pins:
            lookup[pin.pin_id] = (node, pin)
    return lookup


def _graph_by_name(result, name: str):
    for graph in result.graphs:
        if graph.graph_name == name:
            return graph
    raise AssertionError(f"graph not found: {name}")


def _find_enhanced_node(graph, short_name: str):
    for node in graph.nodes:
        data = node.node_data or {}
        if node.class_name == "K2Node_EnhancedInputAction" and data.get("input_action_short_name") == short_name:
            return node
    raise AssertionError(f"enhanced input node not found: {short_name}")


def _pin(node, pin_name: str):
    for pin in node.pins:
        if pin.pin_name == pin_name:
            return pin
    raise AssertionError(f"pin not found: {getattr(node, '_export_object_name', node.class_name)}.{pin_name}")


def _linked_member_name(graph, pin) -> str:
    lookup = _pin_lookup(graph)
    assert pin.linked_to_raw
    target_node, _ = lookup[pin.linked_to_raw[0]["pin_guid"]]
    ref = (target_node.node_data or {}).get("function_reference")
    return getattr(ref, "member_name", "")


def test_bp_firstperson_graphs_and_pin_links(sample_result) -> None:
    assert sample_result.is_success
    assert {graph.graph_name for graph in sample_result.graphs} == {
        "Aim",
        "EventGraph",
        "Move",
        "UserConstructionScript",
    }

    event_graph = _graph_by_name(sample_result, "EventGraph")
    for action_name in ("IA_Look", "IA_Move", "IA_MouseLook"):
        node = _find_enhanced_node(event_graph, action_name)
        parent_pin = _pin(node, "ActionValue")
        x_pin = _pin(node, "ActionValue_X")
        y_pin = _pin(node, "ActionValue_Y")
        input_action_pin = _pin(node, "InputAction")

        assert len(parent_pin.sub_pins) == 2
        assert len(x_pin.linked_to_raw) == 1
        assert len(y_pin.linked_to_raw) == 1
        assert x_pin.parent_pin is not None
        assert y_pin.parent_pin is not None
        assert x_pin.pin_friendly_name == "Action Value X"
        assert y_pin.pin_friendly_name == "Action Value Y"
        assert input_action_pin.default_value == action_name
        assert input_action_pin.default_object_ref is not None
        assert input_action_pin.default_object_ref.get_full_name().endswith(f"{action_name}.{action_name}")


def test_bp_firstperson_semantics_match_cpp(sample_result) -> None:
    event_graph = _graph_by_name(sample_result, "EventGraph")
    move_graph = _graph_by_name(sample_result, "Move")
    aim_graph = _graph_by_name(sample_result, "Aim")

    jump_node = _find_enhanced_node(event_graph, "IA_Jump")
    assert _linked_member_name(event_graph, _pin(jump_node, "Started")) == "Jump"
    assert _linked_member_name(event_graph, _pin(jump_node, "Completed")) == "StopJumping"

    move_event = _find_enhanced_node(event_graph, "IA_Move")
    look_event = _find_enhanced_node(event_graph, "IA_Look")
    mouse_look_event = _find_enhanced_node(event_graph, "IA_MouseLook")
    assert _linked_member_name(event_graph, _pin(move_event, "Triggered")) == "Move"
    assert _linked_member_name(event_graph, _pin(look_event, "Triggered")) == "Aim"
    assert _linked_member_name(event_graph, _pin(mouse_look_event, "Triggered")) == "Aim"

    move_calls = {
        (node.node_data or {}).get("function_reference").member_name
        for node in move_graph.nodes
        if node.class_name == "K2Node_CallFunction" and (node.node_data or {}).get("function_reference")
    }
    assert {"AddMovementInput", "GetActorRightVector", "GetActorForwardVector"} <= move_calls

    aim_calls = {
        (node.node_data or {}).get("function_reference").member_name
        for node in aim_graph.nodes
        if node.class_name == "K2Node_CallFunction" and (node.node_data or {}).get("function_reference")
    }
    assert {"AddControllerYawInput", "AddControllerPitchInput"} <= aim_calls


def test_bp_firstperson_ue_text_output(sample_result) -> None:
    text = format_blueprint_ue_text(sample_result)
    event_graph = _graph_by_name(sample_result, "EventGraph")
    look_node = _find_enhanced_node(event_graph, "IA_Look")
    x_pin = _pin(look_node, "ActionValue_X")
    call_move_node = next(
        node for node in _graph_by_name(sample_result, "Move").nodes if node.class_name == "K2Node_Knot"
    )
    jump_node = _find_enhanced_node(event_graph, "IA_Jump")

    assert f'Begin Object Class=/Script/InputBlueprintNodes.K2Node_EnhancedInputAction Name="{look_node._export_object_name}"' in text
    assert f'SubPins=({look_node._export_object_name} {x_pin.pin_id.upper()}' in text
    assert f'ParentPin={look_node._export_object_name} {_pin(look_node, "ActionValue").pin_id.upper()}' in text
    assert 'DefaultObject="/Game/Input/Actions/IA_Look.IA_Look"' in text
    assert 'FunctionReference=(MemberName="Jump",bSelfContext=True)' in text
    assert f'Begin Object Class=/Script/BlueprintGraph.K2Node_Knot Name="{call_move_node._export_object_name}"' in text
    assert jump_node._export_object_name in text
