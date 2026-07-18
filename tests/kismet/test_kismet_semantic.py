"""Kismet 语义提取与标签输出测试。

合并来源：
- test_goto_label_emission.py — _emit_goto_fallback 标签输出测试
- test_semantic_multi_call.py — Ubergraph 语义提取捕获所有 CallFunction 验证
"""
from __future__ import annotations

from unittest.mock import MagicMock

from uasset_read.kismet.structured_flow import StructuredControlFlow
from uasset_read.kismet.expressions.control_flow import EX_Jump, EX_JumpIfNot
from uasset_read.kismet.semantic import (
    extract_eventgraph_semantic_calls,
    _flow_to_cpp,
)


# ================================================================
# goto 标签输出辅助工厂
# ================================================================

def _make_expr(statement_index: int):
    """创建最简 mock，仅携带 StatementIndex。"""
    class _Stub:
        StatementIndex = statement_index
    return _Stub()


def _make_expr_with_byte_offset(statement_index: int, offset_val: int):
    """创建带 StatementIndex 的 mock 表达式（用于标签映射测试）。"""
    obj = _make_expr(statement_index)
    obj.StatementIndex = offset_val
    return obj


def _make_jump(statement_index: int, code_offset: int) -> EX_Jump:
    """创建 EX_Jump。"""
    jmp = EX_Jump(CodeOffset=code_offset)
    jmp.StatementIndex = statement_index
    return jmp


def _make_jump_if_not(
    statement_index: int,
    code_offset: int,
    boolean_expression=None,
) -> EX_JumpIfNot:
    """创建 EX_JumpIfNot。"""
    jmp = EX_JumpIfNot(CodeOffset=code_offset, BooleanExpression=boolean_expression)
    jmp.StatementIndex = statement_index
    return jmp


# ================================================================
# goto 标签输出测试
# ================================================================

class TestGotoLabelEmission:
    """goto 回退路径的标签输出。"""

    def test_label_emitted_before_target_expression(self):
        """跳转目标对应的表达式前应输出 Label。"""
        # 布局:
        #   idx 0: Jump(CodeOffset=30)  — 跳到 offset 30
        #   idx 1: expr (byte_offset=10)
        #   idx 2: expr (byte_offset=30)  — 跳转目标
        jump = _make_jump(statement_index=0, code_offset=30)
        expr1 = _make_expr_with_byte_offset(10, 10)
        target = _make_expr_with_byte_offset(20, 30)
        expressions = [jump, expr1, target]

        scf = StructuredControlFlow()
        # 手动调用 _emit_goto_fallback（绕过 reconstruct 的结构化检测）
        result = scf._emit_goto_fallback(expressions, jump_targets={30})

        # 应包含 Label_30: 且在 target 表达式之前
        label_lines = [l for l in result if l.startswith("Label_")]
        assert len(label_lines) == 1
        assert "Label_30:" in label_lines[0]
        label_idx = result.index("Label_30:")
        # 标签应出现在 target 的输出行之前
        assert label_idx < len(result) - 1

    def test_multiple_jump_targets_emit_multiple_labels(self):
        """多个跳转目标应各自输出对应标签。"""
        # Jump → 30 和 Jump → 50
        jump1 = _make_jump(statement_index=0, code_offset=30)
        jump2 = _make_jump(statement_index=10, code_offset=50)
        expr_mid = _make_expr_with_byte_offset(20, 20)
        target1 = _make_expr_with_byte_offset(30, 30)
        target2 = _make_expr_with_byte_offset(40, 50)
        expressions = [jump1, jump2, expr_mid, target1, target2]

        scf = StructuredControlFlow()
        result = scf._emit_goto_fallback(expressions, jump_targets={30, 50})

        label_lines = [l for l in result if l.startswith("Label_")]
        assert len(label_lines) == 2
        assert any("Label_30:" in l for l in label_lines)
        assert any("Label_50:" in l for l in label_lines)

    def test_no_duplicate_labels(self):
        """同一跳转目标不应输出重复标签。"""
        # 两个 jump 都指向 offset 30
        jump1 = _make_jump(statement_index=0, code_offset=30)
        jump2 = _make_jump(statement_index=10, code_offset=30)
        target = _make_expr_with_byte_offset(20, 30)
        expressions = [jump1, jump2, target]

        scf = StructuredControlFlow()
        result = scf._emit_goto_fallback(expressions, jump_targets={30})

        label_lines = [l for l in result if l.startswith("Label_")]
        assert len(label_lines) == 1

    def test_no_labels_when_no_jump_targets(self):
        """无跳转目标时不应输出任何标签。"""
        expr1 = _make_expr_with_byte_offset(0, 0)
        expr2 = _make_expr_with_byte_offset(10, 10)
        expressions = [expr1, expr2]

        scf = StructuredControlFlow()
        result = scf._emit_goto_fallback(expressions, jump_targets=set())

        label_lines = [l for l in result if l.startswith("Label_")]
        assert len(label_lines) == 0

    def test_label_uses_codeoffset_value(self):
        """标签名称应使用 jump target 的 CodeOffset 值。"""
        jump = _make_jump(statement_index=0, code_offset=42)
        # target 表达式的 byte_offset 映射到 CodeOffset=42
        target = _make_expr_with_byte_offset(10, 42)
        expressions = [jump, target]

        scf = StructuredControlFlow()
        result = scf._emit_goto_fallback(expressions, jump_targets={42})

        assert "Label_42:" in result

    def test_offset_to_index_mapping_with_statement_index(self):
        """验证 StatementIndex → index 映射正确关联跳转目标。"""
        # Jump(CodeOffset=50) 跳到 offset 50
        # 表达式列表中 idx 2 的 StatementIndex=50
        jump = _make_jump(statement_index=0, code_offset=50)
        expr1 = _make_expr(10)
        target = _make_expr_with_byte_offset(20, 50)
        expressions = [jump, expr1, target]

        # 构建 offset_to_index 映射
        offset_to_index: dict[int, int] = {}
        for idx, expr in enumerate(expressions):
            stmt_idx = getattr(expr, "StatementIndex", None)
            if stmt_idx is not None:
                offset_to_index[stmt_idx] = idx
            if hasattr(expr, "CodeOffset"):
                offset_to_index[expr.CodeOffset] = idx

        # CodeOffset=50 应映射到 idx 0（来自 jump 的 CodeOffset）和 idx 2（来自 StatementIndex）
        # 最终映射为 idx 2（后写覆盖）
        assert offset_to_index.get(50) == 2

    def test_offset_to_index_passed_from_reconstruct(self):
        """验证 reconstruct 传入的 offset_to_index 被正确使用。"""
        # 构造一个不会被 _detect_patterns 识别为结构化模式的序列
        # 从而走 goto 回退路径
        jump = _make_jump(statement_index=0, code_offset=30)
        mid = _make_expr(10)
        target = _make_expr_with_byte_offset(20, 30)
        end = _make_expr(30)  # offset 30 的目标
        expressions = [jump, mid, target, end]

        scf = StructuredControlFlow()
        result = scf.reconstruct(expressions)

        # 应包含 Label_30:
        label_lines = [l for l in result if "Label_30:" in l]
        assert len(label_lines) == 1

    def test_labels_sorted_by_offset(self):
        """多个标签应按偏移量排序输出。"""
        # 乱序跳转目标
        jump1 = _make_jump(statement_index=0, code_offset=50)
        jump2 = _make_jump(statement_index=5, code_offset=20)
        target2 = _make_expr_with_byte_offset(10, 20)
        target1 = _make_expr_with_byte_offset(15, 50)
        expressions = [jump1, jump2, target2, target1]

        scf = StructuredControlFlow()
        result = scf._emit_goto_fallback(expressions, jump_targets={20, 50})

        label_lines = [l for l in result if l.startswith("Label_")]
        assert len(label_lines) == 2
        # Label_20 应在 Label_50 之前（因为 target2 在 target1 之前）
        idx_20 = result.index("Label_20:")
        idx_50 = result.index("Label_50:")
        assert idx_20 < idx_50

    def test_empty_expressions(self):
        """空表达式列表不应抛异常。"""
        scf = StructuredControlFlow()
        result = scf._emit_goto_fallback([], jump_targets={10})
        assert result == []

    def test_label_not_emitted_for_non_target_offset(self):
        """非跳转目标的偏移量不应生成标签。"""
        jump = _make_jump(statement_index=0, code_offset=30)
        expr = _make_expr_with_byte_offset(10, 10)  # 不是跳转目标
        target = _make_expr_with_byte_offset(20, 30)
        expressions = [jump, expr, target]

        scf = StructuredControlFlow()
        result = scf._emit_goto_fallback(expressions, jump_targets={30})

        label_lines = [l for l in result if l.startswith("Label_")]
        assert len(label_lines) == 1
        assert "Label_30:" in label_lines[0]
        # 不应有 Label_10
        assert not any("Label_10:" in l for l in label_lines)


# ================================================================
# 语义提取辅助工厂
# ================================================================

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


# ================================================================
# extract_eventgraph_semantic_calls — 多 CallFunction 提取测试
# ================================================================

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


# ================================================================
# _flow_to_cpp — VariableSet / VariableGet 处理测试
# ================================================================

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
