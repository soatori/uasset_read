"""验证 CustomEvent 使用实际事件名而非写死的 'CustomEvent'。"""
from uasset_read.graph.flow_builder import _get_start_event_name


class FakePinType:
    def __init__(self, category):
        self.pin_category = category


class FakePin:
    def __init__(self, name, direction, pin_category="exec"):
        self.pin_name = name
        self.direction = direction
        self.pin_type = FakePinType(pin_category)
        self.linked_to_raw = []
        self.pin_id = f"pid_{name}"


class FakeNodeData:
    def __init__(self, custom_event_name=None):
        self.custom_event_name = custom_event_name


class FakeNode:
    def __init__(self, guid, class_name, pins=None, node_data=None):
        self.node_guid = guid
        self.class_name = class_name
        self.pins = pins or []
        self.node_data = node_data


def test_custom_event_uses_actual_name():
    """CustomEvent 应提取实际事件名。"""
    node_data = FakeNodeData(custom_event_name="OnPlayerDeath")
    node = FakeNode("guid_1", "K2Node_CustomEvent", node_data=node_data)

    name = _get_start_event_name(node)
    assert name == "CustomEvent.OnPlayerDeath", f"期望 'CustomEvent.OnPlayerDeath'，得到 '{name}'"


def test_custom_event_fallback():
    """无事件名时应使用 'CustomEvent' 回退。"""
    node_data = FakeNodeData(custom_event_name=None)
    node = FakeNode("guid_1", "K2Node_CustomEvent", node_data=node_data)

    name = _get_start_event_name(node)
    assert name == "CustomEvent"


def test_custom_event_with_dict_node_data():
    """node_data 为 dict 格式时应正确提取事件名。"""
    node_data = {"custom_event_name": "OnBeginPlay"}
    node = FakeNode("guid_2", "K2Node_CustomEvent", node_data=node_data)

    name = _get_start_event_name(node)
    assert name == "CustomEvent.OnBeginPlay", f"期望 'CustomEvent.OnBeginPlay'，得到 '{name}'"


def test_custom_event_with_dict_node_data_no_name():
    """node_data 为 dict 但无事件名时应回退。"""
    node_data = {"some_other_key": "value"}
    node = FakeNode("guid_3", "K2Node_CustomEvent", node_data=node_data)

    name = _get_start_event_name(node)
    assert name == "CustomEvent"


def test_custom_event_with_raw_properties():
    """node_data 包含 _raw_properties 时应从中提取 CustomPropertyName。"""
    node_data = {"_raw_properties": {"CustomPropertyName": "OnTriggerEnter"}}
    node = FakeNode("guid_4", "K2Node_CustomEvent", node_data=node_data)

    name = _get_start_event_name(node)
    assert name == "CustomEvent.OnTriggerEnter", f"期望 'CustomEvent.OnTriggerEnter'，得到 '{name}'"


def test_custom_event_with_empty_name():
    """事件名为空字符串时应回退。"""
    node_data = {"custom_event_name": ""}
    node = FakeNode("guid_5", "K2Node_CustomEvent", node_data=node_data)

    name = _get_start_event_name(node)
    assert name == "CustomEvent"


def test_custom_event_with_none_node_data():
    """node_data 为 None 时应回退。"""
    node = FakeNode("guid_6", "K2Node_CustomEvent", node_data=None)

    name = _get_start_event_name(node)
    assert name == "CustomEvent"
