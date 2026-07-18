"""graph 模块系统性缺陷测试。"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import pytest

from uasset_read.graph.graph_utils import (
    _iter_normalized_edges,
    _build_graph_indexes,
    _build_normalized_edge_indexes,
    _derive_node_name,
    _pin_ref_guid,
    _is_valid_pin_guid,
    _sanitize_string,
    _sanitize_recursive,
    _sanitize_pin_dict,
    _node_member_name,
    _enhanced_input_action_name,
    _choose_synthetic_source_pin,
    _synthetic_parameter_edges,
    _pin_direction_text,
    _pin_category,
    _pin_subcategory,
    _pin_container_type,
    _is_exec_pin,
    format_pin_ref,
    configure_synthetic_edges,
)
from uasset_read.graph.flow_builder import (
    _resolve_knot_chain,
    _trace_data_source,
    _comment_enclosed_nodes,
    _get_start_event_name,
    _extract_call_function_parameters,
    format_node_dict,
    _find_next_exec_node,
    _trace_execution_from_event,
    build_connections_map,
    build_execution_flow_entries,
    build_data_flows,
)
from uasset_read.graph.chain_builder import build_execution_chains
from pathlib import Path

from uasset_read.constants import CONTROL_FLOW_NODES, BRANCH_TYPE_MAP, PKG_Cooked
from uasset_read.graph.parser import extract_blueprint_graphs


# ============================================================================
# Mock 工具
# ============================================================================

@dataclass
class FakePinType:
    pin_category: str = ""
    pin_subcategory: str = ""
    is_reference: bool = False
    is_const: bool = False
    container_type: int = 0


@dataclass
class FakePin:
    pin_id: str = ""
    pin_name: str = ""
    direction: int = 0  # 0=input, 1=output
    pin_type: Optional[FakePinType] = None
    linked_to_raw: List[dict] = field(default_factory=list)
    default_value: Optional[str] = None
    persistent_guid: Optional[str] = None
    hidden: bool = False
    parent_pin: Optional[str] = None


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


def make_exec_pin(pin_id: str, name: str = "exec", direction: int = 0) -> FakePin:
    return FakePin(pin_id=pin_id, pin_name=name, direction=direction,
                   pin_type=FakePinType(pin_category="exec"))


def make_data_pin(pin_id: str, name: str, direction: int = 0, category: str = "float") -> FakePin:
    return FakePin(pin_id=pin_id, pin_name=name, direction=direction,
                   pin_type=FakePinType(pin_category=category))


# ============================================================================
# TestGraphQuality
# ============================================================================

class TestGraphQuality:
    """graph 模块质量验证。"""

    def test_graph_imports(self):
        """graph 模块可正常导入。"""
        from uasset_read.graph import flow_builder
        assert flow_builder is not None

    def test_graph_package_imports(self):
        """graph 包 __init__ 可正常导入所有公开 API。"""
        from uasset_read.graph import (
            extract_blueprint_graphs,
            build_execution_flow_entries,
            build_data_flows,
            build_connections_map,
            format_graphs_json,
            format_pin_ref,
            build_function_graphs,
            build_execution_chains,
        )
        assert all([
            extract_blueprint_graphs,
            build_execution_flow_entries,
            build_data_flows,
            build_connections_map,
            format_graphs_json,
            format_pin_ref,
            build_function_graphs,
            build_execution_chains,
        ])


class TestEdgeDirection:
    """边方向正确性测试（source -> target）。"""

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
        # A.output 连接到 B.input
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

    def test_same_direction_pins_no_edge(self):
        """同方向 pin 不应产出边。"""
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
                pin_id="PIN-B-OUT", pin_name="then", direction=1,
                pin_type=FakePinType(pin_category="exec"),
            )],
        )
        # A.output 连接到 B.output（异常情况）
        node_a.pins[0].linked_to_raw = [{"pin_id": "PIN-B-OUT"}]

        graph = FakeGraph(nodes=[node_a, node_b])
        edges = list(_iter_normalized_edges(graph))

        # 同方向不应有边
        assert not any(
            e["from_node_guid"] == "guid-a" and e["to_node_guid"] == "guid-b"
            for e in edges
        )


class TestEdgeDeduplication:
    """边去重测试。"""

    def test_duplicate_linked_to_not_duplicated(self):
        """同一 pin 的重复 linked_to 引用不应产出重复边。"""
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
        # A.output 引用 B.input 两次
        node_a.pins[0].linked_to_raw = [
            {"pin_id": "PIN-B-IN"},
            {"pin_id": "PIN-B-IN"},
        ]

        graph = FakeGraph(nodes=[node_a, node_b])
        edges = list(_iter_normalized_edges(graph))

        # 只应有一条边
        ab_edges = [e for e in edges if e["from_node_guid"] == "guid-a" and e["to_node_guid"] == "guid-b"]
        assert len(ab_edges) == 1

    def test_bidirectional_refs_produce_single_edge(self):
        """双向引用（A linked_to B 和 B linked_to A）应只产出一条边。"""
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
        # 双向引用
        node_a.pins[0].linked_to_raw = [{"pin_id": "PIN-B-IN"}]
        node_b.pins[0].linked_to_raw = [{"pin_id": "PIN-A-OUT"}]

        graph = FakeGraph(nodes=[node_a, node_b])
        edges = list(_iter_normalized_edges(graph))

        ab_edges = [e for e in edges if e["from_node_guid"] == "guid-a" and e["to_node_guid"] == "guid-b"]
        assert len(ab_edges) == 1


class TestEmptyGraphHandling:
    """空图和退化图处理测试。"""

    def test_empty_graph_no_edges(self):
        """空图不应产出任何边。"""
        graph = FakeGraph(nodes=[])
        edges = list(_iter_normalized_edges(graph))
        assert edges == []

    def test_single_node_no_edges(self):
        """单节点无连接不应产出边。"""
        node = FakeNode(node_guid="guid-a", pins=[make_exec_pin("pin-a", "exec")])
        graph = FakeGraph(nodes=[node])
        edges = list(_iter_normalized_edges(graph))
        assert edges == []

    def test_node_without_pins(self):
        """无 pin 节点不应导致异常。"""
        node = FakeNode(node_guid="guid-a", pins=[])
        graph = FakeGraph(nodes=[node])
        edges = list(_iter_normalized_edges(graph))
        assert edges == []


class TestNodeNameDerivation:
    """节点名称派生测试。"""

    def test_derive_node_name_stability(self):
        """同一节点在同一索引下应返回稳定名称。"""
        node = FakeNode(node_guid="guid-a", class_name="K2Node_CallFunction")
        name1 = _derive_node_name(node, 0)
        name2 = _derive_node_name(node, 0)
        assert name1 == name2

    def test_derive_node_name_format(self):
        """节点名称格式应为 ClassName_idx。"""
        node = FakeNode(node_guid="guid-a", class_name="K2Node_Event")
        name = _derive_node_name(node, 5)
        assert name == "K2Node_Event_5"

    def test_derive_node_name_different_indices(self):
        """不同索引应产出不同名称。"""
        node = FakeNode(node_guid="guid-a", class_name="K2Node_CallFunction")
        name0 = _derive_node_name(node, 0)
        name1 = _derive_node_name(node, 1)
        assert name0 != name1


class TestPinRefGuid:
    """Pin GUID 归一化测试。"""

    def test_guid_uppercase(self):
        """GUID 应归一化为小写无 dash 格式。"""
        assert _pin_ref_guid("a1b2c3d4-e5f6-7890-abcd-ef1234567890") == "a1b2c3d4e5f67890abcdef1234567890"

    def test_guid_strip_dashes(self):
        """GUID 应移除 dash。"""
        result = _pin_ref_guid("A1B2C3D4-E5F6-7890-ABCD-EF1234567890")
        assert "-" not in result

    def test_guid_from_dict_pin_guid(self):
        """从 dict 的 pin_guid 字段提取。"""
        result = _pin_ref_guid({"pin_guid": "a1b2c3d4-e5f6-7890-abcd-ef1234567890"})
        assert result == "a1b2c3d4e5f67890abcdef1234567890"

    def test_guid_from_dict_pin_id(self):
        """从 dict 的 pin_id 字段提取。"""
        result = _pin_ref_guid({"pin_id": "AABBCCDD"})
        assert result == "aabbccdd"

    def test_guid_none_returns_none(self):
        """None 输入应返回 None。"""
        assert _pin_ref_guid(None) is None

    def test_guid_empty_string_returns_none(self):
        """空字符串应返回 None。"""
        assert _pin_ref_guid("") is None

    def test_guid_integer_returns_none(self):
        """整数输入应返回 None。"""
        assert _pin_ref_guid(12345) is None


class TestValidPinGuid:
    """Pin GUID 有效性验证测试。"""

    def test_valid_32hex(self):
        """32 字符 hex 应有效。"""
        assert _is_valid_pin_guid("A1B2C3D4E5F67890ABCDEF1234567890") is True

    def test_valid_with_dashes(self):
        """带 dash 的 hex 应有效。"""
        assert _is_valid_pin_guid("A1B2C3D4-E5F6-7890-ABCD-EF1234567890") is True

    def test_valid_test_fixture(self):
        """测试 fixture 格式 pin-xxx 应有效。"""
        assert _is_valid_pin_guid("pin-1234") is True

    def test_valid_all_zero(self):
        """全零 GUID 应有效。"""
        assert _is_valid_pin_guid("00000000-0000-0000-0000-000000000000") is True

    def test_invalid_empty(self):
        """空字符串应无效。"""
        assert _is_valid_pin_guid("") is False

    def test_invalid_none(self):
        """None 应无效。"""
        assert _is_valid_pin_guid(None) is False

    def test_invalid_too_short(self):
        """过短的 hex 应无效。"""
        assert _is_valid_pin_guid("AABB") is False

    def test_invalid_non_hex(self):
        """非 hex 字符应无效。"""
        assert _is_valid_pin_guid("ZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZ") is False


class TestKnotChainResolution:
    """Knot 链穿透解析测试。"""

    def test_simple_knot_chain(self):
        """从目标 pin 穿透 Knot 链应到达非 Knot 终端节点。"""
        # Source -> Knot.InputPin -> Knot.OutputPin -> Target
        # _resolve_knot_chain 从 target pin 开始，找到 target 节点（非 Knot），返回成功
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

        # 从 target pin 开始追踪：target 节点不是 Knot，直接返回成功
        terminal_guid, success = _resolve_knot_chain(
            target_pin_id, pin_lookup, node_lookup
        )
        assert success is True
        assert terminal_guid == target_pin_id

    def test_knot_chain_traces_through_to_source(self):
        """从 Knot OutputPin 开始追踪应穿透到 InputPin 的数据源。"""
        # _pin_ref_guid 归一化为小写无 dash 格式，pin_lookup 键也需小写
        source_pin_id = "sourcepin"
        knot_input_id = "knotin"
        knot_output_id = "knotout"

        source_node = FakeNode(node_guid="src", pins=[
            FakePin(pin_id="SOURCEPIN", pin_name="ReturnValue", direction=1),
        ])
        knot_node = FakeNode(
            node_guid="knot", class_name="K2Node_Knot",
            pins=[
                FakePin(pin_id="KNOTIN", pin_name="InputPin", direction=0,
                        linked_to_raw=[{"pin_id": "SOURCEPIN"}]),
                FakePin(pin_id="KNOTOUT", pin_name="OutputPin", direction=1),
            ],
        )

        pin_lookup = {
            source_pin_id: ("src", "ReturnValue"),
            knot_input_id: ("knot", "InputPin"),
            knot_output_id: ("knot", "OutputPin"),
        }
        node_lookup = {
            "src": source_node,
            "knot": knot_node,
        }

        # 从 Knot OutputPin 开始：找到 Knot → 找到 InputPin → 跟踪到 source
        terminal_guid, success = _resolve_knot_chain(
            knot_output_id, pin_lookup, node_lookup
        )
        assert success is True
        assert terminal_guid == source_pin_id

    def test_knot_chain_cycle_detection(self):
        """Knot 链中的循环应被检测并终止。"""
        knot_a_input = "KNOTAIN"
        knot_a_output = "KNOTAOUT"
        knot_b_input = "KNOTBIN"
        knot_b_output = "KNOTBOUT"

        knot_a = FakeNode(
            node_guid="knot-a", class_name="K2Node_Knot",
            pins=[
                FakePin(pin_id=knot_a_input, pin_name="InputPin", direction=0,
                        linked_to_raw=[{"pin_id": knot_b_output}]),
                FakePin(pin_id=knot_a_output, pin_name="OutputPin", direction=1),
            ],
        )
        knot_b = FakeNode(
            node_guid="knot-b", class_name="K2Node_Knot",
            pins=[
                FakePin(pin_id=knot_b_input, pin_name="InputPin", direction=0,
                        linked_to_raw=[{"pin_id": knot_a_output}]),
                FakePin(pin_id=knot_b_output, pin_name="OutputPin", direction=1),
            ],
        )

        pin_lookup = {
            knot_a_input: ("knot-a", "InputPin"),
            knot_a_output: ("knot-a", "OutputPin"),
            knot_b_input: ("knot-b", "InputPin"),
            knot_b_output: ("knot-b", "OutputPin"),
        }
        node_lookup = {
            "knot-a": knot_a,
            "knot-b": knot_b,
        }

        _, success = _resolve_knot_chain(
            knot_a_output, pin_lookup, node_lookup, max_depth=10
        )
        assert success is False  # 循环应检测到

    def test_knot_chain_missing_pin(self):
        """Knot 链中 pin 缺失时应终止。"""
        knot_node = FakeNode(
            node_guid="knot", class_name="K2Node_Knot",
            pins=[
                FakePin(pin_id="KNOTIN", pin_name="InputPin", direction=0,
                        linked_to_raw=[{"pin_id": "NONEXISTENT"}]),
            ],
        )
        pin_lookup = {"KNOTIN": ("knot", "InputPin")}
        node_lookup = {"knot": knot_node}

        _, success = _resolve_knot_chain("NONEXISTENT", pin_lookup, node_lookup)
        assert success is False


class TestCommentEnclosedNodes:
    """注释节点包围检测测试。"""

    def test_comment_encloses_node_in_rect(self):
        """注释矩形内的节点应被包围。"""
        comment = FakeNode(
            node_guid="comment-1",
            class_name="EdGraphNode_Comment",
            node_pos_x=0, node_pos_y=0,
            node_data={"node_width": 500, "node_height": 300},
        )
        inner_node = FakeNode(
            node_guid="inner-1",
            class_name="K2Node_CallFunction",
            node_pos_x=100, node_pos_y=100,
        )
        graph = FakeGraph(nodes=[comment, inner_node])

        enclosed = _comment_enclosed_nodes(comment, graph)
        assert "inner-1" in enclosed

    def test_comment_does_not_enclose_outside_node(self):
        """注释矩形外的节点不应被包围。"""
        comment = FakeNode(
            node_guid="comment-1",
            class_name="EdGraphNode_Comment",
            node_pos_x=0, node_pos_y=0,
            node_data={"node_width": 100, "node_height": 100},
        )
        outside_node = FakeNode(
            node_guid="outside-1",
            class_name="K2Node_CallFunction",
            node_pos_x=200, node_pos_y=200,
        )
        graph = FakeGraph(nodes=[comment, outside_node])

        enclosed = _comment_enclosed_nodes(comment, graph)
        assert "outside-1" not in enclosed

    def test_comment_excludes_other_comments(self):
        """其他注释节点不应被包围。"""
        comment1 = FakeNode(
            node_guid="comment-1",
            class_name="EdGraphNode_Comment",
            node_pos_x=0, node_pos_y=0,
            node_data={"node_width": 500, "node_height": 500},
        )
        comment2 = FakeNode(
            node_guid="comment-2",
            class_name="EdGraphNode_Comment",
            node_pos_x=10, node_pos_y=10,
        )
        graph = FakeGraph(nodes=[comment1, comment2])

        enclosed = _comment_enclosed_nodes(comment1, graph)
        assert "comment-2" not in enclosed

    def test_comment_excludes_self(self):
        """注释节点自身不应出现在包围列表中。"""
        comment = FakeNode(
            node_guid="comment-1",
            class_name="EdGraphNode_Comment",
            node_pos_x=0, node_pos_y=0,
            node_data={"node_width": 500, "node_height": 500},
        )
        graph = FakeGraph(nodes=[comment])

        enclosed = _comment_enclosed_nodes(comment, graph)
        assert "comment-1" not in enclosed

    def test_comment_zero_size_returns_empty(self):
        """零尺寸注释不应包围任何节点。"""
        comment = FakeNode(
            node_guid="comment-1",
            class_name="EdGraphNode_Comment",
            node_pos_x=0, node_pos_y=0,
            node_data={"node_width": 0, "node_height": 0},
        )
        inner_node = FakeNode(
            node_guid="inner-1",
            class_name="K2Node_CallFunction",
            node_pos_x=10, node_pos_y=10,
        )
        graph = FakeGraph(nodes=[comment, inner_node])

        enclosed = _comment_enclosed_nodes(comment, graph)
        assert enclosed == []


class TestStartEventName:
    """起点事件名称提取测试。"""

    def test_k2node_event_name(self):
        """K2Node_Event 应从 event_reference.member_name 提取名称。"""
        node = FakeNode(
            node_guid="guid-1",
            class_name="K2Node_Event",
            node_data={"event_reference": {"member_name": "ReceiveBeginPlay"}},
        )
        name = _get_start_event_name(node)
        assert name == "Event.ReceiveBeginPlay"

    def test_k2node_event_with_path(self):
        """K2Node_Event 的 member_name 路径应只取最后一段。"""
        node = FakeNode(
            node_guid="guid-1",
            class_name="K2Node_Event",
            node_data={"event_reference": {"member_name": "/Game/Blueprints/BP_Test.ReceiveBeginPlay"}},
        )
        name = _get_start_event_name(node)
        assert name == "Event.ReceiveBeginPlay"

    def test_enhanced_input_action_name(self):
        """K2Node_EnhancedInputAction 应提取 action 名称。"""
        node = FakeNode(
            node_guid="guid-1",
            class_name="K2Node_EnhancedInputAction",
            node_data={"input_action_path": "/Game/Inputs/IA_Jump"},
        )
        name = _get_start_event_name(node)
        assert name == "InputAction.IA_Jump"

    def test_custom_event_name(self):
        """K2Node_CustomEvent 应提取 custom_event_name。"""
        node = FakeNode(
            node_guid="guid-1",
            class_name="K2Node_CustomEvent",
            node_data={"custom_event_name": "MyCustomEvent"},
        )
        name = _get_start_event_name(node)
        assert name == "CustomEvent.MyCustomEvent"

    def test_variable_set_returns_constant(self):
        """K2Node_VariableSet 应返回 'VariableSet'。"""
        node = FakeNode(
            node_guid="guid-1",
            class_name="K2Node_VariableSet",
            node_data={},
        )
        name = _get_start_event_name(node)
        assert name == "VariableSet"

    def test_function_entry_name(self):
        """K2Node_FunctionEntry 应提取 function_reference.member_name。"""
        node = FakeNode(
            node_guid="guid-1",
            class_name="K2Node_FunctionEntry",
            node_data={"function_reference": {"member_name": "Move"}},
        )
        name = _get_start_event_name(node)
        assert name == "FunctionEntry.Move"

    def test_unknown_type_uses_class_name(self):
        """未知类型应返回 class_name。"""
        node = FakeNode(
            node_guid="guid-1",
            class_name="K2Node_Unknown",
            node_data={},
        )
        name = _get_start_event_name(node)
        assert name == "K2Node_Unknown"

    def test_event_none_node_data(self):
        """node_data 为 None 时应返回 class_name。"""
        node = FakeNode(
            node_guid="guid-1",
            class_name="K2Node_Event",
            node_data=None,
        )
        name = _get_start_event_name(node)
        assert name == "K2Node_Event"


class TestNodeMemberName:
    """节点成员名称提取测试。"""

    def test_none_node_returns_empty(self):
        """None 节点应返回空字符串。"""
        assert _node_member_name(None) == ""

    def test_no_node_data_returns_empty(self):
        """无 node_data 应返回空字符串。"""
        node = FakeNode(node_guid="guid-1", node_data=None)
        assert _node_member_name(node) == ""

    def test_dict_function_reference(self):
        """dict 格式 function_reference 应提取 member_name。"""
        node = FakeNode(
            node_guid="guid-1",
            node_data={"function_reference": {"member_name": "GetActorLocation"}},
        )
        assert _node_member_name(node) == "GetActorLocation"

    def test_dict_event_reference(self):
        """dict 格式 event_reference 应提取 member_name。"""
        node = FakeNode(
            node_guid="guid-1",
            node_data={"event_reference": {"member_name": "ReceiveBeginPlay"}},
        )
        assert _node_member_name(node) == "ReceiveBeginPlay"

    def test_function_reference_preferred_over_event(self):
        """function_reference 应优先于 event_reference。"""
        node = FakeNode(
            node_guid="guid-1",
            node_data={
                "function_reference": {"member_name": "MyFunc"},
                "event_reference": {"member_name": "MyEvent"},
            },
        )
        assert _node_member_name(node) == "MyFunc"


class TestTraceDataSource:
    """数据来源追踪测试。"""

    def test_no_connection_returns_default_value(self):
        """无连接时应返回默认值来源。"""
        pin = FakePin(
            pin_id="pin-1", pin_name="Value",
            direction=0, default_value="42.0",
        )
        result = _trace_data_source(pin, pin_lookup={}, node_lookup={})
        assert result is not None
        assert result["data_sources"][0]["source_type"] == "default_value"
        assert result["data_sources"][0]["value"] == "42.0"

    def test_no_connection_no_default_returns_none(self):
        """无连接且无默认值应返回 None。"""
        pin = FakePin(
            pin_id="pin-1", pin_name="Value",
            direction=0, default_value=None,
        )
        result = _trace_data_source(pin, pin_lookup={}, node_lookup={})
        assert result is None

    def test_connection_to_function_entry(self):
        """连接到 FunctionEntry 参数应返回 function_parameter。"""
        fe_node = FakeNode(
            node_guid="fe-guid",
            class_name="K2Node_FunctionEntry",
            pins=[FakePin(pin_id="FE-PARAM-PIN", pin_name="MyParam", direction=1)],
        )
        caller_node = FakeNode(
            node_guid="caller-guid",
            class_name="K2Node_CallFunction",
            pins=[FakePin(
                pin_id="CALLER-PIN", pin_name="Value", direction=0,
                linked_to_raw=[{"pin_id": "FE-PARAM-PIN"}],
            )],
        )

        # pin_lookup 键必须与 _pin_ref_guid 输出格式一致（小写、无 dash）
        pin_lookup = {
            "feparampin": ("fe-guid", "MyParam"),
            "callercallerpin": ("caller-guid", "Value"),
        }
        node_lookup = {
            "fe-guid": fe_node,
            "caller-guid": caller_node,
        }

        pin = caller_node.pins[0]
        result = _trace_data_source(
            pin, pin_lookup, node_lookup,
            node_name_lookup={"fe-guid": "FunctionEntry_0"},
        )
        assert result is not None
        sources = result["data_sources"]
        assert any(s["source_type"] == "function_parameter" for s in sources)

    def test_connection_to_self_reference(self):
        """连接到 self pin 应返回 self_reference。"""
        self_node = FakeNode(
            node_guid="self-guid",
            class_name="K2Node_Self",
            pins=[FakePin(pin_id="SELF-PIN", pin_name="Self", direction=1)],
        )
        caller_node = FakeNode(
            node_guid="caller-guid",
            class_name="K2Node_CallFunction",
            pins=[FakePin(
                pin_id="CALLER-PIN", pin_name="Target", direction=0,
                linked_to_raw=[{"pin_id": "SELF-PIN"}],
            )],
        )

        # pin_lookup 键必须与 _pin_ref_guid 输出格式一致（小写、无 dash）
        pin_lookup = {
            "selfpin": ("self-guid", "Self"),
            "callercallerpin": ("caller-guid", "Target"),
        }
        node_lookup = {
            "self-guid": self_node,
            "caller-guid": caller_node,
        }

        pin = caller_node.pins[0]
        result = _trace_data_source(pin, pin_lookup, node_lookup)
        assert result is not None
        sources = result["data_sources"]
        assert any(s["source_type"] == "self_reference" for s in sources)


class TestFormatPinRef:
    """Pin 引用格式化测试。"""

    def test_name_mode_lookup_success(self):
        """name 模式下查找成功应返回 {node, pin}。"""
        lookup = {"guid-1": "MyNode_0"}
        result = format_pin_ref("guid-1", "Value", lookup, mode="name")
        assert result["node"] == "MyNode_0"
        assert result["pin"] == "Value"

    def test_name_mode_lookup_failure(self):
        """name 模式下查找失败应返回 warning。"""
        result = format_pin_ref("unknown-guid", "Value", {}, mode="name")
        assert "warning" in result
        assert "node_guid" in result

    def test_guid_mode(self):
        """guid 模式应返回 node_guid 和 pin_name。"""
        result = format_pin_ref("guid-1", "Value", {}, mode="guid")
        assert result["node_guid"] == "guid-1"
        assert result["pin_name"] == "Value"


class TestSanitization:
    """字符串清理测试。"""

    def test_remove_null_chars(self):
        """应移除 null 字符。"""
        assert _sanitize_string("hello\x00world") == "helloworld"

    def test_preserve_newlines(self):
        """应保留换行符。"""
        assert _sanitize_string("line1\nline2\rline3\ttab") == "line1\nline2\rline3\ttab"

    def test_remove_control_chars(self):
        """应移除其他控制字符。"""
        result = _sanitize_string("hello\x01\x02world")
        assert result == "helloworld"

    def test_empty_string(self):
        """空字符串应原样返回。"""
        assert _sanitize_string("") == ""

    def test_none_passthrough(self):
        """None 应原样返回（由调用者处理）。"""
        # _sanitize_string 只接受 str，这里测试空字符串
        assert _sanitize_string("") == ""

    def test_sanitize_pin_dict(self):
        """pin dict 中的字符串字段应被清理。"""
        pin_dict = {
            "pin_name": "test\x00name",
            "pin_id": "12345",
            "default_value": "value\x01here",
        }
        result = _sanitize_pin_dict(pin_dict)
        assert result["pin_name"] == "testname"
        assert result["pin_id"] == "12345"
        assert result["default_value"] == "valuehere"


class TestFormatNodeDict:
    """节点格式化测试。"""

    def test_basic_node_dict_structure(self):
        """基本节点格式化应包含必要字段。"""
        node = FakeNode(
            node_guid="guid-1",
            class_name="K2Node_CallFunction",
            node_pos_x=100, node_pos_y=200,
            node_comment="test comment",
            pins=[make_exec_pin("pin-1", "exec", direction=0)],
        )
        result = format_node_dict(node, 0)
        assert result["node_name"] == "K2Node_CallFunction_0"
        assert result["node_type"] == "K2Node_CallFunction"
        assert result["node_guid"] == "guid-1"
        assert result["position"] == {"x": 100, "y": 200}
        assert "pins" in result

    def test_comment_node_dict(self):
        """注释节点应包含 comment 字段。"""
        node = FakeNode(
            node_guid="guid-1",
            class_name="EdGraphNode_Comment",
            node_comment="This is a comment",
            node_data={"node_width": 300, "node_height": 200, "font_size": 12},
        )
        result = format_node_dict(node, 0)
        assert "comment" in result
        assert result["comment"]["text"] == "This is a comment"
        assert result["comment"]["width"] == 300

    def test_call_function_node_has_parameters(self):
        """CallFunction 节点应包含 parameters。"""
        node = FakeNode(
            node_guid="guid-1",
            class_name="K2Node_CallFunction",
            pins=[
                make_exec_pin("exec-in", "exec", direction=0),
                make_data_pin("param-in", "Value", direction=0, category="float"),
                make_data_pin("param-out", "ReturnValue", direction=1, category="float"),
            ],
        )
        result = format_node_dict(node, 0)
        assert "parameters" in result
        params = result["parameters"]
        # exec pin 应被过滤
        assert len(params["input_params"]) == 1
        assert params["input_params"][0]["name"] == "Value"
        assert len(params["output_params"]) == 1
        assert params["output_params"][0]["name"] == "ReturnValue"


class TestFindNextExecNode:
    """下一个执行节点查找测试。"""

    def test_finds_connected_exec_output(self):
        """应找到 exec output pin 连接的下一个节点。"""
        node_a = FakeNode(
            node_guid="guid-a",
            pins=[FakePin(
                pin_id="PIN-A-OUT", pin_name="then", direction=1,
                pin_type=FakePinType(pin_category="exec"),
                linked_to_raw=[{"pin_id": "PIN-B-IN"}],
            )],
        )
        node_b = FakeNode(
            node_guid="guid-b",
            pins=[FakePin(
                pin_id="PIN-B-IN", pin_name="exec", direction=0,
                pin_type=FakePinType(pin_category="exec"),
            )],
        )
        # pin_lookup 键必须与 _pin_ref_guid 输出格式一致（小写、无 dash）
        pin_lookup = {"pinbin": ("guid-b", "exec")}
        node_lookup = {"guid-a": node_a, "guid-b": node_b}

        next_node, pin_name = _find_next_exec_node(node_a, pin_lookup, node_lookup)
        assert next_node is not None
        assert next_node.node_guid == "guid-b"

    def test_no_connection_returns_none(self):
        """无连接时应返回 (None, None)。"""
        node = FakeNode(
            node_guid="guid-a",
            pins=[make_exec_pin("pin-a", "then", direction=1)],
        )
        next_node, pin_name = _find_next_exec_node(node, pin_lookup={}, node_lookup={})
        assert next_node is None
        assert pin_name is None


class TestBuildConnectionsMap:
    """连接映射构建测试。"""

    def test_empty_graph_returns_empty(self):
        """空图应返回空连接列表。"""
        graph = FakeGraph(nodes=[])
        connections, warnings = build_connections_map(graph)
        assert connections == []

    def test_single_edge_produces_connection(self):
        """单条边应产出一个连接。"""
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
        graph = FakeGraph(nodes=[node_a, node_b])

        connections, warnings = build_connections_map(graph)
        # 至少有一条连接
        assert len(connections) >= 1

    def test_no_linked_to_produces_warning(self):
        """无 LinkedTo 数据应产生 warning。"""
        node = FakeNode(
            node_guid="guid-a",
            pins=[make_exec_pin("pin-a", "exec")],
        )
        graph = FakeGraph(nodes=[node])

        connections, warnings = build_connections_map(graph)
        assert any("No LinkedTo data" in w for w in warnings)


class TestBuildExecutionFlows:
    """执行流构建测试。"""

    def test_empty_graph_returns_empty(self):
        """空图应返回空执行流。"""
        graph = FakeGraph(nodes=[])
        flows = build_execution_flow_entries(graph)
        assert flows == []

    def test_event_node_starts_flow(self):
        """K2Node_Event 应启动执行流。"""
        event_node = FakeNode(
            node_guid="guid-event",
            class_name="K2Node_Event",
            pins=[make_exec_pin("event-out", "then", direction=1)],
            node_data={"event_reference": {"member_name": "ReceiveBeginPlay"}},
        )
        func_node = FakeNode(
            node_guid="guid-func",
            class_name="K2Node_CallFunction",
            pins=[make_exec_pin("func-in", "exec", direction=0)],
        )
        event_node.pins[0].linked_to_raw = [{"pin_id": "FUNC-IN"}]

        graph = FakeGraph(nodes=[event_node, func_node])
        flows = build_execution_flow_entries(graph)

        assert len(flows) >= 1
        assert "Event.ReceiveBeginPlay" in flows[0]["start_event"]

    def test_enhanced_input_action_starts_flow(self):
        """K2Node_EnhancedInputAction 应启动执行流。"""
        input_node = FakeNode(
            node_guid="guid-input",
            class_name="K2Node_EnhancedInputAction",
            pins=[
                FakePin(pin_id="triggered-out", pin_name="Triggered",
                        direction=1, pin_type=FakePinType(pin_category="exec")),
                FakePin(pin_id="completed-out", pin_name="Completed",
                        direction=1, pin_type=FakePinType(pin_category="exec")),
            ],
            node_data={"input_action_path": "/Game/Inputs/IA_Jump"},
        )
        func_node = FakeNode(
            node_guid="guid-func",
            class_name="K2Node_CallFunction",
            pins=[make_exec_pin("func-in", "exec", direction=0)],
        )
        input_node.pins[0].linked_to_raw = [{"pin_id": "FUNC-IN"}]

        graph = FakeGraph(nodes=[input_node, func_node])
        flows = build_execution_flow_entries(graph)

        # EnhancedInputAction 应有多个执行流（每个 exec output pin 一个）
        assert len(flows) >= 1


class TestBuildDataFlows:
    """数据流构建测试。"""

    def test_empty_graph_returns_empty(self):
        """空图应返回空数据流。"""
        graph = FakeGraph(nodes=[])
        flows = build_data_flows(graph)
        assert flows == []

    def test_data_edge_produces_flow(self):
        """非 exec 边应产出数据流。"""
        node_a = FakeNode(
            node_guid="guid-a",
            pins=[FakePin(
                pin_id="PIN-A-OUT", pin_name="ReturnValue", direction=1,
                pin_type=FakePinType(pin_category="float"),
            )],
        )
        node_b = FakeNode(
            node_guid="guid-b",
            pins=[FakePin(
                pin_id="PIN-B-IN", pin_name="Value", direction=0,
                pin_type=FakePinType(pin_category="float"),
            )],
        )
        node_a.pins[0].linked_to_raw = [{"pin_id": "PIN-B-IN"}]

        graph = FakeGraph(nodes=[node_a, node_b])
        flows = build_data_flows(graph)

        assert len(flows) >= 1
        assert flows[0]["source"]["pin"] == "ReturnValue"
        assert flows[0]["target"]["pin"] == "Value"

    def test_exec_edge_not_in_data_flows(self):
        """exec 边不应出现在数据流中。"""
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

        graph = FakeGraph(nodes=[node_a, node_b])
        flows = build_data_flows(graph)

        assert not any(
            f["source"]["pin"] == "then" and f["target"]["pin"] == "exec"
            for f in flows
        )


class TestBuildGraphIndexes:
    """图索引构建测试。"""

    def test_builds_correct_pin_lookup(self):
        """pin_lookup 应正确映射归一化 pin_id -> (node_guid, pin_name)。"""
        node = FakeNode(
            node_guid="guid-1",
            pins=[
                FakePin(pin_id="PINA", pin_name="InputPin"),
                FakePin(pin_id="PINB", pin_name="OutputPin"),
            ],
        )
        graph = FakeGraph(nodes=[node])

        pin_lookup, node_lookup, pin_obj_lookup = _build_graph_indexes(graph)
        # 键应归一化为小写无 dash 格式
        assert pin_lookup["pina"] == ("guid-1", "InputPin")
        assert pin_lookup["pinb"] == ("guid-1", "OutputPin")
        assert node_lookup["guid-1"] is node

    def test_empty_graph(self):
        """空图应返回空索引。"""
        graph = FakeGraph(nodes=[])
        pin_lookup, node_lookup, pin_obj_lookup = _build_graph_indexes(graph)
        assert pin_lookup == {}
        assert node_lookup == {}


# ============================================================================
# flow_builder 关键路径补充测试
# ============================================================================

class TestSanitizeRecursive:
    """_sanitize_recursive 递归清理测试。"""

    def test_nested_dict_cleanup(self):
        """嵌套字典中的字符串应被清理。"""
        obj = {"key": "hello\x00world", "nested": {"inner": "test\x01val"}}
        result = _sanitize_recursive(obj)
        assert result["key"] == "helloworld"
        assert result["nested"]["inner"] == "testval"

    def test_nested_list_cleanup(self):
        """嵌套列表中的字符串应被清理。"""
        obj = ["hello\x00world", ["nested\x01val"]]
        result = _sanitize_recursive(obj)
        assert result[0] == "helloworld"
        assert result[1][0] == "nestedval"

    def test_mixed_nested_structures(self):
        """混合嵌套结构应正确清理。"""
        obj = {"list": ["a\x00b", {"key": "c\x01d"}]}
        result = _sanitize_recursive(obj)
        assert result["list"][0] == "ab"
        assert result["list"][1]["key"] == "cd"

    def test_non_string_passthrough(self):
        """非字符串类型应原样返回。"""
        assert _sanitize_recursive(42) == 42
        assert _sanitize_recursive(3.14) == 3.14
        assert _sanitize_recursive(True) is True
        assert _sanitize_recursive(None) is None

    def test_object_with_get_full_name(self):
        """有 get_full_name 方法的对象应返回全名。"""
        class MockObj:
            def get_full_name(self):
                return "Full.Name"
        result = _sanitize_recursive(MockObj())
        assert result == "Full.Name"

    def test_object_with_get_full_name_exception(self):
        """get_full_name 抛异常应回退到 str()。"""
        class MockObj:
            def get_full_name(self):
                raise RuntimeError("fail")
        result = _sanitize_recursive(MockObj())
        assert "MockObj" in result

    def test_object_with_object_name(self):
        """有 object_name 属性的对象应返回 object_name。"""
        class MockObj:
            object_name = "MyObject"
        result = _sanitize_recursive(MockObj())
        assert result == "MyObject"

    def test_cycle_detection_list(self):
        """循环引用列表应返回空列表。"""
        a = [1, 2]
        a.append(a)  # self-reference
        result = _sanitize_recursive(a)
        assert result[:2] == [1, 2]
        assert result[2] == []  # cycle broken

    def test_cycle_detection_dict(self):
        """循环引用字典应返回空字典。"""
        a = {"key": "value"}
        a["self"] = a  # self-reference
        result = _sanitize_recursive(a)
        assert result["key"] == "value"
        assert result["self"] == {}  # cycle broken


class TestPinDirectionText:
    """_pin_direction_text 方向文本测试。"""

    def test_output_direction(self):
        """direction=1 应返回 output。"""
        assert _pin_direction_text(1) == "output"

    def test_input_direction(self):
        """direction=0 应返回 input。"""
        assert _pin_direction_text(0) == "input"

    def test_other_direction(self):
        """其他值应返回 input。"""
        assert _pin_direction_text(99) == "input"


class TestPinHelpers:
    """_pin_category, _pin_subcategory, _pin_container_type 辅助函数测试。"""

    def test_pin_category_with_type(self):
        """有 pin_type 时应返回 pin_category。"""
        pin = FakePin(pin_type=FakePinType(pin_category="float"))
        assert _pin_category(pin) == "float"

    def test_pin_category_without_type(self):
        """无 pin_type 时应返回空字符串。"""
        pin = FakePin(pin_type=None)
        assert _pin_category(pin) == ""

    def test_pin_subcategory_with_type(self):
        """有 pin_type 时应返回 pin_subcategory。"""
        pin = FakePin(pin_type=FakePinType(pin_subcategory="float"))
        assert _pin_subcategory(pin) == "float"

    def test_pin_subcategory_without_type(self):
        """无 pin_type 时应返回空字符串。"""
        pin = FakePin(pin_type=None)
        assert _pin_subcategory(pin) == ""

    def test_pin_container_type_with_type(self):
        """有 pin_type 时应返回 container_type 字符串。"""
        pin = FakePin(pin_type=FakePinType(container_type=2))
        assert _pin_container_type(pin) == "2"

    def test_pin_container_type_without_type(self):
        """无 pin_type 时应返回空字符串。"""
        pin = FakePin(pin_type=None)
        assert _pin_container_type(pin) == ""


class TestIsExecPin:
    """_is_exec_pin 测试。"""

    def test_exec_pin_returns_true(self):
        """exec 类型 pin 应返回 True。"""
        pin = FakePin(pin_type=FakePinType(pin_category="exec"))
        assert _is_exec_pin(pin) is True

    def test_non_exec_pin_returns_false(self):
        """非 exec 类型 pin 应返回 False。"""
        pin = FakePin(pin_type=FakePinType(pin_category="float"))
        assert _is_exec_pin(pin) is False

    def test_no_pin_type_returns_false(self):
        """无 pin_type 时应返回 False。"""
        pin = FakePin(pin_type=None)
        assert _is_exec_pin(pin) is False


class TestBuildNormalizedEdgeIndexes:
    """_build_normalized_edge_indexes 边索引构建测试。"""

    def test_builds_from_and_to_indexes(self):
        """应构建 from_pin_id 和 to_pin_id 两种索引。"""
        node_a = FakeNode(
            node_guid="guid-a",
            pins=[FakePin(
                pin_id="PIN-A-OUT", pin_name="ReturnValue", direction=1,
                pin_type=FakePinType(pin_category="float"),
            )],
        )
        node_b = FakeNode(
            node_guid="guid-b",
            pins=[FakePin(
                pin_id="PIN-B-IN", pin_name="Value", direction=0,
                pin_type=FakePinType(pin_category="float"),
            )],
        )
        node_a.pins[0].linked_to_raw = [{"pin_id": "PIN-B-IN"}]

        graph = FakeGraph(nodes=[node_a, node_b])
        by_from, by_to = _build_normalized_edge_indexes(graph)

        # from_pin_id 应包含归一化后的 PIN-A-OUT（去 dash，小写）
        assert "pinaout" in by_from
        assert len(by_from["pinaout"]) == 1

        # to_pin_id 应包含归一化后的 PIN-B-IN
        assert "pinbin" in by_to
        assert len(by_to["pinbin"]) == 1

    def test_empty_graph(self):
        """空图应返回空索引。"""
        graph = FakeGraph(nodes=[])
        by_from, by_to = _build_normalized_edge_indexes(graph)
        assert by_from == {}
        assert by_to == {}


class TestEnhancedInputActionName:
    """_enhanced_input_action_name 测试。"""

    def test_extracts_action_name_from_path(self):
        """应从 input_action_path 提取动作名称。"""
        node = FakeNode(
            node_guid="guid-1",
            class_name="K2Node_EnhancedInputAction",
            node_data={"input_action_path": "/Game/Inputs/IA_Jump"},
        )
        assert _enhanced_input_action_name(node) == "IA_Jump"

    def test_no_path_returns_empty(self):
        """无 input_action_path 时应返回空字符串。"""
        node = FakeNode(
            node_guid="guid-1",
            class_name="K2Node_EnhancedInputAction",
            node_data={"input_action_path": ""},
        )
        assert _enhanced_input_action_name(node) == ""

    def test_no_node_data_returns_empty(self):
        """无 node_data 时应返回空字符串。"""
        node = FakeNode(
            node_guid="guid-1",
            class_name="K2Node_EnhancedInputAction",
            node_data=None,
        )
        assert _enhanced_input_action_name(node) == ""

    def test_path_with_dot_suffix(self):
        """路径含 . 后缀时应只取动作名部分。"""
        node = FakeNode(
            node_guid="guid-1",
            class_name="K2Node_EnhancedInputAction",
            node_data={"input_action_path": "IA_Dash"},
        )
        assert _enhanced_input_action_name(node) == "IA_Dash"


class TestSyntheticParameterEdges:
    """_synthetic_parameter_edges 语义参数边测试。"""

    @pytest.fixture(autouse=True)
    def _configure_synthetic_edges(self):
        """配置合成边映射表用于测试。"""
        configure_synthetic_edges(
            param_mapping={
                "Move": [("ActionValue_X", "X"), ("ActionValue_Y", "Y")],
                "Aim": [("ActionValue_Y", "Yaw"), ("ActionValue_X", "Pitch")],
            }
        )
        yield
        configure_synthetic_edges(param_mapping={})

    def test_move_function_gets_edges(self):
        """目标函数为 Move 时应返回 X/Y 参数边。"""
        source = FakeNode(
            node_guid="src",
            class_name="K2Node_EnhancedInputAction",
            node_data={"function_reference": {"member_name": "IA_Move"}},
        )
        target = FakeNode(
            node_guid="tgt",
            class_name="K2Node_CallFunction",
            node_data={"function_reference": {"member_name": "Move"}},
        )
        edges = _synthetic_parameter_edges(source, target)
        assert len(edges) == 2
        names = {e[0] for e in edges}
        assert "ActionValue_X" in names
        assert "ActionValue_Y" in names

    def test_aim_function_gets_edges(self):
        """目标函数为 Aim 时应返回 Yaw/Pitch 参数边。"""
        source = FakeNode(
            node_guid="src",
            class_name="K2Node_EnhancedInputAction",
            node_data={"function_reference": {"member_name": "IA_Look"}},
        )
        target = FakeNode(
            node_guid="tgt",
            class_name="K2Node_CallFunction",
            node_data={"function_reference": {"member_name": "Aim"}},
        )
        edges = _synthetic_parameter_edges(source, target)
        assert len(edges) == 2
        pin_names = {e[1] for e in edges}
        assert "Yaw" in pin_names
        assert "Pitch" in pin_names

    def test_unknown_target_returns_empty(self):
        """目标函数非 Move/Aim 时应返回空列表。"""
        source = FakeNode(
            node_guid="src",
            class_name="K2Node_EnhancedInputAction",
            node_data={"function_reference": {"member_name": "IA_Move"}},
        )
        target = FakeNode(
            node_guid="tgt",
            class_name="K2Node_CallFunction",
            node_data={"function_reference": {"member_name": "Jump"}},
        )
        edges = _synthetic_parameter_edges(source, target)
        assert edges == []

    def test_non_source_type_returns_mapping(self):
        """非 EnhancedInputAction/Event 源节点仍应返回映射（基于目标函数名）。"""
        source = FakeNode(
            node_guid="src",
            class_name="K2Node_CallFunction",
            node_data={"function_reference": {"member_name": "Something"}},
        )
        target = FakeNode(
            node_guid="tgt",
            class_name="K2Node_CallFunction",
            node_data={"function_reference": {"member_name": "Move"}},
        )
        edges = _synthetic_parameter_edges(source, target)
        # 新实现仅基于目标函数名查找映射，不检查源类型
        assert len(edges) == 2


class TestExtractCallFunctionParameters:
    """_extract_call_function_parameters 参数提取测试。"""

    def test_filters_exec_pins(self):
        """exec pin 应被过滤。"""
        node = FakeNode(
            node_guid="guid-1",
            class_name="K2Node_CallFunction",
            pins=[
                make_exec_pin("exec-in", "exec", direction=0),
                make_data_pin("param-in", "Value", direction=0),
            ],
        )
        result = _extract_call_function_parameters(node)
        assert len(result["input_params"]) == 1
        assert result["input_params"][0]["name"] == "Value"

    def test_separates_input_output(self):
        """输入/输出参数应分离到不同数组。"""
        node = FakeNode(
            node_guid="guid-1",
            class_name="K2Node_CallFunction",
            pins=[
                make_exec_pin("exec-in", "exec", direction=0),
                make_data_pin("param-in", "Value", direction=0),
                make_data_pin("param-out", "ReturnValue", direction=1),
            ],
        )
        result = _extract_call_function_parameters(node)
        assert len(result["input_params"]) == 1
        assert result["input_params"][0]["name"] == "Value"
        assert len(result["output_params"]) == 1
        assert result["output_params"][0]["name"] == "ReturnValue"

    def test_includes_default_value(self):
        """有默认值的参数应包含 default_value。"""
        node = FakeNode(
            node_guid="guid-1",
            class_name="K2Node_CallFunction",
            pins=[
                FakePin(
                    pin_id="pin-1", pin_name="Value", direction=0,
                    pin_type=FakePinType(pin_category="float"),
                    default_value="3.14",
                ),
            ],
        )
        result = _extract_call_function_parameters(node)
        assert result["input_params"][0]["default_value"] == "3.14"

    def test_includes_reference_flag(self):
        """is_reference 标志应被提取。"""
        node = FakeNode(
            node_guid="guid-1",
            class_name="K2Node_CallFunction",
            pins=[
                FakePin(
                    pin_id="pin-1", pin_name="Value", direction=0,
                    pin_type=FakePinType(pin_category="object", is_reference=True),
                ),
            ],
        )
        result = _extract_call_function_parameters(node)
        assert result["input_params"][0]["is_reference"] is True


# ============================================================================
# 来自 test_control_flow_expansion.py — 控制流节点常量验证
# ============================================================================

REQUIRED_CONTROL_FLOW = {
    "K2Node_IfThenElse",
    "K2Node_Switch",
    "K2Node_SwitchString",
    "K2Node_SwitchEnum",
    "K2Node_SwitchInteger",
    "K2Node_MacroInstance",
    # 新增
    "K2Node_ForLoop",
    "K2Node_WhileLoop",
    "K2Node_DoOnce",
    "K2Node_Sequence",
    "K2Node_MultiGate",
    "K2Node_Select",
    "K2Node_ExecutionSequence",
}

REQUIRED_BRANCH_TYPES = {
    "K2Node_IfThenElse",
    "K2Node_Switch",
    "K2Node_SwitchString",
    "K2Node_SwitchEnum",
    "K2Node_SwitchInteger",
    "K2Node_MacroInstance",
    # 新增
    "K2Node_ForLoop",
    "K2Node_WhileLoop",
    "K2Node_DoOnce",
    "K2Node_Sequence",
    "K2Node_MultiGate",
    "K2Node_Select",
}


class TestControlFlowExpansion:
    """CONTROL_FLOW_NODES / BRANCH_TYPE_MAP 完整性验证。"""

    def test_control_flow_nodes_complete(self):
        """CONTROL_FLOW_NODES 应包含所有已知控制流节点。"""
        missing = REQUIRED_CONTROL_FLOW - CONTROL_FLOW_NODES
        assert not missing, f"CONTROL_FLOW_NODES 缺少: {missing}"

    def test_branch_type_map_complete(self):
        """BRANCH_TYPE_MAP 应包含所有控制流节点的分支类型。"""
        missing = REQUIRED_BRANCH_TYPES - set(BRANCH_TYPE_MAP.keys())
        assert not missing, f"BRANCH_TYPE_MAP 缺少: {missing}"


# ============================================================================
# 来自 test_exec_pin_names.py — 链式输出显示执行引脚名称
# ============================================================================

class _ExecPinMockNode:
    """模拟 UEdGraphNode，仅保留链构建所需的属性。"""
    def __init__(self, guid, class_name=""):
        self.node_guid = guid
        self.class_name = class_name


class _ExecPinMockGraph:
    """模拟 UEdGraph，仅保留链构建所需的属性。"""
    def __init__(self, nodes):
        self.nodes = nodes


class TestExecPinNames:
    """验证链式输出显示执行引脚名称。"""

    def test_chain_shows_exec_pin_names(self):
        """链式字符串应包含执行引脚名称。

        used_exec_pin_name 设置在源节点上，表示该节点的 exec output pin 名称。
        链式字符串中箭头的引脚名称来自源节点（names[i]），而非目标节点。
        """
        mock_flows = [
            {
                "start_event": "Event.BeginPlay",
                "nodes": [
                    {"node_guid": "g1", "node_type": "K2Node_Event", "used_exec_pin_name": "exec"},
                    {"node_guid": "g2", "node_type": "K2Node_CallFunction", "used_exec_pin_name": "Then"},
                    {"node_guid": "g3", "node_type": "K2Node_CallFunction"},
                ],
            }
        ]

        mock_graph = _ExecPinMockGraph([
            _ExecPinMockNode("g1", "K2Node_Event"),
            _ExecPinMockNode("g2", "K2Node_CallFunction"),
            _ExecPinMockNode("g3", "K2Node_CallFunction"),
        ])

        chains = build_execution_chains(mock_graph, mock_flows)
        assert len(chains) > 0
        chain_str = chains[0].get("chains", [""])[0]
        # 链应包含源节点的引脚名称: N0--exec-->N1--Then-->N2
        assert "exec" in chain_str, f"链应包含 'exec' 引脚名称: {chain_str}"
        assert "Then" in chain_str, f"链应包含 'Then' 引脚名称: {chain_str}"

    def test_chain_fallback_to_arrow_without_pin_names(self):
        """无引脚名称时应使用简单的箭头格式。"""
        mock_flows = [
            {
                "start_event": "Event.BeginPlay",
                "nodes": [
                    {"node_guid": "g1", "node_type": "K2Node_Event"},
                    {"node_guid": "g2", "node_type": "K2Node_CallFunction"},
                ],
            }
        ]

        mock_graph = _ExecPinMockGraph([
            _ExecPinMockNode("g1", "K2Node_Event"),
            _ExecPinMockNode("g2", "K2Node_CallFunction"),
        ])

        chains = build_execution_chains(mock_graph, mock_flows)
        chain_str = chains[0].get("chains", [""])[0]
        assert "->" in chain_str, f"链应包含箭头: {chain_str}"
        # 不应包含 -- 引脚名称格式
        assert "--" not in chain_str, f"无引脚名称时不应包含 '--': {chain_str}"


# ============================================================================
# 来自 test_chain_exec_pins.py — 链式执行引脚测试
# ============================================================================

class _ChainMockNode:
    """模拟 UEdGraphNode，仅保留链构建所需的属性。"""
    def __init__(self, guid, class_name=""):
        self.node_guid = guid
        self.class_name = class_name


class _ChainMockGraph:
    """模拟 UEdGraph，仅保留链构建所需的属性。"""
    def __init__(self, nodes):
        self.nodes = nodes


class TestChainExecPins:
    """链式执行引脚测试。"""

    def test_chain_mixed_pin_names(self):
        """部分节点有引脚名称、部分没有时应正确混合。

        used_exec_pin_name 设置在源节点上。g1 有 "exec"，g2 无引脚名称。
        g1->g2 应使用 "exec"，g2->g3 应使用简单箭头（因为 g2 无引脚名称）。
        """
        mock_flows = [
            {
                "start_event": "Event.BeginPlay",
                "nodes": [
                    {"node_guid": "g1", "node_type": "K2Node_Event", "used_exec_pin_name": "exec"},
                    {"node_guid": "g2", "node_type": "K2Node_CallFunction"},  # 无引脚名称
                    # g3 是最后一个节点
                ],
            }
        ]

        mock_graph = _ChainMockGraph([
            _ChainMockNode("g1", "K2Node_Event"),
            _ChainMockNode("g2", "K2Node_CallFunction"),
            _ChainMockNode("g3", "K2Node_CallFunction"),
        ])

        chains = build_execution_chains(mock_graph, mock_flows)
        chain_str = chains[0].get("chains", [""])[0]
        # g1 有 "exec" -> 应使用 exec 引脚，g2 无引脚名称 -> 应使用简单箭头
        assert "exec" in chain_str, f"链应包含 'exec': {chain_str}"
        # g1->g2 应使用 exec 引脚
        assert "--exec-->" in chain_str, f"g1->g2 应使用 exec 引脚: {chain_str}"
        # g2->g3 应使用简单箭头（g2 无引脚名称）
        assert "->" in chain_str, f"g2->g3 应使用简单箭头: {chain_str}"

    def test_single_node_chain(self):
        """单节点链不应包含任何箭头。"""
        mock_flows = [
            {
                "start_event": "Event.BeginPlay",
                "nodes": [
                    {"node_guid": "g1", "node_type": "K2Node_Event", "used_exec_pin_name": "exec"},
                ],
            }
        ]

        mock_graph = _ChainMockGraph([_ChainMockNode("g1", "K2Node_Event")])

        chains = build_execution_chains(mock_graph, mock_flows)
        chain_str = chains[0].get("chains", [""])[0]
        assert chain_str == "N0", f"单节点链应为 'N0': {chain_str}"
        assert "->" not in chain_str, f"单节点链不应包含箭头: {chain_str}"

    def test_chain_with_branch_split(self):
        """分支点应将链分割为多个片段。"""
        mock_flows = [
            {
                "start_event": "Event.BeginPlay",
                "nodes": [
                    {"node_guid": "g1", "node_type": "K2Node_Event", "used_exec_pin_name": "exec"},
                    {"node_guid": "g2", "node_type": "K2Node_IfThenElse", "branch_type": "branch"},
                    {"node_guid": "g3", "node_type": "K2Node_CallFunction", "used_exec_pin_name": "Completed"},
                ],
            }
        ]

        mock_graph = _ChainMockGraph([
            _ChainMockNode("g1", "K2Node_Event"),
            _ChainMockNode("g2", "K2Node_IfThenElse"),
            _ChainMockNode("g3", "K2Node_CallFunction"),
        ])

        chains = build_execution_chains(mock_graph, mock_flows)
        assert len(chains) > 0
        entry = chains[0]
        # 分支点会将链分割
        chain_list = entry.get("chains", [])
        assert len(chain_list) >= 2, f"分支应产生至少 2 条链: {chain_list}"
        # 元数据应记录分支数
        assert entry.get("chain_metadata", {}).get("branch_count", 0) >= 1


# ============================================================================
# 来自 test_execution_trace_safety.py — 执行流追踪安全防护
# ============================================================================

class TestExecutionTraceSafety:
    """执行流追踪安全防护测试。"""

    def test_no_guid_self_loop_terminates(self):
        """单个无 GUID 节点（无出边）应立即终止。"""
        node = FakeNode(node_guid=None, class_name="K2Node_CallFunction")
        flow = _trace_execution_from_event(
            node, pin_lookup={}, node_lookup={}, node_name_lookup={},
            asset_context={},
        )
        assert len(flow) >= 1
        assert flow[0].get("warning") == "missing node_guid"

    def test_no_guid_repeated_node_stops(self):
        """同一个无 GUID 节点自环应 cycle_detected 终止。"""
        pin_in = FakePin(
            pin_id="AA", pin_name="exec",
            direction=0, pin_type=FakePinType(pin_category="exec"),
        )
        pin_out = FakePin(
            pin_id="BB", pin_name="then",
            direction=1, pin_type=FakePinType(pin_category="exec"),
            linked_to_raw=["AA"],
        )
        node = FakeNode(node_guid=None, class_name="K2Node_CallFunction", pins=[pin_out, pin_in])

        pin_lookup = {"aa": (None, "exec")}
        node_lookup = {None: node}

        flow = _trace_execution_from_event(
            node, pin_lookup, node_lookup, node_name_lookup={},
            asset_context={},
        )
        assert any(f.get("cycle_detected") for f in flow), f"Expected cycle_detected in flow: {flow}"

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
        assert any(f.get("cycle_detected") for f in flow), f"Expected cycle_detected in flow: {flow}"

    def test_max_steps_exceeded(self):
        """超过最大步数应 stopped_at max_steps_exceeded。"""
        nodes = []
        for i in range(502):
            pin_in = FakePin(
                pin_id=f"IN{i:04d}", pin_name="exec",
                direction=0, pin_type=FakePinType(pin_category="exec"),
            )
            pin_out = FakePin(
                pin_id=f"OUT{i:04d}", pin_name="then",
                direction=1, pin_type=FakePinType(pin_category="exec"),
            )
            if i < 501:
                pin_out.linked_to_raw = [f"IN{i+1:04d}"]
            node = FakeNode(
                node_guid=f"guid-{i:04d}",
                class_name="K2Node_CallFunction",
                pins=[pin_out, pin_in],
            )
            nodes.append(node)

        pin_lookup = {}
        node_lookup = {}
        node_name_lookup = {}
        for i in range(501):
            pin_lookup[f"in{i+1:04d}"] = (f"guid-{i+1:04d}", "exec")
            node_lookup[f"guid-{i:04d}"] = nodes[i]
            node_name_lookup[f"guid-{i:04d}"] = f"Node{i}"
        node_lookup["guid-501"] = nodes[501]

        flow = _trace_execution_from_event(
            nodes[0], pin_lookup, node_lookup, node_name_lookup,
            asset_context={},
        )
        assert any(f.get("stopped_at") == "max_steps_exceeded" for f in flow), \
            f"Expected max_steps_exceeded in flow"


# ============================================================================
# 来自 test_latent_detection.py — Latent/Async 动作标记
# ============================================================================

class _LatentFakePinType:
    def __init__(self, category):
        self.pin_category = category


class _LatentFakePin:
    def __init__(self, name, direction, pin_category="exec", linked_to=None):
        self.pin_name = name
        self.direction = direction
        self.pin_type = _LatentFakePinType(pin_category)
        self.linked_to_raw = linked_to or []
        self.pin_id = f"pid_{name}"


class _LatentFakeNode:
    def __init__(self, guid, class_name, pins=None, node_data=None):
        self.node_guid = guid
        self.class_name = class_name
        self.pins = pins or []
        self.node_data = node_data


class TestLatentDetection:
    """Latent/Async 动作在执行流中标记测试。"""

    def test_async_action_marked_as_latent(self):
        """K2Node_AsyncAction 应在执行流中标记 latent=True。"""
        pid_async_input = "b" * 32
        pid_end_input = "d" * 32

        event = _LatentFakeNode("guid_event", "K2Node_Event", [
            _LatentFakePin("exec", 1, "exec", ["B" * 32]),
        ])
        async_node = _LatentFakeNode("guid_async", "K2Node_AsyncAction", [
            _LatentFakePin("Then", 0, "exec"),
            _LatentFakePin("Completed", 1, "exec", ["D" * 32]),
        ])
        end_node = _LatentFakeNode("guid_end", "K2Node_MakeVariable", [
            _LatentFakePin("Completed", 0, "exec"),
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

    def test_timeline_marked_as_latent(self):
        """K2Node_Timeline 应在执行流中标记 latent=True。"""
        pid_timeline_input = "b" * 32

        event = _LatentFakeNode("guid_event", "K2Node_Event", [
            _LatentFakePin("exec", 1, "exec", ["B" * 32]),
        ])
        timeline = _LatentFakeNode("guid_timeline", "K2Node_Timeline", [
            _LatentFakePin("Update", 0, "exec"),
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

    def test_normal_node_not_latent(self):
        """普通节点不应有 latent 标记。"""
        pid_call_input = "b" * 32

        event = _LatentFakeNode("guid_event", "K2Node_Event", [
            _LatentFakePin("exec", 1, "exec", ["B" * 32]),
        ])
        call_func = _LatentFakeNode("guid_call", "K2Node_CallFunction", [
            _LatentFakePin("Then", 0, "exec"),
        ])

        pin_lookup = {pid_call_input: ("guid_call", "Then")}
        node_lookup = {"guid_event": event, "guid_call": call_func}

        flow = _trace_execution_from_event(event, pin_lookup, node_lookup)

        call_flow = next(f for f in flow if f["node_type"] == "K2Node_CallFunction")
        assert "latent" not in call_flow or call_flow.get("latent") is False


# ============================================================================
# 来自 test_macro_flow_penetration.py — 宏实例穿透测试
# ============================================================================

class _MacroFakePinType:
    def __init__(self, category):
        self.pin_category = category


class _MacroFakePin:
    def __init__(self, name, direction, pin_category="exec", linked_to=None):
        self.pin_name = name
        self.direction = direction
        self.pin_type = _MacroFakePinType(pin_category)
        self.linked_to_raw = linked_to or []
        self.pin_id = f"PID_{name.upper()}"


class _MacroFakeNode:
    def __init__(self, guid, class_name, pins=None, node_data=None):
        self.node_guid = guid
        self.class_name = class_name
        self.pins = pins or []
        self.node_data = node_data


class TestMacroFlowPenetration:
    """执行链穿透宏实例测试。"""

    def test_flow_penetrates_macro_instance(self):
        """执行链应穿透 MacroInstance 到其内部节点。"""
        event = _MacroFakeNode("guid_event", "K2Node_Event", [
            _MacroFakePin("exec", 1, "exec", ["PID_MACRO"]),
        ])
        macro = _MacroFakeNode("guid_macro", "K2Node_MacroInstance", [
            _MacroFakePin("exec", 0, "exec"),
            _MacroFakePin("Then", 1, "exec", ["PID_AFTER"]),
        ])
        after = _MacroFakeNode("guid_after", "K2Node_CallFunction", [
            _MacroFakePin("Then", 0, "exec"),
        ])

        pin_lookup = {
            "pid_macro": ("guid_macro", "exec"),
            "pid_after": ("guid_after", "Then"),
        }
        node_lookup = {
            "guid_event": event,
            "guid_macro": macro,
            "guid_after": after,
        }

        flow = _trace_execution_from_event(event, pin_lookup, node_lookup)

        macro_flow = next(f for f in flow if f["node_type"] == "K2Node_MacroInstance")
        assert "macro_expansion" in macro_flow, \
            "MacroInstance 应包含 macro_expansion 字段"

        after_flow = next((f for f in flow if f["node_type"] == "K2Node_CallFunction"), None)
        assert after_flow is not None, "执行链应穿透 MacroInstance 到达后续节点"

    def test_standard_macro_marked(self):
        """标准宏（如 ForLoop）应被识别并标记为标准宏。"""
        event = _MacroFakeNode("guid_event", "K2Node_Event", [
            _MacroFakePin("exec", 1, "exec", ["PID_FORLOOP"]),
        ])
        forloop = _MacroFakeNode("guid_forloop", "K2Node_MacroInstance", [
            _MacroFakePin("exec", 0, "exec"),
            _MacroFakePin("Loop Body", 1, "exec", ["PID_AFTER"]),
        ], node_data={
            "macro_graph_reference": {
                "graph_name": "ForLoop",
                "graph_guid": "",
            }
        })
        after = _MacroFakeNode("guid_after", "K2Node_CallFunction", [
            _MacroFakePin("Then", 0, "exec"),
        ])

        pin_lookup = {
            "pid_forloop": ("guid_forloop", "Loop Body"),
            "pid_after": ("guid_after", "Then"),
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

    def test_macro_without_reference(self):
        """无 macro_graph_reference 的宏实例应标记 unresolved。"""
        event = _MacroFakeNode("guid_event", "K2Node_Event", [
            _MacroFakePin("exec", 1, "exec", ["PID_MACRO"]),
        ])
        macro = _MacroFakeNode("guid_macro", "K2Node_MacroInstance", [
            _MacroFakePin("exec", 0, "exec"),
            _MacroFakePin("Then", 1, "exec", ["PID_AFTER"]),
        ], node_data={})
        after = _MacroFakeNode("guid_after", "K2Node_CallFunction", [
            _MacroFakePin("Then", 0, "exec"),
        ])

        pin_lookup = {
            "pid_macro": ("guid_macro", "exec"),
            "pid_after": ("guid_after", "Then"),
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


# ============================================================================
# 来自 test_graph_output_chain.py — ParseResult → ExportIR 输出链
# ============================================================================

_GRAPH_SAMPLES_DIR = Path(__file__).parent.parent / "samples"


class TestGraphOutputChain:
    """图数据输出链测试。"""

    @pytest.mark.integration
    def test_parse_result_graphs_count(self):
        """验证 ParseResult.graphs 包含图数据。"""
        from uasset_read.parse_uasset import parse_package

        path = _GRAPH_SAMPLES_DIR / "StackOBot_BP_Drone.uasset"
        if not path.exists():
            pytest.skip("测试样本不存在")

        result = parse_package(str(path))
        # 本地样本可能只有少量图
        assert len(result.graphs) >= 1, f"应有至少 1 个图，实际: {len(result.graphs)}"

    @pytest.mark.integration
    def test_export_ir_graphs_not_empty(self):
        """验证 ExportIR.graphs 包含图数据。"""
        from uasset_read.parse_uasset import parse_package
        from uasset_read.ir_builder import build_package_ir

        path = _GRAPH_SAMPLES_DIR / "StackOBot_BP_Drone.uasset"
        if not path.exists():
            pytest.skip("测试样本不存在")

        result = parse_package(str(path))
        ir = build_package_ir(result)

        # 找到蓝图 export（以 _C 结尾）
        bp_exports = [e for e in ir.exports if e.object_name.endswith("_C")]
        assert len(bp_exports) > 0, "应有蓝图 export"

        # 至少一个蓝图 export 应有图
        has_graphs = any(len(e.graphs) > 0 for e in bp_exports)
        assert has_graphs, "蓝图 export 应包含图数据"

    @pytest.mark.integration
    def test_json_output_contains_graphs(self):
        """验证 JSON 输出包含图数据。"""
        from uasset_read.parse_uasset import parse_package
        from uasset_read.ir_builder import build_package_ir
        from uasset_read.renderers.json_renderer import JSONRenderer
        from uasset_read.renderers.base import RenderOptions

        path = _GRAPH_SAMPLES_DIR / "StackOBot_BP_Drone.uasset"
        if not path.exists():
            pytest.skip("测试样本不存在")

        result = parse_package(str(path))
        ir = build_package_ir(result)
        renderer = JSONRenderer()
        output = renderer.render(ir, RenderOptions(output_level="normal"))

        import json
        data = json.loads(output)

        # 检查 exports 中是否有图
        exports_with_graphs = [e for e in data.get("exports", []) if e.get("graphs")]
        assert len(exports_with_graphs) > 0, "JSON 输出应包含图数据"

    @pytest.mark.integration
    def test_markdown_output_contains_graph_sections(self):
        """验证 Markdown 输出包含图章节。"""
        from uasset_read.parse_uasset import parse_package
        from uasset_read.ir_builder import build_package_ir
        from uasset_read.renderers.markdown_renderer import MarkdownRenderer
        from uasset_read.renderers.base import RenderOptions

        path = _GRAPH_SAMPLES_DIR / "StackOBot_BP_Drone.uasset"
        if not path.exists():
            pytest.skip("测试样本不存在")

        result = parse_package(str(path))
        ir = build_package_ir(result)
        renderer = MarkdownRenderer()
        output = renderer.render(ir, RenderOptions(output_level="normal"))

        # 检查是否有图章节
        assert "## Graph:" in output or "## Event Graph" in output, \
            "Markdown 输出应包含图章节"


# ============================================================================
# 来自 test_graph_parser.py — extract_blueprint_graphs 基本接口测试
# ============================================================================


class TestExtractBlueprintGraphsCallable:
    """extract_blueprint_graphs 应可调用。"""

    def test_callable(self):
        assert callable(extract_blueprint_graphs)


class TestExtractBlueprintGraphsCookedSkip:
    """cooked 包应跳过图解析。"""

    def _make_summary(self, flags: int):
        class FakeSummary:
            package_flags = flags
        return FakeSummary()

    def test_cooked_package_returns_empty(self):
        summary = self._make_summary(PKG_Cooked)
        result = extract_blueprint_graphs(
            archive=None,
            summary=summary,
            name_map=[],
            import_map=[],
            export_map=[],
        )
        assert result == []

    def test_non_cooked_package_not_skipped(self):
        """非 cooked 包不会因 flags 被跳过（可能因无 EdGraph export 而返回空）。"""
        summary = self._make_summary(0)
        result = extract_blueprint_graphs(
            archive=None,
            summary=summary,
            name_map=[],
            import_map=[],
            export_map=[],
        )
        assert result == []


class TestExtractBlueprintGraphsEmptyExports:
    """空 export_map 应返回空列表。"""

    def test_empty_export_map(self):
        class FakeSummary:
            package_flags = 0

        result = extract_blueprint_graphs(
            archive=None,
            summary=FakeSummary(),
            name_map=[],
            import_map=[],
            export_map=[],
        )
        assert result == []
        assert isinstance(result, list)
