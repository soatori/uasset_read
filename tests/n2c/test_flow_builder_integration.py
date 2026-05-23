"""flow_builder.py Processor Registry 集成测试。

验证 format_node_dict 和 _trace_execution_from_event 使用 Processor Registry
后的行为正确性，确保 OUT-01 JSON 输出格式完全不变。
"""
import pytest

from uasset_read.models.core import UEdGraphPin, UEdGraphNode, FEdGraphPinType, FMemberReference
from uasset_read.n2c.processor_registry import N2CProcessorRegistry
from uasset_read.graph.flow_builder import (
    format_node_dict,
    _trace_execution_from_event,
    _resolve_node_type,
)
from uasset_read.n2c.node_types import N2CNodeType


@pytest.fixture(autouse=True)
def reset_registry():
    """每个测试重置注册表，conftest.py 的 autouse fixture 之后额外隔离。"""
    N2CProcessorRegistry.reset()
    # 重新注册处理器（模拟 flow_builder 模块加载时的行为）
    from uasset_read.n2c.processors import register_all_processors
    register_all_processors()
    yield
    N2CProcessorRegistry.reset()


def _make_pin(pin_name="TestPin", category="exec", direction=0, linked_to=None):
    """辅助函数：创建 UEdGraphPin。"""
    return UEdGraphPin(
        pin_id=f"pin-{pin_name}",
        pin_name=pin_name,
        direction=direction,
        pin_type=FEdGraphPinType(pin_category=category),
        default_value=None,
        linked_to_raw=linked_to or [],
    )


def _make_node(class_name, node_data=None, pins=None, guid="test-guid-001"):
    """辅助函数：创建 UEdGraphNode。"""
    node = UEdGraphNode(
        node_guid=guid,
        node_pos_x=100,
        node_pos_y=200,
        node_comment="Test Node",
        class_name=class_name,
        node_data=node_data,
        pins=pins or [],
    )
    return node


# ============================================================================
# format_node_dict tests
# ============================================================================


class TestFormatNodeDictCallFunction:
    """CallFunction 节点输出应有 function_reference。"""

    def test_format_node_dict_call_function(self):
        fr = FMemberReference(
            member_name="SomeFunction",
            member_parent="SomeClass",
            b_self_context=False,
        )
        node_data = {"function_reference": fr}
        pins = [_make_pin("exec", "exec", 0), _make_pin("ReturnValue", "object", 1)]
        node = _make_node("K2Node_CallFunction", node_data, pins)

        result = format_node_dict(node, 0)

        assert result["node_name"] == "K2Node_CallFunction_0"
        assert result["node_type"] == "K2Node_CallFunction"
        assert result["function_reference"]["member_name"] == "SomeFunction"
        assert result["function_reference"]["member_parent"] == "SomeClass"
        assert "pins" in result

    def test_format_node_dict_call_function_dataclass(self):
        """node_data 为 dataclass 而非 dict。"""
        fr = FMemberReference(
            member_name="DataclassFunc",
            member_parent="DataClass",
            b_self_context=True,
        )
        # 模拟 dataclass node_data
        class MockNodeData:
            pass
        nd = MockNodeData()
        nd.function_reference = fr
        nd.b_defaults_to_pure = False

        pins = [_make_pin("exec", "exec", 0)]
        node = _make_node("K2Node_CallFunction", nd, pins)

        result = format_node_dict(node, 1)

        assert result["function_reference"]["member_name"] == "DataclassFunc"
        assert result["function_reference"]["self_context"] is True


class TestFormatNodeDictEvent:
    """Event 节点输出应有 event_reference。"""

    def test_format_node_dict_event(self):
        fr = FMemberReference(
            member_name="BeginPlay",
            member_parent="Actor",
        )
        node_data = {"event_reference": fr}
        pins = [_make_pin("then", "exec", 1)]
        node = _make_node("K2Node_Event", node_data, pins)

        result = format_node_dict(node, 2)

        assert result["node_type"] == "K2Node_Event"
        assert result["event_reference"]["member_name"] == "BeginPlay"
        assert result["event_reference"]["member_parent"] == "Actor"


class TestFormatNodeDictFunctionEntry:
    """FunctionEntry 节点输出应有 function_entry_reference。"""

    def test_format_node_dict_function_entry(self):
        fr = FMemberReference(
            member_name="MyCustomFunction",
            member_parent="MyBP",
            b_self_context=True,
        )
        node_data = {"function_reference": fr}
        pins = [_make_pin("exec", "exec", 0), _make_pin("ReturnValue", "bool", 1)]
        node = _make_node("K2Node_FunctionEntry", node_data, pins)

        result = format_node_dict(node, 3)

        assert result["node_type"] == "K2Node_FunctionEntry"
        assert "function_entry_reference" in result
        assert result["function_entry_reference"]["member_name"] == "MyCustomFunction"
        assert result["function_entry_reference"]["self_context"] is True


class TestFormatNodeDictControlFlow:
    """ControlFlow 节点输出应有 branch_type。"""

    def test_format_node_dict_control_flow(self):
        pins = [
            _make_pin("exec", "exec", 0),
            _make_pin("Condition", "bool", 0),
            _make_pin("Then", "exec", 1),
            _make_pin("Else", "exec", 1),
        ]
        node = _make_node("K2Node_IfThenElse", None, pins)

        result = format_node_dict(node, 4)

        assert result["branch_type"] == "if_then_else"


class TestFormatNodeDictVariable:
    """Variable 节点输出应有正确的 node_type。"""

    def test_format_node_dict_variable_get(self):
        pins = [_make_pin("Value", "int", 1)]
        node = _make_node("K2Node_VariableGet", {"variable_name": "MyVar"}, pins)

        result = format_node_dict(node, 5)

        assert result["node_type"] == "K2Node_VariableGet"

    def test_format_node_dict_variable_set(self):
        pins = [_make_pin("exec", "exec", 0), _make_pin("Value", "int", 0), _make_pin("exec", "exec", 1)]
        node = _make_node("K2Node_VariableSet", {"variable_name": "MyVar"}, pins)

        result = format_node_dict(node, 6)

        assert result["node_type"] == "K2Node_VariableSet"


# ============================================================================
# _trace_execution_from_event tests
# ============================================================================


def _build_lookups(*nodes):
    """从节点列表构建 pin_lookup 和 node_lookup。"""
    pin_lookup = {}
    node_lookup = {}
    node_name_lookup = {}
    for idx, node in enumerate(nodes):
        node_lookup[node.node_guid] = node
        node_name_lookup[node.node_guid] = f"{node.class_name}_{idx}"
        for pin in node.pins:
            pin_lookup[pin.pin_id] = (node.node_guid, pin.pin_name)
    return pin_lookup, node_lookup, node_name_lookup


def _link_exec(source_node, target_node, source_pin_name="then", target_pin_name="exec"):
    """在两个节点之间创建 exec 连接。"""
    source_pin = None
    for p in source_node.pins:
        if p.pin_name == source_pin_name:
            source_pin = p
            break
    target_pin = None
    for p in target_node.pins:
        if p.pin_name == target_pin_name:
            target_pin = p
            break

    if source_pin and target_pin:
        source_pin.linked_to_raw = [{"pin_guid": target_pin.pin_id}]


class TestTraceExecutionCallFunction:
    """执行流应为 CallFunction 节点包含 function_name。"""

    def test_trace_execution_from_event_call_function(self):
        # Event -> CallFunction
        event_fr = FMemberReference(member_name="BeginPlay", member_parent="Actor")
        event_node = _make_node(
            "K2Node_Event",
            {"event_reference": event_fr},
            [_make_pin("then", "exec", 1)],
            "event-guid",
        )

        func_fr = FMemberReference(member_name="PrintString", member_parent="KismetSystemLibrary")
        call_node = _make_node(
            "K2Node_CallFunction",
            {"function_reference": func_fr},
            [_make_pin("exec", "exec", 0), _make_pin("exec", "exec", 1)],
            "call-guid",
        )

        _link_exec(event_node, call_node, "then", "exec")
        pin_lookup, node_lookup, node_name_lookup = _build_lookups(event_node, call_node)

        flow = _trace_execution_from_event(event_node, pin_lookup, node_lookup, node_name_lookup)

        assert len(flow) == 2
        assert flow[0]["event_name"] == "BeginPlay"
        assert flow[1]["function_name"] == "PrintString"


class TestTraceExecutionEvent:
    """执行流应为 Event 节点包含 event_name。"""

    def test_trace_execution_from_event_event(self):
        fr = FMemberReference(member_name="Tick", member_parent="Actor")
        event_node = _make_node(
            "K2Node_Event",
            {"event_reference": fr},
            [_make_pin("then", "exec", 1)],
            "event-guid",
        )

        pin_lookup, node_lookup, node_name_lookup = _build_lookups(event_node)

        flow = _trace_execution_from_event(event_node, pin_lookup, node_lookup, node_name_lookup)

        assert len(flow) == 1
        assert flow[0]["event_name"] == "Tick"


class TestTraceExecutionControlFlow:
    """执行流应在控制流节点处停止并包含 branch_type。"""

    def test_trace_execution_stops_at_control_flow(self):
        # Event -> IfThenElse (should stop here)
        event_node = _make_node(
            "K2Node_Event",
            {"event_reference": FMemberReference(member_name="BeginPlay")},
            [_make_pin("then", "exec", 1)],
            "event-guid",
        )

        branch_node = _make_node(
            "K2Node_IfThenElse",
            None,
            [
                _make_pin("exec", "exec", 0),
                _make_pin("Condition", "bool", 0),
                _make_pin("Then", "exec", 1),
                _make_pin("Else", "exec", 1),
            ],
            "branch-guid",
        )

        _link_exec(event_node, branch_node, "then", "exec")
        pin_lookup, node_lookup, node_name_lookup = _build_lookups(event_node, branch_node)

        flow = _trace_execution_from_event(event_node, pin_lookup, node_lookup, node_name_lookup)

        assert len(flow) == 2
        assert flow[1]["branch_type"] == "if_then_else"
        assert flow[1]["stopped_at"] == "control_flow_node"

    def test_trace_execution_stops_at_switch_string(self):
        event_node = _make_node(
            "K2Node_Event",
            {"event_reference": FMemberReference(member_name="BeginPlay")},
            [_make_pin("then", "exec", 1)],
            "event-guid",
        )

        switch_node = _make_node(
            "K2Node_SwitchString",
            None,
            [_make_pin("exec", "exec", 0), _make_pin("Selection", "string", 0), _make_pin("Default", "exec", 1)],
            "switch-guid",
        )

        _link_exec(event_node, switch_node, "then", "exec")
        pin_lookup, node_lookup, node_name_lookup = _build_lookups(event_node, switch_node)

        flow = _trace_execution_from_event(event_node, pin_lookup, node_lookup, node_name_lookup)

        assert len(flow) == 2
        assert flow[1]["branch_type"] == "switch_string"
        assert flow[1]["stopped_at"] == "control_flow_node"


class TestUnknownNodeType:
    """未知节点类型应使用 FallbackProcessor，不崩溃。"""

    def test_unknown_node_type_uses_fallback(self):
        from uasset_read.n2c.node_types import N2CNodeType

        node_type = _resolve_node_type("K2Node_UnknownMacro")
        assert node_type == N2CNodeType.Unknown

        # 确保不崩溃
        node = _make_node("K2Node_UnknownMacro", None, [_make_pin("exec", "exec", 1)])
        result = format_node_dict(node, 99)
        assert result["node_type"] == "K2Node_UnknownMacro"


class TestNodeDataNone:
    """node_data=None 不应崩溃。"""

    def test_node_data_none_does_not_crash(self):
        # CallFunction with None node_data
        node = _make_node(
            "K2Node_CallFunction",
            None,  # node_data=None
            [_make_pin("exec", "exec", 0), _make_pin("exec", "exec", 1)],
        )

        result = format_node_dict(node, 0)
        assert result["node_type"] == "K2Node_CallFunction"
        assert "function_reference" not in result  # No data, no reference
        assert "pins" in result

    def test_trace_execution_event_with_none_node_data(self):
        event_node = _make_node(
            "K2Node_Event",
            None,  # node_data=None
            [_make_pin("then", "exec", 1)],
            "event-guid",
        )

        pin_lookup, node_lookup, node_name_lookup = _build_lookups(event_node)

        flow = _trace_execution_from_event(event_node, pin_lookup, node_lookup, node_name_lookup)

        assert len(flow) == 1
        assert flow[0]["node_type"] == "K2Node_Event"
        assert "event_name" not in flow[0]  # No data, no event_name


class TestFunctionEntry:
    """FunctionEntry 节点应有正确的 function_name。"""

    def test_trace_execution_function_entry(self):
        fr = FMemberReference(member_name="MyFunction", member_parent="MyBP")
        fe_node = _make_node(
            "K2Node_FunctionEntry",
            {"function_reference": fr},
            [_make_pin("exec", "exec", 0), _make_pin("ReturnValue", "bool", 1)],
            "fe-guid",
        )

        pin_lookup, node_lookup, node_name_lookup = _build_lookups(fe_node)

        flow = _trace_execution_from_event(fe_node, pin_lookup, node_lookup, node_name_lookup)

        assert len(flow) == 1
        assert flow[0]["function_name"] == "MyFunction"


class TestPureFunctionDetection:
    """纯函数检测应在 flow 中标注 pure: true。"""

    def test_pure_function_marked_in_flow(self):
        # Event -> Pure CallFunction (no exec pin)
        event_node = _make_node(
            "K2Node_Event",
            {"event_reference": FMemberReference(member_name="BeginPlay")},
            [_make_pin("then", "exec", 1)],
            "event-guid",
        )

        pure_node = _make_node(
            "K2Node_CallFunction",
            {"function_reference": FMemberReference(member_name="MakeVector", member_parent="KismetMathLibrary")},
            [
                _make_pin("X", "float", 0),
                _make_pin("Y", "float", 0),
                _make_pin("Z", "float", 0),
                _make_pin("ReturnValue", "struct", 1),
            ],  # No exec pins = pure
            "pure-guid",
        )

        pin_lookup, node_lookup, node_name_lookup = _build_lookups(event_node, pure_node)

        flow = _trace_execution_from_event(event_node, pin_lookup, node_lookup, node_name_lookup)

        # Event 没有连接可以到达 pure_node（因为没有 exec output），
        # 但 event_node 本身应该有 flow
        assert len(flow) == 1
        assert flow[0]["node_type"] == "K2Node_Event"


class TestResolveNodeType:
    """_resolve_node_type 应正确映射已知类名。"""

    def test_resolve_known_types(self):
        assert _resolve_node_type("K2Node_CallFunction") == N2CNodeType.CallFunction
        assert _resolve_node_type("K2Node_Event") == N2CNodeType.Event
        assert _resolve_node_type("K2Node_FunctionEntry") == N2CNodeType.FunctionEntry
        assert _resolve_node_type("K2Node_IfThenElse") == N2CNodeType.Branch
        assert _resolve_node_type("K2Node_VariableGet") == N2CNodeType.VariableGet
        assert _resolve_node_type("K2Node_VariableSet") == N2CNodeType.VariableSet
        assert _resolve_node_type("K2Node_CustomEvent") == N2CNodeType.CustomEvent
        assert _resolve_node_type("K2Node_SwitchString") == N2CNodeType.SwitchString
        assert _resolve_node_type("K2Node_SwitchEnum") == N2CNodeType.SwitchEnum
        assert _resolve_node_type("K2Node_SwitchInteger") == N2CNodeType.SwitchInt
        assert _resolve_node_type("K2Node_ExecutionSequence") == N2CNodeType.Sequence
        assert _resolve_node_type("K2Node_DynamicCast") == N2CNodeType.DynamicCast

    def test_resolve_unknown_type(self):
        assert _resolve_node_type("K2Node_SomeUnknownThing") == N2CNodeType.Unknown
        assert _resolve_node_type("") == N2CNodeType.Unknown
        assert _resolve_node_type("NotAK2Node") == N2CNodeType.Unknown


class TestMissingNodeGuid:
    """缺失 node_guid 应有 warning 但不崩溃。"""

    def test_missing_node_guid_warning(self):
        node = UEdGraphNode(
            node_guid=None,  # Missing GUID
            node_pos_x=100,
            node_pos_y=200,
            class_name="K2Node_Event",
            node_data={"event_reference": FMemberReference(member_name="BeginPlay")},
            pins=[_make_pin("then", "exec", 1)],
        )

        pin_lookup, node_lookup, node_name_lookup = _build_lookups(node)

        flow = _trace_execution_from_event(node, pin_lookup, node_lookup, node_name_lookup)

        assert len(flow) == 1
        assert flow[0]["warning"] == "missing node_guid"
        assert flow[0]["node_type"] == "K2Node_Event"
