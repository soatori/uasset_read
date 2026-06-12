"""验证执行链能穿透宏实例到内部节点。"""
from uasset_read.graph.flow_builder import _trace_execution_from_event


class FakePinType:
    def __init__(self, category):
        self.pin_category = category


class FakePin:
    def __init__(self, name, direction, pin_category="exec", linked_to=None):
        self.pin_name = name
        self.direction = direction
        self.pin_type = FakePinType(pin_category)
        self.linked_to_raw = linked_to or []
        self.pin_id = f"PID_{name.upper()}"


class FakeNode:
    def __init__(self, guid, class_name, pins=None, node_data=None):
        self.node_guid = guid
        self.class_name = class_name
        self.pins = pins or []
        self.node_data = node_data


def test_flow_penetrates_macro_instance():
    """执行链应穿透 MacroInstance 到其内部节点。"""
    event = FakeNode("guid_event", "K2Node_Event", [
        FakePin("exec", 1, "exec", ["PID_MACRO"]),
    ])
    macro = FakeNode("guid_macro", "K2Node_MacroInstance", [
        FakePin("exec", 0, "exec"),
        FakePin("Then", 1, "exec", ["PID_AFTER"]),
    ])
    after = FakeNode("guid_after", "K2Node_CallFunction", [
        FakePin("Then", 0, "exec"),
    ])

    pin_lookup = {
        "PID_MACRO": ("guid_macro", "exec"),
        "PID_AFTER": ("guid_after", "Then"),
    }
    node_lookup = {
        "guid_event": event,
        "guid_macro": macro,
        "guid_after": after,
    }

    flow = _trace_execution_from_event(event, pin_lookup, node_lookup)

    # 验证 MacroInstance 节点包含 macro_expansion 字段
    macro_flow = next(f for f in flow if f["node_type"] == "K2Node_MacroInstance")
    assert "macro_expansion" in macro_flow, \
        "MacroInstance 应包含 macro_expansion 字段"

    # 验证执行链穿透到了 after 节点
    after_flow = next((f for f in flow if f["node_type"] == "K2Node_CallFunction"), None)
    assert after_flow is not None, "执行链应穿透 MacroInstance 到达后续节点"


def test_standard_macro_marked():
    """标准宏（如 ForLoop）应被识别并标记为标准宏。"""
    event = FakeNode("guid_event", "K2Node_Event", [
        FakePin("exec", 1, "exec", ["PID_FORLOOP"]),
    ])
    forloop = FakeNode("guid_forloop", "K2Node_MacroInstance", [
        FakePin("exec", 0, "exec"),
        FakePin("Loop Body", 1, "exec", ["PID_AFTER"]),
    ], node_data={
        "macro_graph_reference": {
            "graph_name": "ForLoop",
            "graph_guid": "",
        }
    })
    after = FakeNode("guid_after", "K2Node_CallFunction", [
        FakePin("Then", 0, "exec"),
    ])

    pin_lookup = {
        "PID_FORLOOP": ("guid_forloop", "Loop Body"),
        "PID_AFTER": ("guid_after", "Then"),
    }
    node_lookup = {
        "guid_event": event,
        "guid_forloop": forloop,
        "guid_after": after,
    }

    flow = _trace_execution_from_event(event, pin_lookup, node_lookup)

    macro_flow = next(f for f in flow if f["node_type"] == "K2Node_MacroInstance")
    expansion = macro_flow.get("macro_expansion", {})
    assert expansion.get("macro_name") == "ForLoop", \
        "标准宏名称应被识别"
    assert expansion.get("is_standard") is True, \
        "标准宏应标记 is_standard=True"


def test_macro_without_reference():
    """无 macro_graph_reference 的宏实例应标记 unresolved。"""
    event = FakeNode("guid_event", "K2Node_Event", [
        FakePin("exec", 1, "exec", ["PID_MACRO"]),
    ])
    macro = FakeNode("guid_macro", "K2Node_MacroInstance", [
        FakePin("exec", 0, "exec"),
        FakePin("Then", 1, "exec", ["PID_AFTER"]),
    ], node_data={})
    after = FakeNode("guid_after", "K2Node_CallFunction", [
        FakePin("Then", 0, "exec"),
    ])

    pin_lookup = {
        "PID_MACRO": ("guid_macro", "exec"),
        "PID_AFTER": ("guid_after", "Then"),
    }
    node_lookup = {
        "guid_event": event,
        "guid_macro": macro,
        "guid_after": after,
    }

    flow = _trace_execution_from_event(event, pin_lookup, node_lookup)

    macro_flow = next(f for f in flow if f["node_type"] == "K2Node_MacroInstance")
    expansion = macro_flow.get("macro_expansion", {})
    assert expansion.get("unresolved") is True, "无引用的宏应标记为 unresolved"
