"""验证执行流追踪中捕获 exec 引脚名称。"""
import pytest
from uasset_read.graph.flow_builder import (
    _find_next_exec_node,
    _trace_execution_from_event,
)


class FakePinType:
    def __init__(self, category):
        self.pin_category = category


class FakePin:
    def __init__(self, name, direction, pin_category="exec", linked_to=None):
        self.pin_name = name
        self.direction = direction  # 0=Input, 1=Output
        self.pin_type = FakePinType(pin_category)
        self.linked_to_raw = linked_to or []
        self.pin_id = f"pid_{name}"


class FakeNode:
    def __init__(self, guid, class_name, pins=None, node_data=None):
        self.node_guid = guid
        self.class_name = class_name
        self.pins = pins or []
        self.node_data = node_data


def test_trace_captures_exec_pin_name():
    """执行流中每个节点的 transition 应包含 used_exec_pin_name。"""
    # 构建: Event(exec→"Then") → CallFunction(exec→"Completed") → EndNode
    event = FakeNode("guid_event", "K2Node_Event", [
        FakePin("exec", 1, "exec", ["PID_CALL"]),
    ])
    call_func = FakeNode("guid_call", "K2Node_CallFunction", [
        FakePin("Then", 0, "exec"),
        FakePin("Completed", 1, "exec", ["PID_END"]),
    ])
    end_node = FakeNode("guid_end", "K2Node_MakeVariable", [
        FakePin("Completed", 0, "exec"),
    ])

    # _pin_ref_guid 归一化为大写，所以 pin_lookup 键也必须大写
    pin_lookup = {
        "PID_CALL": ("guid_call", "Then"),
        "PID_END": ("guid_end", "Completed"),
    }
    node_lookup = {
        "guid_event": event,
        "guid_call": call_func,
        "guid_end": end_node,
    }

    flow = _trace_execution_from_event(event, pin_lookup, node_lookup)

    # 第一个节点（Event）应记录使用了哪个 exec pin 输出
    assert len(flow) >= 2
    # Event → CallFunction 的连接应记录 pin 名称
    assert flow[0].get("used_exec_pin_name") == "exec"


def test_find_next_exec_node_returns_pin_name():
    """_find_next_exec_node 应返回 (node, pin_name) 元组。"""
    event = FakeNode("guid_event", "K2Node_Event", [
        FakePin("exec", 1, "exec", ["PID_CALL"]),
    ])
    call_func = FakeNode("guid_call", "K2Node_CallFunction", [
        FakePin("Then", 0, "exec"),
    ])

    # _pin_ref_guid 归一化为大写
    pin_lookup = {"PID_CALL": ("guid_call", "Then")}
    node_lookup = {"guid_event": event, "guid_call": call_func}

    next_node, pin_name = _find_next_exec_node(event, pin_lookup, node_lookup)
    assert next_node is not None
    assert next_node.node_guid == "guid_call"
    assert pin_name == "exec"
