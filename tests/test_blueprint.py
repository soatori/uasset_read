"""蓝图模块测试 — 图遍历、Knot 链、循环检测、Kismet 字节码。"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional
from unittest.mock import MagicMock

import pytest

from uasset_read.graph.flow_builder import (
    _resolve_knot_chain,
    _trace_execution_from_event,
    _get_start_event_name,
)
from uasset_read.graph.graph_utils import _iter_normalized_edges
from uasset_read.kismet.bytecode_extractor import _has_false_positive_pattern
from uasset_read.kismet.cfg import build_cfg
from uasset_read.kismet.cfg.data import EdgeKind
from uasset_read.kismet.expressions.control_flow import EX_Jump, EX_JumpIfNot
from uasset_read.kismet.function_resolver import FunctionRefResolver
from uasset_read.kismet.jump_analyzer import JumpAnalyzer
from uasset_read.kismet.translator import MathFunctionCleaner


# === Mock 工具 ===

@dataclass
class FakePinType:
    pin_category: str = ""
    pin_subcategory: str = ""
    is_reference: bool = False
    container_type: int = 0


@dataclass
class FakePin:
    pin_id: str = ""
    pin_name: str = ""
    direction: int = 0
    pin_type: Optional[FakePinType] = None
    linked_to_raw: List[dict] = field(default_factory=list)
    default_value: Optional[str] = None
    persistent_guid: Optional[str] = None


@dataclass
class FakeNode:
    node_guid: str = ""
    class_name: str = "K2Node_CallFunction"
    pins: List[FakePin] = field(default_factory=list)
    node_data: Optional[dict] = None
    node_pos_x: int = 0
    node_pos_y: int = 0
    node_comment: str = ""
    _export_object_name: Optional[str] = None


@dataclass
class FakeGraph:
    graph_name: str = "TestGraph"
    graph_class: str = "EdGraph"
    nodes: List[FakeNode] = field(default_factory=list)
    graph_guid: str = ""
    schema: Optional[str] = None


def _make_linker():
    return MagicMock()

def _make_instance(object_name, object_class=None, outer=None):
    inst = MagicMock()
    inst.object_name = object_name
    inst.object_class = object_class
    inst.outer = outer
    return inst

def _stub(statement_index: int, label: str = "stmt"):
    class _Stub:
        StatementIndex = statement_index
        def __repr__(self):
            return f"<Stub {label}@{statement_index}>"
    return _Stub()

def _make_let(stmt_idx: int):
    from uasset_read.kismet.expressions.assignments import EX_Let
    e = EX_Let()
    e.StatementIndex = stmt_idx
    return e

def _make_jump_if_not(stmt_idx: int, code_offset: int) -> EX_JumpIfNot:
    e = EX_JumpIfNot(CodeOffset=code_offset, BooleanExpression=None)
    e.StatementIndex = stmt_idx
    return e

def _make_end(stmt_idx: int):
    from uasset_read.kismet.expressions.control_flow import EX_EndOfScript
    e = EX_EndOfScript()
    e.StatementIndex = stmt_idx
    return e


# === 测试用例 ===

class TestEdgeDirection:
    """边方向正确性（output -> input）。"""

    def test_output_to_input_edge_direction(self):
        """output pin -> input pin 应产出正确的 from/to 方向。"""
        node_a = FakeNode(
            node_guid="guid-a",
            pins=[FakePin(
                pin_id="PIN-A-OUT", pin_name="then", direction=1,
                pin_type=FakePinType(pin_category="exec"),
            )],
        )
        node_b = FakeNode(
            node_guid="guid-b",
            pins=[FakePin(
                pin_id="PIN-B-IN", pin_name="exec", direction=0,
                pin_type=FakePinType(pin_category="exec"),
            )],
        )
        node_a.pins[0].linked_to_raw = [{"pin_id": "PIN-B-IN"}]
        node_b.pins[0].linked_to_raw = [{"pin_id": "PIN-A-OUT"}]

        graph = FakeGraph(nodes=[node_a, node_b])
        edges = list(_iter_normalized_edges(graph))

        assert len(edges) >= 1
        edge = edges[0]
        assert edge["from_node_guid"] == "guid-a"
        assert edge["from_pin"] == "then"
        assert edge["to_node_guid"] == "guid-b"
        assert edge["to_pin"] == "exec"


class TestKnotChainResolution:
    """Knot 链穿透解析。"""

    def test_simple_knot_chain(self):
        """从目标 pin 穿透 Knot 链应到达非 Knot 终端节点。"""
        source_pin_id = "SOURCEPIN"
        knot_input_id = "KNOTIN"
        knot_output_id = "KNOTOUT"
        target_pin_id = "TARGETPIN"

        source_node = FakeNode(node_guid="src", pins=[
            FakePin(pin_id=source_pin_id, pin_name="ReturnValue", direction=1),
        ])
        knot_node = FakeNode(
            node_guid="knot", class_name="K2Node_Knot",
            pins=[
                FakePin(pin_id=knot_input_id, pin_name="InputPin", direction=0,
                        linked_to_raw=[{"pin_id": source_pin_id}]),
                FakePin(pin_id=knot_output_id, pin_name="OutputPin", direction=1),
            ],
        )
        target_node = FakeNode(node_guid="tgt", pins=[
            FakePin(pin_id=target_pin_id, pin_name="Value", direction=0,
                    linked_to_raw=[{"pin_id": knot_output_id}]),
        ])

        pin_lookup = {
            source_pin_id: ("src", "ReturnValue"),
            knot_input_id: ("knot", "InputPin"),
            knot_output_id: ("knot", "OutputPin"),
            target_pin_id: ("tgt", "Value"),
        }
        node_lookup = {
            "src": source_node,
            "knot": knot_node,
            "tgt": target_node,
        }

        terminal_guid, success = _resolve_knot_chain(
            target_pin_id, pin_lookup, node_lookup
        )
        assert success is True
        assert terminal_guid == target_pin_id


class TestCycleDetection:
    """执行流循环检测。"""

    def test_guid_node_cycle_detected(self):
        """有 GUID 节点自环应 cycle_detected 终止。"""
        pin_in = FakePin(
            pin_id="AA", pin_name="exec",
            direction=0, pin_type=FakePinType(pin_category="exec"),
        )
        pin_out = FakePin(
            pin_id="BB", pin_name="then",
            direction=1, pin_type=FakePinType(pin_category="exec"),
            linked_to_raw=["AA"],
        )
        node = FakeNode(
            node_guid="guid-self",
            class_name="K2Node_CallFunction",
            pins=[pin_out, pin_in],
        )
        pin_lookup = {"aa": ("guid-self", "exec")}
        node_lookup = {"guid-self": node}

        flow = _trace_execution_from_event(
            node, pin_lookup, node_lookup, node_name_lookup={"guid-self": "Self"},
            asset_context={},
        )
        assert any(f.get("cycle_detected") for f in flow), \
            f"Expected cycle_detected in flow: {flow}"


class TestCustomEventNaming:
    """CustomEvent 事件名提取。"""

    def test_custom_event_uses_actual_name(self):
        """CustomEvent 应提取实际事件名。"""
        class FakeNodeData:
            def __init__(self, custom_event_name=None):
                self.custom_event_name = custom_event_name

        class FakeCEPin:
            def __init__(self, name, direction, pin_category="exec"):
                self.pin_name = name
                self.direction = direction
                self.pin_type = type("PT", (), {"pin_category": pin_category})()
                self.linked_to_raw = []
                self.pin_id = f"pid_{name}"

        class FakeCENode:
            def __init__(self, guid, class_name, pins=None, node_data=None):
                self.node_guid = guid
                self.class_name = class_name
                self.pins = pins or []
                self.node_data = node_data

        node_data = FakeNodeData(custom_event_name="OnPlayerDeath")
        node = FakeCENode("guid_1", "K2Node_CustomEvent", node_data=node_data)

        name = _get_start_event_name(node)
        assert name == "CustomEvent.OnPlayerDeath", \
            f"期望 'CustomEvent.OnPlayerDeath'，得到 '{name}'"


class TestFunctionRefResolution:
    """函数引用解析。"""

    def test_basic_resolution(self):
        """正数 StackNode 应解析为 ClassName::FuncName 格式。"""
        linker = _make_linker()
        inst = _make_instance("ReceiveBeginPlay", object_class="AActor")
        linker.resolve_package_index.return_value = inst
        resolver = FunctionRefResolver(linker)
        assert resolver.resolve_string(1) == "AActor::ReceiveBeginPlay"


class TestBuildCfg:
    """CFG 构建。"""

    def test_conditional_edges(self):
        """JumpIfNot 应产生 CONDITIONAL + FALSE_BRANCH 边。"""
        let0 = _make_let(0)
        jmp = _make_jump_if_not(8, 24)
        let1 = _make_let(16)
        let2 = _make_let(24)
        end = _make_end(32)
        cfg = build_cfg([let0, jmp, let1, let2, end])
        bb0 = cfg.blocks[0]
        edge_kinds = set(bb0.edge_kinds.values())
        assert EdgeKind.CONDITIONAL in edge_kinds
        assert EdgeKind.FALSE_BRANCH in edge_kinds


class TestControlFlowDetection:
    """JumpAnalyzer 控制流模式检测。"""

    def test_if_else_pattern(self):
        """JumpIfNot → then → Jump(end) → else → end 应识别为 if_else。"""
        cond = _stub(0)
        jin = EX_JumpIfNot(CodeOffset=30, BooleanExpression=cond)
        jin.StatementIndex = 1
        then_body = _stub(20)
        jmp_end = EX_Jump(CodeOffset=50)
        jmp_end.StatementIndex = 25
        else_body = _stub(30)
        end_expr = _stub(50)
        exprs = [cond, jin, then_body, jmp_end, else_body, end_expr]
        analyzer = JumpAnalyzer(exprs)
        result = analyzer.detect_if_else_pattern(1)
        assert result is not None
        assert result["type"] == "if_else"


class TestBytecodeRecovery:
    """字节码恢复。"""

    def test_valid_bytecode_preserved(self):
        """有效字节码不应被过滤。"""
        data = bytes([0x04, 0x1C, 0x01, 0x02, 0x03, 0x04, 0x53])
        assert _has_false_positive_pattern(data) is False


class TestMathFunctionCleaner:
    """数学函数简化。"""

    def test_add_int_int(self):
        """Add_IntInt->a+b；未知->ClassName::FuncName。"""
        assert MathFunctionCleaner.clean("KismetMathLibrary", "Add_IntInt", ["a", "b"]) == "a + b"
        assert MathFunctionCleaner.clean("KismetMathLibrary", "SomeUnknownFunc", ["a", "b"]) == "KismetMathLibrary::SomeUnknownFunc(a, b)"
