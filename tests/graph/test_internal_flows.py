"""_build_internal_flows 算法测试。"""
import pytest
from uasset_read.graph.macro_expander import MacroExpander


def _make_pin(pin_id, name, direction, category="exec", linked_to=None):
    """创建测试用的引脚字典。"""
    return {
        "pin_id": pin_id,
        "pin_name": name,
        "direction": direction,
        "pin_type": {"pin_category": category},
        "parent_pin": None,
        "linked_to_raw": linked_to or [],
    }


def _make_node(guid, class_name, pins=None):
    """创建测试用的节点字典。"""
    return {
        "node_guid": guid,
        "node_type": class_name,
        "pins": pins or [],
    }


def _make_tunnel(name, direction, category="exec", exact_class="UK2Node_Tunnel",
                 b_can_have_inputs=False, b_can_have_outputs=False,
                 pins=None):
    """创建测试用的 Tunnel 节点字典。"""
    return {
        "node_type": "K2Node_Tunnel",
        "exact_class": exact_class,
        "b_can_have_inputs": b_can_have_inputs,
        "b_can_have_outputs": b_can_have_outputs,
        "pins": pins or [_make_pin(f"PID_{name}", name, direction, category)],
    }


def test_empty_entry_tunnels():
    """空 entry_tunnels 应返回空列表。"""
    ctx = {"graphs": []}
    expander = MacroExpander(ctx)
    result = expander._build_internal_flows([], [], [])
    assert result == []


def test_empty_internal_nodes():
    """空 internal_nodes 应返回空列表。"""
    entry = _make_tunnel("exec_in", direction=1)
    result = MacroExpander({"graphs": []})._build_internal_flows([entry], [], [])
    assert result == []


def test_linear_flow():
    """简单线性流：entry → CallFunction → exit。

    entry output pin linked_to → call input pin
    call output pin (Then)
    """
    # entry tunnel: output pin linked to call's input pin
    entry = _make_tunnel("Entry", direction=1, pins=[
        _make_pin("PID_ENTRY_OUT", "exec", 1, linked_to=["PID_CALL_IN"]),
    ])

    # call node: input pin + output pin
    call_node = _make_node("guid_call", "K2Node_CallFunction", [
        _make_pin("PID_CALL_IN", "exec", 0),
        _make_pin("PID_CALL_OUT", "Then", 1),
    ])

    # exit tunnel
    exit_tunnel = _make_tunnel("Exit", direction=0)

    result = MacroExpander({"graphs": []})._build_internal_flows(
        [entry], [call_node], [exit_tunnel]
    )

    assert len(result) == 1
    assert result[0]["entry_tunnel"] == "exec"
    assert len(result[0]["nodes"]) == 1
    assert result[0]["nodes"][0]["node_type"] == "K2Node_CallFunction"


def test_two_node_flow():
    """两节点流：entry → CallA → CallB → exit。"""
    entry = _make_tunnel("Entry", direction=1, pins=[
        _make_pin("PID_ENTRY_OUT", "exec", 1, linked_to=["PID_A_IN"]),
    ])

    call_a = _make_node("guid_a", "K2Node_CallFunction", [
        _make_pin("PID_A_IN", "exec", 0),
        _make_pin("PID_A_OUT", "Then", 1, linked_to=["PID_B_IN"]),
    ])
    call_b = _make_node("guid_b", "K2Node_CallFunction", [
        _make_pin("PID_B_IN", "exec", 0),
        _make_pin("PID_B_OUT", "Then", 1, linked_to=["PID_EXIT_IN"]),
    ])

    # exit tunnel 用独立的 node_guid 和 pin_id
    exit_tunnel = _make_tunnel("Exit", direction=0, pins=[
        _make_pin("PID_EXIT_IN", "exec", 0),
    ])
    exit_tunnel["node_guid"] = "guid_exit"

    result = MacroExpander({"graphs": []})._build_internal_flows(
        [entry], [call_a, call_b], [exit_tunnel]
    )

    assert len(result) == 1
    assert len(result[0]["nodes"]) == 2
    node_types = [n["node_type"] for n in result[0]["nodes"]]
    assert "K2Node_CallFunction" in node_types


def test_cycle_stops_at_limit():
    """内部循环应被安全上限截断。"""
    entry = _make_tunnel("Entry", direction=1, pins=[
        _make_pin("PID_ENTRY_OUT", "exec", 1, linked_to=["PID_SELF_IN"]),
    ])

    # 自引用节点
    self_ref = _make_node("guid_self", "K2Node_CallFunction", [
        _make_pin("PID_SELF_IN", "exec", 0),
        _make_pin("PID_SELF_OUT", "Then", 1, linked_to=["PID_SELF_IN"]),
    ])

    result = MacroExpander({"graphs": []})._build_internal_flows(
        [entry], [self_ref], []
    )

    # 不应无限循环，应正常返回
    assert isinstance(result, list)


def test_no_exit_tunnel():
    """无 exit tunnel 时流应正常终止。"""
    entry = _make_tunnel("Entry", direction=1, pins=[
        _make_pin("PID_ENTRY_OUT", "exec", 1, linked_to=["PID_CALL_IN"]),
    ])

    call_node = _make_node("guid_call", "K2Node_CallFunction", [
        _make_pin("PID_CALL_IN", "exec", 0),
        _make_pin("PID_CALL_OUT", "Then", 1),
    ])

    result = MacroExpander({"graphs": []})._build_internal_flows(
        [entry], [call_node], []
    )

    assert len(result) == 1
    assert len(result[0]["nodes"]) == 1
