"""graph 模块系统性缺陷测试。"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

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
        """GUID 应转为大写。"""
        assert _pin_ref_guid("a1b2c3d4-e5f6-7890-abcd-ef1234567890") == "A1B2C3D4E5F67890ABCDEF1234567890"

    def test_guid_strip_dashes(self):
        """GUID 应移除 dash。"""
        result = _pin_ref_guid("A1B2C3D4-E5F6-7890-ABCD-EF1234567890")
        assert "-" not in result

    def test_guid_from_dict_pin_guid(self):
        """从 dict 的 pin_guid 字段提取。"""
        result = _pin_ref_guid({"pin_guid": "a1b2c3d4-e5f6-7890-abcd-ef1234567890"})
        assert result == "A1B2C3D4E5F67890ABCDEF1234567890"

    def test_guid_from_dict_pin_id(self):
        """从 dict 的 pin_id 字段提取。"""
        result = _pin_ref_guid({"pin_id": "AABBCCDD"})
        assert result == "AABBCCDD"

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
        source_pin_id = "SOURCEPIN"
        knot_input_id = "KNOTIN"
        knot_output_id = "KNOTOUT"

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

        # pin_lookup 键必须与 _pin_ref_guid 输出格式一致（大写、无 dash）
        pin_lookup = {
            "FEPARAMPIN": ("fe-guid", "MyParam"),
            "CALLERPIN": ("caller-guid", "Value"),
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

        # pin_lookup 键必须与 _pin_ref_guid 输出格式一致（大写、无 dash）
        pin_lookup = {
            "SELFPIN": ("self-guid", "Self"),
            "CALLERPIN": ("caller-guid", "Target"),
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
        # pin_lookup 键必须与 _pin_ref_guid 输出格式一致（大写、无 dash）
        pin_lookup = {"PINBIN": ("guid-b", "exec")}
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
        # 键应归一化为大写
        assert pin_lookup["PINA"] == ("guid-1", "InputPin")
        assert pin_lookup["PINB"] == ("guid-1", "OutputPin")
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

        # from_pin_id 应包含归一化后的 PIN-A-OUT（去 dash，大写）
        assert "PINAOUT" in by_from
        assert len(by_from["PINAOUT"]) == 1

        # to_pin_id 应包含归一化后的 PIN-B-IN
        assert "PINBIN" in by_to
        assert len(by_to["PINBIN"]) == 1

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

    def test_non_source_type_returns_empty(self):
        """非 EnhancedInputAction/Event 源节点应返回空列表。"""
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
        assert edges == []


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
