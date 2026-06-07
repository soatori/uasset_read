"""验证 Ubergraph 语义提取捕获所有 CallFunction，不仅第一个。

覆盖：
- extract_eventgraph_semantic_calls 提取每个事件的所有 CallFunction 节点
- _flow_to_cpp 处理 K2Node_VariableSet 和 K2Node_VariableGet 节点
"""
from __future__ import annotations

from unittest.mock import MagicMock

from uasset_read.kismet.semantic import (
    extract_eventgraph_semantic_calls,
    _flow_to_cpp,
)


# ---------------------------------------------------------------------------
# 辅助工厂
# ---------------------------------------------------------------------------

def _make_event_node(
    node_guid: str,
    event_name: str,
    output_exec_pin_id: str = "EV000000000000000000000000000001",
    member_parent: str = "",
) -> MagicMock:
    """创建 K2Node_Event 节点。"""
    node = MagicMock()
    node.node_guid = node_guid
    node.class_name = "K2Node_Event"
    node.node_pos_x = 0
    node.node_pos_y = 0
    node.node_comment = ""
    node._export_object_name = None

    func_ref = MagicMock()
    func_ref.member_name = event_name
    func_ref.member_parent = member_parent
    node.node_data = {"event_reference": func_ref}

    exec_out = MagicMock()
    exec_out.pin_id = output_exec_pin_id
    exec_out.pin_name = "Then"
    exec_out.direction = 1
    exec_out.default_value = ""
    exec_out.linked_to_raw = []
    exec_out.persistent_guid = output_exec_pin_id
    exec_out.pin_type = MagicMock()
    exec_out.pin_type.pin_category = "exec"

    node.pins = [exec_out]
    return node


def _make_call_function_node(
    node_guid: str,
    function_name: str,
    input_exec_pin_id: str = "CF000000000000000000000000000001",
    output_exec_pin_id: str = "CF000000000000000000000000000002",
    member_parent: str = "/Script/Engine.Actor",
    extra_pins: list | None = None,
) -> MagicMock:
    """创建 K2Node_CallFunction 节点。"""
    node = MagicMock()
    node.node_guid = node_guid
    node.class_name = "K2Node_CallFunction"
    node.node_pos_x = 100
    node.node_pos_y = 0
    node.node_comment = ""
    node._export_object_name = None

    func_ref = MagicMock()
    func_ref.member_name = function_name
    func_ref.member_parent = member_parent
    node.node_data = {"function_reference": func_ref}

    exec_in = MagicMock()
    exec_in.pin_id = input_exec_pin_id
    exec_in.pin_name = "execute"
    exec_in.direction = 0
    exec_in.default_value = ""
    exec_in.linked_to_raw = []
    exec_in.persistent_guid = input_exec_pin_id
    exec_in.pin_type = MagicMock()
    exec_in.pin_type.pin_category = "exec"

    exec_out = MagicMock()
    exec_out.pin_id = output_exec_pin_id
    exec_out.pin_name = "then"
    exec_out.direction = 1
    exec_out.default_value = ""
    exec_out.linked_to_raw = []
    exec_out.persistent_guid = output_exec_pin_id
    exec_out.pin_type = MagicMock()
    exec_out.pin_type.pin_category = "exec"

    pins = [exec_in, exec_out]
    if extra_pins:
        pins.extend(extra_pins)
    node.pins = pins
    return node


def _make_variable_set_node(
    node_guid: str,
    variable_name: str,
    input_exec_pin_id: str = "VS000000000000000000000000000001",
    output_exec_pin_id: str = "VS000000000000000000000000000002",
) -> MagicMock:
    """创建 K2Node_VariableSet 节点。"""
    node = MagicMock()
    node.node_guid = node_guid
    node.class_name = "K2Node_VariableSet"
    node.node_pos_x = 200
    node.node_pos_y = 0
    node.node_comment = ""
    node._export_object_name = None
    node.node_data = {"variable_name": variable_name}

    exec_in = MagicMock()
    exec_in.pin_id = input_exec_pin_id
    exec_in.pin_name = "execute"
    exec_in.direction = 0
    exec_in.default_value = ""
    exec_in.linked_to_raw = []
    exec_in.persistent_guid = input_exec_pin_id
    exec_in.pin_type = MagicMock()
    exec_in.pin_type.pin_category = "exec"

    exec_out = MagicMock()
    exec_out.pin_id = output_exec_pin_id
    exec_out.pin_name = "then"
    exec_out.direction = 1
    exec_out.default_value = ""
    exec_out.linked_to_raw = []
    exec_out.persistent_guid = output_exec_pin_id
    exec_out.pin_type = MagicMock()
    exec_out.pin_type.pin_category = "exec"

    node.pins = [exec_in, exec_out]
    return node


def _make_variable_get_node(
    node_guid: str,
    variable_name: str,
) -> MagicMock:
    """创建 K2Node_VariableGet 节点（Pure，无 exec pin）。"""
    node = MagicMock()
    node.node_guid = node_guid
    node.class_name = "K2Node_VariableGet"
    node.node_pos_x = 150
    node.node_pos_y = 50
    node.node_comment = ""
    node._export_object_name = None
    node.node_data = {"variable_name": variable_name}

    value_pin = MagicMock()
    value_pin.pin_id = "VG000000000000000000000000000001"
    value_pin.pin_name = variable_name
    value_pin.direction = 1
    value_pin.default_value = ""
    value_pin.linked_to_raw = []
    value_pin.persistent_guid = "VG000000000000000000000000000001"
    value_pin.pin_type = MagicMock()
    value_pin.pin_type.pin_category = "int"

    node.pins = [value_pin]
    return node


def _make_pin(
    pin_id: str,
    pin_name: str,
    direction: int = 0,
    category: str = "float",
) -> MagicMock:
    """创建普通数据 pin。"""
    pin = MagicMock()
    pin.pin_id = pin_id
    pin.pin_name = pin_name
    pin.direction = direction
    pin.default_value = ""
    pin.linked_to_raw = []
    pin.persistent_guid = pin_id
    pin.pin_type = MagicMock()
    pin.pin_type.pin_category = category
    return pin


def _make_graph(graph_name: str, nodes: list) -> MagicMock:
    """创建 mock UEdGraph。"""
    graph = MagicMock()
    graph.graph_name = graph_name
    graph.graph_class = "EdGraph"
    graph.nodes = nodes
    graph.graph_guid = "test-guid-0001"
    graph.schema = None
    return graph


def _link_pins(from_pin: MagicMock, to_pin: MagicMock) -> None:
    """连接两个 pin（设置 linked_to_raw 单向引用，避免 pin 共享导致的交叉追踪）。"""
    from_pin.linked_to_raw = [{"pin_guid": to_pin.pin_id}]


# ---------------------------------------------------------------------------
# extract_eventgraph_semantic_calls — 多 CallFunction 提取测试
# ---------------------------------------------------------------------------

class TestExtractMultiCallFunction:
    """extract_eventgraph_semantic_calls — 验证提取每个事件的所有 CallFunction 节点。"""

    def test_single_event_single_call(self):
        """单个事件单个调用应正常返回。"""
        event_node = _make_event_node("guid-ev-001", "BeginPlay")
        call_node = _make_call_function_node("guid-cf-001", "PrintString")
        _link_pins(event_node.pins[0], call_node.pins[0])

        graph = _make_graph("EventGraph", [event_node, call_node])
        results = extract_eventgraph_semantic_calls([graph])

        assert len(results) == 1
        assert results[0]["event_name"] == "BeginPlay"
        assert results[0]["function_name"] == "PrintString"

    def test_single_event_multiple_calls(self):
        """单个事件多个 CallFunction 应全部提取。"""
        event_node = _make_event_node("guid-ev-001", "BeginPlay")
        call1 = _make_call_function_node(
            "guid-cf-001", "PrintString",
            input_exec_pin_id="CF0000000000000000000000000000A1",
            output_exec_pin_id="CF0000000000000000000000000000A2",
        )
        call2 = _make_call_function_node(
            "guid-cf-002", "SetActorLocation",
            input_exec_pin_id="CF0000000000000000000000000000B1",
            output_exec_pin_id="CF0000000000000000000000000000B2",
        )
        # 链式连接：Event -> Call1 -> Call2
        _link_pins(event_node.pins[0], call1.pins[0])
        _link_pins(call1.pins[1], call2.pins[0])

        graph = _make_graph("EventGraph", [event_node, call1, call2])
        results = extract_eventgraph_semantic_calls([graph])

        # 关键断言：应返回 2 个结果，不仅第一个
        assert len(results) >= 2, f"应提取至少 2 个 CallFunction，实际得到 {len(results)}"
        func_names = [r["function_name"] for r in results]
        assert "PrintString" in func_names, "PrintString 应出现在结果中"
        assert "SetActorLocation" in func_names, "SetActorLocation 应出现在结果中"

    def test_multiple_events_each_with_calls(self):
        """多个事件各自有调用应全部提取。"""
        event1 = _make_event_node(
            "guid-ev-001", "BeginPlay",
            output_exec_pin_id="EV000000000000000000000000000101",
        )
        call1 = _make_call_function_node(
            "guid-cf-001", "FuncA",
            input_exec_pin_id="CF0000000000000000000000000000C1",
            output_exec_pin_id="CF0000000000000000000000000000C2",
        )
        event2 = _make_event_node(
            "guid-ev-002", "Tick",
            output_exec_pin_id="EV000000000000000000000000000102",
        )
        call2 = _make_call_function_node(
            "guid-cf-003", "FuncB",
            input_exec_pin_id="CF0000000000000000000000000000D1",
            output_exec_pin_id="CF0000000000000000000000000000D2",
        )
        _link_pins(event1.pins[0], call1.pins[0])
        _link_pins(event2.pins[0], call2.pins[0])

        graph = _make_graph("EventGraph", [event1, call1, event2, call2])
        results = extract_eventgraph_semantic_calls([graph])

        assert len(results) >= 2
        func_names = [r["function_name"] for r in results]
        assert "FuncA" in func_names
        assert "FuncB" in func_names

    def test_event_without_call_skipped(self):
        """没有 CallFunction 的事件应被跳过。"""
        event_node = _make_event_node("guid-ev-001", "EmptyEvent")
        graph = _make_graph("EventGraph", [event_node])
        results = extract_eventgraph_semantic_calls([graph])
        assert results == []

    def test_no_event_graph_returns_empty(self):
        """无 EventGraph 时返回空列表。"""
        call_node = _make_call_function_node("guid-cf-001", "SomeFunc")
        graph = _make_graph("SomeOtherGraph", [call_node])
        results = extract_eventgraph_semantic_calls([graph])
        assert results == []


# ---------------------------------------------------------------------------
# _flow_to_cpp — VariableSet / VariableGet 处理测试
# ---------------------------------------------------------------------------

class TestFlowToCppVariableNodes:
    """_flow_to_cpp — 验证处理 VariableSet 和 VariableGet 节点。"""

    def test_variable_set_in_flow(self):
        """执行流中的 VariableSet 节点应出现在 C++ 输出中。"""
        var_set = _make_variable_set_node("guid-vs-001", "Health")
        entry_node = MagicMock()
        entry_node.node_guid = "guid-fe-001"
        entry_node.class_name = "K2Node_FunctionEntry"
        entry_node.node_data = {}

        flows = [{
            "start_event": "FunctionEntry.TakeDamage",
            "nodes": [
                {"node_type": "K2Node_FunctionEntry", "node_guid": "guid-fe-001"},
                {
                    "node_type": "K2Node_VariableSet",
                    "node_guid": "guid-vs-001",
                },
            ],
        }]
        node_lookup = {"guid-vs-001": var_set}
        result = _flow_to_cpp("TakeDamage", flows, node_lookup)

        assert "Health" in result, "变量名 Health 应出现在 C++ 输出中"

    def test_variable_get_in_flow(self):
        """执行流中的 VariableGet 节点应出现在 C++ 输出中。"""
        var_get = _make_variable_get_node("guid-vg-001", "MaxHealth")

        flows = [{
            "start_event": "FunctionEntry.GetHealthPercent",
            "nodes": [
                {"node_type": "K2Node_FunctionEntry", "node_guid": "guid-fe-001"},
                {
                    "node_type": "K2Node_VariableGet",
                    "node_guid": "guid-vg-001",
                },
            ],
        }]
        node_lookup = {"guid-vg-001": var_get}
        result = _flow_to_cpp("GetHealthPercent", flows, node_lookup)

        assert "MaxHealth" in result, "变量名 MaxHealth 应出现在 C++ 输出中"

    def test_mixed_call_and_variable_nodes(self):
        """混合 CallFunction、VariableSet、VariableGet 的执行流应全部处理。"""
        call_node = _make_call_function_node("guid-cf-001", "ApplyDamage")
        var_set = _make_variable_set_node("guid-vs-001", "Health")
        var_get = _make_variable_get_node("guid-vg-001", "MaxHealth")

        flows = [{
            "start_event": "FunctionEntry.TakeDamage",
            "nodes": [
                {"node_type": "K2Node_FunctionEntry", "node_guid": "guid-fe-001"},
                {
                    "node_type": "K2Node_VariableGet",
                    "node_guid": "guid-vg-001",
                },
                {
                    "node_type": "K2Node_CallFunction",
                    "node_guid": "guid-cf-001",
                    "parameters": {
                        "input_params": [
                            {"name": "DamageAmount", "pin_category": "float"},
                        ],
                        "output_params": [],
                    },
                },
                {
                    "node_type": "K2Node_VariableSet",
                    "node_guid": "guid-vs-001",
                },
            ],
        }]
        node_lookup = {
            "guid-cf-001": call_node,
            "guid-vs-001": var_set,
            "guid-vg-001": var_get,
        }
        result = _flow_to_cpp("TakeDamage", flows, node_lookup)

        assert "ApplyDamage" in result, "函数调用应出现在输出中"
        assert "Health" in result, "VariableSet 变量应出现在输出中"
        assert "MaxHealth" in result, "VariableGet 变量应出现在输出中"
