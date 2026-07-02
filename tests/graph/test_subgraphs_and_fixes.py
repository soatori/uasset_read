"""Tests for graph module fixes: SubGraphs, synthetic data flows, DFS cycle detection.

Issue #248: M-10, M-11, M-12
"""
from __future__ import annotations

import pytest
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field

from uasset_read.models.core import UEdGraph, UEdGraphNode, UEdGraphPin, FEdGraphPinType


# ============================================================================
# Fixtures
# ============================================================================

def _make_pin(
    pin_id: str,
    pin_name: str,
    direction: int = 0,
    category: str = "float",
    linked_to: Optional[List[dict]] = None,
) -> UEdGraphPin:
    return UEdGraphPin(
        pin_id=pin_id,
        pin_name=pin_name,
        direction=direction,
        pin_type=FEdGraphPinType(pin_category=category),
        linked_to_raw=linked_to or [],
    )


def _make_node(
    guid: str,
    class_name: str = "K2Node_CallFunction",
    x: int = 0,
    y: int = 0,
    pins: Optional[List[UEdGraphPin]] = None,
    node_data: Optional[Dict[str, Any]] = None,
) -> UEdGraphNode:
    return UEdGraphNode(
        node_guid=guid,
        node_pos_x=x,
        node_pos_y=y,
        class_name=class_name,
        pins=pins or [],
        node_data=node_data,
    )


def _make_graph(
    name: str = "TestGraph",
    class_name: str = "EdGraph",
    nodes: Optional[List[UEdGraphNode]] = None,
    subgraphs: Optional[List[UEdGraph]] = None,
) -> UEdGraph:
    return UEdGraph(
        graph_name=name,
        graph_class=class_name,
        nodes=nodes or [],
        subgraphs=subgraphs or [],
    )


# ============================================================================
# M-10: SubGraphs parsing support
# ============================================================================

class TestSubGraphsParsing:
    """验证 SubGraphs 字段在 UEdGraph 中正确维护和传递。"""

    def test_subgraphs_field_populated(self):
        """UEdGraph.subgraphs 字段可以被正确赋值。"""
        child_graph = _make_graph(name="ChildGraph")
        parent_graph = _make_graph(name="ParentGraph", subgraphs=[child_graph])

        assert len(parent_graph.subgraphs) == 1
        assert parent_graph.subgraphs[0].graph_name == "ChildGraph"

    def test_nested_subgraphs(self):
        """嵌套子图（子图的子图）正确传递。"""
        grandchild = _make_graph(name="Grandchild")
        child = _make_graph(name="Child", subgraphs=[grandchild])
        parent = _make_graph(name="Parent", subgraphs=[child])

        assert len(parent.subgraphs) == 1
        assert len(parent.subgraphs[0].subgraphs) == 1
        assert parent.subgraphs[0].subgraphs[0].graph_name == "Grandchild"

    def test_subgraphs_empty_by_default(self):
        """UEdGraph.subgraphs 默认为空列表。"""
        graph = _make_graph()
        assert graph.subgraphs == []

    def test_ir_builder_preserves_subgraphs(self):
        """IR Builder 正确传递 subgraphs 到 GraphIR。"""
        from uasset_read.ir_builder import _build_graph_ir

        child = _make_graph(name="Child")
        parent = _make_graph(name="Parent", subgraphs=[child])

        ir = _build_graph_ir(parent)
        assert len(ir.subgraphs) == 1
        assert ir.subgraphs[0].graph_name == "Child"

    def test_subgraphs_with_mixed_sources(self):
        """SubGraphs 数组和 AnimGraphNode 引用的子图可以合并。"""
        graph_a = _make_graph(name="GraphA")
        graph_b = _make_graph(name="GraphB")
        parent = _make_graph(name="Parent", subgraphs=[graph_a, graph_b])

        names = [sg.graph_name for sg in parent.subgraphs]
        assert "GraphA" in names
        assert "GraphB" in names


# ============================================================================
# M-11: Dynamic synthetic data flows (no hardcoded FirstPerson template)
# ============================================================================

class TestSyntheticDataFlows:
    """验证 _build_synthetic_function_data_flows 不再依赖硬编码模板名称。"""

    def _build_fe_node(
        self, pins_config: List[tuple]
    ) -> UEdGraphNode:
        """构建 FunctionEntry 节点。

        pins_config: [(pin_name, direction, category), ...]
        """
        pins = [
            _make_pin(f"fe_{i}", name, direction=dir, category=cat)
            for i, (name, dir, cat) in enumerate(pins_config)
        ]
        return _make_node(
            guid="fe_guid_001",
            class_name="K2Node_FunctionEntry",
            pins=pins,
            node_data={"function_reference": {"member_name": "TestFunc"}},
        )

    def _build_call_node(
        self,
        func_name: str,
        input_pins: List[str],
        output_pins: List[str],
        linked_inputs: Optional[Dict[str, str]] = None,
    ) -> UEdGraphNode:
        """构建 CallFunction 节点。

        linked_inputs: {pin_name: "some_pin_id"} 表示已连接的输入 pin
        """
        pins = []
        linked_inputs = linked_inputs or {}
        for i, name in enumerate(input_pins):
            linked = [{"pin_guid": "dummy"}] if name in linked_inputs else []
            pins.append(_make_pin(f"cf_in_{i}", name, direction=0, category="float", linked_to=linked))
        for i, name in enumerate(output_pins):
            pins.append(_make_pin(f"cf_out_{i}", name, direction=1, category="float"))
        return _make_node(
            guid=f"cf_guid_{func_name}",
            class_name="K2Node_CallFunction",
            pins=pins,
            node_data={"function_reference": {"member_name": func_name}},
        )

    def test_dynamic_detection_no_hardcoded_name(self):
        """任何图名都应该被处理，不仅限于 Move/Aim。"""
        from uasset_read.graph.flow_builder import _build_synthetic_function_data_flows

        fe = self._build_fe_node([
            ("ReturnValue", 1, "float"),
            ("ReturnValue2", 1, "float"),
        ])
        cf = self._build_call_node(
            "CustomFunction",
            input_pins=["ReturnValue", "ReturnValue2"],
            output_pins=["Result"],
        )
        graph = _make_graph(name="AnyCustomName", nodes=[fe, cf])

        node_name_lookup = {fe.node_guid: "FE", cf.node_guid: "CF"}
        flows = _build_synthetic_function_data_flows(graph, node_name_lookup, "name")

        # 应该检测到参数匹配
        assert len(flows) == 2

    def test_no_flows_without_function_entry(self):
        """没有 FunctionEntry 节点时返回空。"""
        from uasset_read.graph.flow_builder import _build_synthetic_function_data_flows

        cf = self._build_call_node("SomeFunc", input_pins=["Param"], output_pins=[])
        graph = _make_graph(name="NoFE", nodes=[cf])

        flows = _build_synthetic_function_data_flows(graph, {}, "name")
        assert flows == []

    def test_no_flows_without_matching_pins(self):
        """FunctionEntry 输出参数与 CallFunction 输入参数无匹配时返回空。"""
        from uasset_read.graph.flow_builder import _build_synthetic_function_data_flows

        fe = self._build_fe_node([
            ("UniqueParam", 1, "float"),
        ])
        cf = self._build_call_node(
            "OtherFunc",
            input_pins=["DifferentParam"],
            output_pins=[],
        )
        graph = _make_graph(name="NoMatch", nodes=[fe, cf])

        node_name_lookup = {fe.node_guid: "FE", cf.node_guid: "CF"}
        flows = _build_synthetic_function_data_flows(graph, node_name_lookup, "name")
        assert flows == []

    def test_already_connected_pins_excluded(self):
        """已连接的输入 pin 不应被补充。"""
        from uasset_read.graph.flow_builder import _build_synthetic_function_data_flows

        fe = self._build_fe_node([
            ("Param", 1, "float"),
        ])
        cf = self._build_call_node(
            "Func",
            input_pins=["Param"],
            output_pins=[],
            linked_inputs={"Param": "some_existing_link"},
        )
        graph = _make_graph(name="Connected", nodes=[fe, cf])

        node_name_lookup = {fe.node_guid: "FE", cf.node_guid: "CF"}
        flows = _build_synthetic_function_data_flows(graph, node_name_lookup, "name")
        assert flows == []


# ============================================================================
# M-12: _detect_cycle DFS neighbor handling
# ============================================================================

class TestDetectCycle:
    """验证 _detect_cycle 正确处理所有节点（包括仅作为 target 出现的节点）。"""

    def test_simple_cycle(self):
        """简单环检测: A -> B -> A。"""
        from uasset_read.graph.chain_builder import _detect_cycle

        adj = {"A": ["B"], "B": ["A"]}
        assert _detect_cycle(adj) is True

    def test_linear_no_cycle(self):
        """线性链无环: A -> B -> C。"""
        from uasset_read.graph.chain_builder import _detect_cycle

        adj = {"A": ["B"], "B": ["C"]}
        assert _detect_cycle(adj) is False

    def test_target_only_node_in_cycle(self):
        """仅作为 target 出现的节点参与环检测。

        旧实现会跳过不在 adjacency keys 中的节点，导致此场景漏检。
        """
        from uasset_read.graph.chain_builder import _detect_cycle

        # C 只作为 target 出现（不在 adjacency keys 中）
        # 但存在环: A -> C -> A
        adj = {"A": ["C"], "C": ["A"]}
        assert _detect_cycle(adj) is True

    def test_target_only_node_no_cycle(self):
        """仅作为 target 出现的节点，无环。"""
        from uasset_read.graph.chain_builder import _detect_cycle

        adj = {"A": ["B"], "B": ["C"], "C": []}
        assert _detect_cycle(adj) is False

    def test_complex_dag_no_cycle(self):
        """复杂 DAG 无环: A -> B -> D, A -> C -> D。"""
        from uasset_read.graph.chain_builder import _detect_cycle

        adj = {"A": ["B", "C"], "B": ["D"], "C": ["D"], "D": []}
        assert _detect_cycle(adj) is False

    def test_three_node_cycle(self):
        """三节点环: A -> B -> C -> A。"""
        from uasset_read.graph.chain_builder import _detect_cycle

        adj = {"A": ["B"], "B": ["C"], "C": ["A"]}
        assert _detect_cycle(adj) is True

    def test_empty_adjacency(self):
        """空邻接表。"""
        from uasset_read.graph.chain_builder import _detect_cycle

        assert _detect_cycle({}) is False

    def test_single_node_no_self_loop(self):
        """单节点无自环。"""
        from uasset_read.graph.chain_builder import _detect_cycle

        adj = {"A": []}
        assert _detect_cycle(adj) is False

    def test_disconnected_components(self):
        """不连通分量，其中一个有环。"""
        from uasset_read.graph.chain_builder import _detect_cycle

        adj = {
            "A": ["B"],  # 无环
            "B": [],
            "X": ["Y"],  # 有环
            "Y": ["X"],
        }
        assert _detect_cycle(adj) is True

    def test_target_only_longer_cycle(self):
        """更长的环中包含仅作为 target 的节点: A -> B -> C -> A, 其中 C 只有入边。"""
        from uasset_read.graph.chain_builder import _detect_cycle

        adj = {"A": ["B"], "B": ["C"]}
        # C 只作为 target，但不存在环
        assert _detect_cycle(adj) is False

        # 加入环
        adj_with_cycle = {"A": ["B"], "B": ["C"], "C": ["A"]}
        assert _detect_cycle(adj_with_cycle) is True
