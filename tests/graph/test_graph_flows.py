"""图流算法与偏移读取测试。

合并来源：
- test_internal_flows.py — _build_internal_flows 算法测试
- test_custom_event_naming.py — CustomEvent 使用实际事件名验证
- test_ue_graph_offset.py — UEdGraph 偏移读取修复测试
"""
import pytest
from pathlib import Path

from uasset_read.graph.macro_expander import MacroExpander
from uasset_read.graph.flow_builder import _get_start_event_name


SAMPLES_DIR = Path(__file__).parent / "samples"


# ================================================================
# _build_internal_flows 辅助工厂
# ================================================================

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


# ================================================================
# _build_internal_flows 测试
# ================================================================

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


# ================================================================
# CustomEvent 事件名提取测试
# ================================================================

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


# ================================================================
# UEdGraph 偏移读取测试
# ================================================================

class TestValidateGraphExportOffset:
    """_validate_graph_export_offset 单元测试。"""

    def _make_export(self, object_name, serial_offset, serial_size):
        class FakeExport:
            pass
        exp = FakeExport()
        exp.object_name = object_name
        exp.serial_offset = serial_offset
        exp.serial_size = serial_size
        return exp

    def test_empty_export_returns_true(self):
        """serial_size=0 的空 export 应通过验证。"""
        from uasset_read.graph.parser import _validate_graph_export_offset
        export = self._make_export("EmptyExport", 0, 0)
        assert _validate_graph_export_offset(export, 100000) is True

    def test_valid_offset_returns_true(self):
        """正常偏移应在有效范围内。"""
        from uasset_read.graph.parser import _validate_graph_export_offset
        export = self._make_export("EventGraph", 1000, 500)
        assert _validate_graph_export_offset(export, 100000) is True

    def test_zero_offset_non_default_returns_false(self):
        """非 Default__ export 的 serial_offset=0 应返回 False。"""
        from uasset_read.graph.parser import _validate_graph_export_offset
        export = self._make_export("EventGraph", 0, 500)
        assert _validate_graph_export_offset(export, 100000) is False

    def test_zero_offset_default_export_returns_true(self):
        """Default__ export 的 serial_offset=0 应通过验证。"""
        from uasset_read.graph.parser import _validate_graph_export_offset
        export = self._make_export("Default__EventGraph", 0, 500)
        assert _validate_graph_export_offset(export, 100000) is True

    def test_offset_beyond_archive_returns_false(self):
        """偏移越界应返回 False。"""
        from uasset_read.graph.parser import _validate_graph_export_offset
        export = self._make_export("EventGraph", 95000, 10000)
        assert _validate_graph_export_offset(export, 100000) is False

    def test_unknown_archive_size_skips_boundary_check(self):
        """archive_size=0 时不检查边界（安全降级）。"""
        from uasset_read.graph.parser import _validate_graph_export_offset
        export = self._make_export("EventGraph", 95000, 10000)
        assert _validate_graph_export_offset(export, 0) is True


class TestUEGraphOffset:
    """UEdGraph 偏移读取集成测试。"""

    @pytest.mark.integration
    def test_local_blueprint_graphs_not_partial(self):
        """验证本地蓝图样本解析后不被标记为 partial。"""
        from uasset_read.parse_uasset import parse_package

        path = SAMPLES_DIR / "StackOBot_BP_Drone.uasset"
        if not path.exists():
            pytest.skip("测试样本不存在")

        result = parse_package(str(path))
        assert result.is_success, f"解析失败: {result.errors}"
        assert result.status != "partial", f"合法资产被错误标记为 partial: {result.errors}"
        assert len(result.graphs) > 0, "应解析出蓝图图"

    @pytest.mark.integration
    def test_graph_offset_within_export_bounds(self):
        """验证图数据偏移在 export 边界内。"""
        from uasset_read.parse_uasset import parse_package

        path = SAMPLES_DIR / "StackOBot_BP_Drone.uasset"
        if not path.exists():
            pytest.skip("测试样本不存在")

        result = parse_package(str(path))
        # 检查每个 export 的图偏移是否在有效范围内
        for export in result.export_map:
            serial_offset = getattr(export, "serial_offset", 0)
            serial_size = getattr(export, "serial_size", 0)
            # 偏移不应为 0（除非是特殊 export）
            if serial_size > 0:
                assert serial_offset > 0 or export.object_name.startswith("Default__"), \
                    f"Export {export.object_name} 偏移异常: offset={serial_offset}, size={serial_size}"
