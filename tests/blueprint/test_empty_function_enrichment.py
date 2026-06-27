"""空函数体从图拓扑补充的单元测试。

覆盖：
- 空壳函数（≤3 表达式）从 K2Node_FunctionEntry 拓扑补充 C++ 代码
- 有实际字节码的函数（>3 表达式）不被覆盖
- 缺失图数据时不报错
- _find_function_entry 辅助函数
- _flow_to_cpp 流转换
- _format_call_node 节点格式化
"""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from uasset_read.kismet.result import KismetDecompiledResult
from uasset_read.kismet.semantic import (
    enrich_decompiled_functions,
    _enrich_empty_functions_from_graphs,
    _enrich_empty_function_from_graph,
    _find_function_entry,
    _flow_to_cpp,
    _format_call_node,
    _EMPTY_BODY_THRESHOLD,
)


# ---------------------------------------------------------------------------
# 辅助工厂
# ---------------------------------------------------------------------------

def _make_pin(
    pin_id: str,
    pin_name: str,
    direction: int = 0,
    category: str = "exec",
    linked_to_raw: list | None = None,
) -> MagicMock:
    """创建 mock UEdGraphPin。"""
    pin = MagicMock()
    pin.pin_id = pin_id
    pin.pin_name = pin_name
    pin.direction = direction
    pin.default_value = ""
    pin.linked_to_raw = linked_to_raw or []
    pin.persistent_guid = pin_id
    pin.pin_type = MagicMock()
    pin.pin_type.pin_category = category
    pin.pin_type.pin_subcategory = ""
    pin.pin_type.is_reference = False
    return pin


def _make_function_entry_node(
    node_guid: str,
    function_name: str,
    output_exec_pin_id: str = "FE000000000000000000000000000001",
    param_pins: list | None = None,
) -> MagicMock:
    """创建 K2Node_FunctionEntry 节点。"""
    node = MagicMock()
    node.node_guid = node_guid
    node.class_name = "K2Node_FunctionEntry"
    node.node_pos_x = 0
    node.node_pos_y = 0
    node.node_comment = ""
    node._export_object_name = None

    # function_reference
    func_ref = MagicMock()
    func_ref.member_name = function_name
    func_ref.member_parent = ""
    node.node_data = {"function_reference": func_ref}

    # pins: exec output + 参数 pins
    exec_pin = _make_pin(output_exec_pin_id, "Then", direction=1, category="exec")
    pins = [exec_pin]
    if param_pins:
        pins.extend(param_pins)
    node.pins = pins
    return node


def _make_call_function_node(
    node_guid: str,
    function_name: str,
    input_exec_pin_id: str = "CF000000000000000000000000000001",
    output_exec_pin_id: str = "CF000000000000000000000000000002",
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
    func_ref.member_parent = "/Script/Engine.Actor"
    node.node_data = {"function_reference": func_ref}

    exec_in = _make_pin(input_exec_pin_id, "execute", direction=0, category="exec")
    exec_out = _make_pin(output_exec_pin_id, "then", direction=1, category="exec")
    pins = [exec_in, exec_out]
    if extra_pins:
        pins.extend(extra_pins)
    node.pins = pins
    return node


def _make_graph(graph_name: str, nodes: list) -> MagicMock:
    """创建 mock UEdGraph。"""
    graph = MagicMock()
    graph.graph_name = graph_name
    graph.graph_class = "EdGraph"
    graph.nodes = nodes
    graph.graph_guid = "test-guid-0001"
    graph.schema = None
    return graph


def _make_result(
    function_name: str,
    expressions: list | None = None,
    cpp_code: str = "",
    warnings: list | None = None,
) -> KismetDecompiledResult:
    """创建 KismetDecompiledResult。"""
    return KismetDecompiledResult(
        function_name=function_name,
        signature=f"void {function_name}()",
        local_variables=[],
        cpp_code=cpp_code,
        expressions=expressions or [],
        warnings=warnings or [],
    )


# ---------------------------------------------------------------------------
# _find_function_entry 测试
# ---------------------------------------------------------------------------

class TestFindFunctionEntry:
    """_find_function_entry — 图中查找匹配的 FunctionEntry 节点。"""

    def test_exact_match(self):
        """精确匹配函数名。"""
        entry = _make_function_entry_node("guid-001", "Move")
        graph = _make_graph("Move", [entry])
        result = _find_function_entry(graph, "Move")
        assert result is entry

    def test_no_match(self):
        """无匹配节点时返回 None。"""
        entry = _make_function_entry_node("guid-001", "Aim")
        graph = _make_graph("Aim", [entry])
        result = _find_function_entry(graph, "Move")
        assert result is None

    def test_path_form_member_name(self):
        """路径形式 member_name（/Game/.../FunctionName）应正确匹配。"""
        entry = _make_function_entry_node("guid-001", "/Game/BP/Move")
        graph = _make_graph("Move", [entry])
        result = _find_function_entry(graph, "Move")
        assert result is entry

    def test_empty_graph(self):
        """空图返回 None。"""
        graph = _make_graph("Empty", [])
        result = _find_function_entry(graph, "Move")
        assert result is None

    def test_non_function_entry_nodes_ignored(self):
        """非 FunctionEntry 节点被忽略。"""
        call_node = _make_call_function_node("guid-001", "Move")
        graph = _make_graph("Move", [call_node])
        result = _find_function_entry(graph, "Move")
        assert result is None


# ---------------------------------------------------------------------------
# _flow_to_cpp 测试
# ---------------------------------------------------------------------------

class TestFlowToCpp:
    """_flow_to_cpp — 执行流转 C++ 伪代码。"""

    def test_single_call_function(self):
        """单个 CallFunction 节点生成调用语句。"""
        call_node = _make_call_function_node(
            "guid-cf-001", "AddMovementInput",
            extra_pins=[_make_pin("pin-val", "ScaleValue", direction=0, category="float")],
        )
        flows = [{
            "start_event": "FunctionEntry.Move",
            "nodes": [
                {"node_type": "K2Node_FunctionEntry", "node_guid": "guid-fe-001"},
                {
                    "node_type": "K2Node_CallFunction",
                    "node_guid": "guid-cf-001",
                    "parameters": {
                        "input_params": [
                            {"name": "ScaleValue", "pin_category": "float"},
                        ],
                        "output_params": [],
                    },
                },
            ],
        }]
        node_lookup = {"guid-cf-001": call_node}
        result = _flow_to_cpp("Move", flows, node_lookup)
        assert "void Move() {" in result
        assert "AddMovementInput(ScaleValue);" in result
        assert "}" in result

    def test_empty_flow_returns_empty(self):
        """无 CallFunction 节点的流返回空字符串。"""
        flows = [{
            "start_event": "FunctionEntry.Move",
            "nodes": [
                {"node_type": "K2Node_FunctionEntry", "node_guid": "guid-fe-001"},
            ],
        }]
        result = _flow_to_cpp("Move", flows)
        assert result == ""

    def test_non_function_entry_flow_ignored(self):
        """非 FunctionEntry 流被跳过。"""
        flows = [{
            "start_event": "Event.BeginPlay",
            "nodes": [
                {"node_type": "K2Node_Event", "node_guid": "guid-ev-001"},
                {
                    "node_type": "K2Node_CallFunction",
                    "node_guid": "guid-cf-001",
                    "parameters": {"input_params": [], "output_params": []},
                },
            ],
        }]
        result = _flow_to_cpp("Move", flows)
        assert result == ""

    def test_multiple_calls(self):
        """多个 CallFunction 节点生成多行调用。"""
        call1 = _make_call_function_node("guid-cf-001", "GetActorRightVector")
        call2 = _make_call_function_node("guid-cf-002", "AddMovementInput")
        flows = [{
            "start_event": "FunctionEntry.Move",
            "nodes": [
                {"node_type": "K2Node_FunctionEntry", "node_guid": "guid-fe-001"},
                {
                    "node_type": "K2Node_CallFunction",
                    "node_guid": "guid-cf-001",
                    "parameters": {"input_params": [], "output_params": []},
                },
                {
                    "node_type": "K2Node_CallFunction",
                    "node_guid": "guid-cf-002",
                    "parameters": {"input_params": [{"name": "ScaleValue", "pin_category": "float"}], "output_params": []},
                },
            ],
        }]
        node_lookup = {"guid-cf-001": call1, "guid-cf-002": call2}
        result = _flow_to_cpp("Move", flows, node_lookup)
        assert "GetActorRightVector()" in result
        assert "AddMovementInput(ScaleValue)" in result


# ---------------------------------------------------------------------------
# _format_call_node 测试
# ---------------------------------------------------------------------------

class TestFormatCallNode:
    """_format_call_node — 节点信息格式化为函数调用字符串。"""

    def test_with_node_lookup(self):
        """从 node_lookup 提取函数名。"""
        node = _make_call_function_node("guid-cf-001", "AddMovementInput")
        node_info = {
            "node_guid": "guid-cf-001",
            "parameters": {
                "input_params": [
                    {"name": "ScaleValue", "pin_category": "float"},
                ],
                "output_params": [],
            },
        }
        result = _format_call_node(node_info, {"guid-cf-001": node})
        assert result == "AddMovementInput(ScaleValue)"

    def test_without_node_lookup_fallback(self):
        """无 node_lookup 时回退到 CallFunction。"""
        node_info = {
            "node_guid": "guid-cf-001",
            "parameters": {
                "input_params": [
                    {"name": "Val", "pin_category": "float"},
                ],
                "output_params": [],
            },
        }
        result = _format_call_node(node_info)
        assert result == "CallFunction(Val)"

    def test_filters_self_and_exec(self):
        """过滤 self 和 exec pin。"""
        node = _make_call_function_node("guid-cf-001", "Jump")
        node_info = {
            "node_guid": "guid-cf-001",
            "parameters": {
                "input_params": [
                    {"name": "self", "pin_category": "object"},
                    {"name": "execute", "pin_category": "exec"},
                ],
                "output_params": [],
            },
        }
        result = _format_call_node(node_info, {"guid-cf-001": node})
        assert result == "Jump()"


# ---------------------------------------------------------------------------
# 空函数体补充集成测试
# ---------------------------------------------------------------------------

class TestEmptyFunctionEnrichment:
    """空函数体从图拓扑补充 — 集成测试。"""

    def test_empty_stub_enriched_from_graph(self):
        """空壳函数（0 表达式）从图拓扑补充 C++ 代码。"""
        # 构建图：FunctionEntry -> CallFunction(AddMovementInput)
        call_node = _make_call_function_node(
            "guid-cf-001", "AddMovementInput",
            input_exec_pin_id="CF0000000000000000000000000000AA",
            extra_pins=[
                _make_pin("CF0000000000000000000000000000BB", "WorldDirection", direction=0, category="struct"),
                _make_pin("CF0000000000000000000000000000CC", "ScaleValue", direction=0, category="float"),
            ],
        )
        entry_node = _make_function_entry_node(
            "guid-fe-001", "Move",
            output_exec_pin_id="FE0000000000000000000000000000AA",
        )
        # 连接：entry exec out -> call exec in
        entry_node.pins[0].linked_to_raw = [{"pin_guid": "CF0000000000000000000000000000AA"}]
        call_node.pins[0].linked_to_raw = [{"pin_guid": "FE0000000000000000000000000000AA"}]

        graph = _make_graph("Move", [entry_node, call_node])
        result = _make_result("Move", expressions=[])

        _enrich_empty_functions_from_graphs([result], [graph])

        assert result.cpp_code != ""
        assert "void Move() {" in result.cpp_code
        assert result.logic_source == "graph_topology"
        assert any("enriched" in w for w in result.warnings)

    def test_real_bytecode_not_overwritten(self):
        """有实际字节码的函数（>3 表达式）不被覆盖。"""
        call_node = _make_call_function_node("guid-cf-001", "AddMovementInput")
        entry_node = _make_function_entry_node("guid-fe-001", "Move")
        graph = _make_graph("Move", [entry_node, call_node])

        # 有 5 个表达式（超过阈值）和已有 cpp_code
        original_cpp = "void Move() { /* original bytecode */ }"
        expressions = [MagicMock() for _ in range(5)]
        result = _make_result("Move", expressions=expressions, cpp_code=original_cpp)

        _enrich_empty_functions_from_graphs([result], [graph])

        # 应保留原始 cpp_code
        assert result.cpp_code == original_cpp

    def test_missing_graph_data_no_error(self):
        """缺失图数据时不报错，函数保持原样。"""
        result = _make_result("Move", expressions=[])

        # 空图列表
        _enrich_empty_functions_from_graphs([result], [])
        assert result.cpp_code == ""

        # 无匹配图
        other_entry = _make_function_entry_node("guid-fe-001", "Aim")
        graph = _make_graph("Aim", [other_entry])
        _enrich_empty_functions_from_graphs([result], [graph])
        assert result.cpp_code == ""

    def test_already_enriched_not_overwritten(self):
        """已被第一轮 EventGraph 语义丰富的函数不被覆盖。"""
        call_node = _make_call_function_node("guid-cf-001", "AddMovementInput")
        entry_node = _make_function_entry_node("guid-fe-001", "Move")
        graph = _make_graph("Move", [entry_node, call_node])

        result = _make_result(
            "Move",
            expressions=[],
            cpp_code="void Move() { SomeEvent(); }",
            warnings=["Kismet bytecode semantics enriched from EventGraph pin topology"],
        )

        _enrich_empty_functions_from_graphs([result], [graph])

        # 应保留已丰富的 cpp_code
        assert "SomeEvent()" in result.cpp_code

    def test_threshold_boundary(self):
        """恰好等于阈值的表达式数量仍触发补充。"""
        call_node = _make_call_function_node(
            "guid-cf-001", "AddMovementInput",
            input_exec_pin_id="CF0000000000000000000000000000AA",
        )
        entry_node = _make_function_entry_node(
            "guid-fe-001", "Move",
            output_exec_pin_id="FE0000000000000000000000000000AA",
        )
        entry_node.pins[0].linked_to_raw = [{"pin_guid": "CF0000000000000000000000000000AA"}]
        call_node.pins[0].linked_to_raw = [{"pin_guid": "FE0000000000000000000000000000AA"}]

        graph = _make_graph("Move", [entry_node, call_node])
        # 表达式数量 == _EMPTY_BODY_THRESHOLD（3）仍应触发
        expressions = [MagicMock() for _ in range(_EMPTY_BODY_THRESHOLD)]
        result = _make_result("Move", expressions=expressions)

        _enrich_empty_functions_from_graphs([result], [graph])

        # 阈值边界：表达式数量 == threshold，应触发补充
        # 但 len(expressions) > threshold 才跳过，所以 == 时仍补充
        assert any("enriched" in w for w in result.warnings)

    def test_no_matching_function_entry(self):
        """图中无匹配的 FunctionEntry 时函数保持原样。"""
        other_entry = _make_function_entry_node("guid-fe-001", "Aim")
        graph = _make_graph("Aim", [other_entry])
        result = _make_result("Move", expressions=[])

        _enrich_empty_functions_from_graphs([result], [graph])

        assert result.cpp_code == ""
        assert result.logic_source == "current_asset"


# ---------------------------------------------------------------------------
# enrich_decompiled_functions 集成测试
# ---------------------------------------------------------------------------

class TestEnrichDecompliledFunctions:
    """enrich_decompiled_functions — 完整流程集成测试。"""

    def test_empty_function_enriched_even_without_eventgraph(self):
        """无 EventGraph 时仍为空函数体补充。"""
        call_node = _make_call_function_node(
            "guid-cf-001", "AddMovementInput",
            input_exec_pin_id="CF0000000000000000000000000000AA",
            extra_pins=[
                _make_pin("CF0000000000000000000000000000CC", "ScaleValue", direction=0, category="float"),
            ],
        )
        entry_node = _make_function_entry_node(
            "guid-fe-001", "Move",
            output_exec_pin_id="FE0000000000000000000000000000AA",
        )
        entry_node.pins[0].linked_to_raw = [{"pin_guid": "CF0000000000000000000000000000AA"}]
        call_node.pins[0].linked_to_raw = [{"pin_guid": "FE0000000000000000000000000000AA"}]

        # 函数图（非 EventGraph）
        func_graph = _make_graph("Move", [entry_node, call_node])
        result = _make_result("Move", expressions=[])

        enrich_decompiled_functions([result], [func_graph])

        assert result.cpp_code != ""
        assert "void Move() {" in result.cpp_code
        assert result.logic_source == "graph_topology"

    def test_empty_list_no_error(self):
        """空函数列表和空图列表不报错。"""
        enrich_decompiled_functions([], [])
        # 无异常即通过
