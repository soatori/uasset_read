"""验证 Latent/Async 动作在执行流中被标记。"""
from uasset_read.graph.flow_builder import _trace_execution_from_event


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


def test_async_action_marked_as_latent():
    """K2Node_AsyncAction 应在执行流中标记 latent=True。"""
    # 使用 32 字符 hex GUID 以通过 _is_valid_pin_guid 验证
    pid_event_exec = "A" * 32
    pid_async_input = "B" * 32
    pid_async_output = "C" * 32
    pid_end_input = "D" * 32

    event = FakeNode("guid_event", "K2Node_Event", [
        FakePin("exec", 1, "exec", [pid_async_input]),
    ])
    async_node = FakeNode("guid_async", "K2Node_AsyncAction", [
        FakePin("Then", 0, "exec"),
        FakePin("Completed", 1, "exec", [pid_end_input]),
    ])
    end_node = FakeNode("guid_end", "K2Node_MakeVariable", [
        FakePin("Completed", 0, "exec"),
    ])

    pin_lookup = {
        pid_async_input: ("guid_async", "Then"),
        pid_end_input: ("guid_end", "Completed"),
    }
    node_lookup = {
        "guid_event": event,
        "guid_async": async_node,
        "guid_end": end_node,
    }

    flow = _trace_execution_from_event(event, pin_lookup, node_lookup)

    async_flow = next(f for f in flow if f["node_type"] == "K2Node_AsyncAction")
    assert async_flow.get("latent") is True, "Latent 动作应标记 latent=True"


def test_timeline_marked_as_latent():
    """K2Node_Timeline 应在执行流中标记 latent=True。"""
    pid_event_exec = "A" * 32
    pid_timeline_input = "B" * 32

    event = FakeNode("guid_event", "K2Node_Event", [
        FakePin("exec", 1, "exec", [pid_timeline_input]),
    ])
    timeline = FakeNode("guid_timeline", "K2Node_Timeline", [
        FakePin("Update", 0, "exec"),
    ])

    pin_lookup = {
        pid_timeline_input: ("guid_timeline", "Update"),
    }
    node_lookup = {
        "guid_event": event,
        "guid_timeline": timeline,
    }

    flow = _trace_execution_from_event(event, pin_lookup, node_lookup)

    tl_flow = next(f for f in flow if f["node_type"] == "K2Node_Timeline")
    assert tl_flow.get("latent") is True


def test_normal_node_not_latent():
    """普通节点不应有 latent 标记。"""
    pid_event_exec = "A" * 32
    pid_call_input = "B" * 32

    event = FakeNode("guid_event", "K2Node_Event", [
        FakePin("exec", 1, "exec", [pid_call_input]),
    ])
    call_func = FakeNode("guid_call", "K2Node_CallFunction", [
        FakePin("Then", 0, "exec"),
    ])

    pin_lookup = {pid_call_input: ("guid_call", "Then")}
    node_lookup = {"guid_event": event, "guid_call": call_func}

    flow = _trace_execution_from_event(event, pin_lookup, node_lookup)

    call_flow = next(f for f in flow if f["node_type"] == "K2Node_CallFunction")
    assert "latent" not in call_flow or call_flow.get("latent") is False
