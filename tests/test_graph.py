"""Consolidated graph module tests.

Merged from:
- tests/graph/test_macro_expander.py
- tests/graph/test_subgraphs_and_fixes.py
- tests/graph/test_execution_trace_safety.py
- tests/test_graph_parser.py
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any

import pytest

from uasset_read.models.core import UEdGraph, UEdGraphNode, UEdGraphPin, FEdGraphPinType


# ============================================================================
# Shared fixtures
# ============================================================================

def _make_pin(
    pin_id: str,
    pin_name: str,
    direction: int = 0,
    category: str = "float",
    linked_to: Optional[List[dict]] = None,
    parent_pin=None,
    default_value: str = "",
) -> UEdGraphPin:
    return UEdGraphPin(
        pin_id=pin_id,
        pin_name=pin_name,
        direction=direction,
        pin_type=FEdGraphPinType(pin_category=category) if category else None,
        linked_to_raw=linked_to or [],
        parent_pin=parent_pin,
        default_value=default_value or None,
    )


def _make_node(
    guid: str,
    class_name: str = "K2Node_CallFunction",
    pins: Optional[List[UEdGraphPin]] = None,
    node_data: Optional[Dict[str, Any]] = None,
) -> UEdGraphNode:
    return UEdGraphNode(
        node_guid=guid,
        class_name=class_name,
        pins=pins or [],
        node_data=node_data,
    )


def _make_graph(
    name: str = "TestGraph",
    guid: str = "",
    nodes: Optional[List[UEdGraphNode]] = None,
    subgraphs: Optional[List[UEdGraph]] = None,
    graph_class: str = "EdGraph",
) -> UEdGraph:
    return UEdGraph(
        graph_name=name,
        graph_class=graph_class,
        graph_guid=guid or None,
        nodes=nodes or [],
        subgraphs=subgraphs or [],
    )


# ============================================================================
# Macro expander tests
# ============================================================================

class TestMacroExpander:
    """Macro expander core functionality."""

    def test_standard_macros_recognized(self):
        """Standard macros should be recognized and not attempt internal expansion."""
        from uasset_read.graph.macro_expander import MacroExpander, STANDARD_MACROS

        ctx = {"graphs": []}
        expander = MacroExpander(ctx)
        instance = {
            "macro_graph_reference": {
                "graph_name": "ForLoop",
                "graph_guid": "",
            }
        }
        expansion = expander.expand_macro_instance(instance)
        assert expansion.context.macro_name == "ForLoop"
        assert expansion.context.macro_name in STANDARD_MACROS


# ============================================================================
# Subgraphs tests
# ============================================================================

class TestSubgraphs:
    """SubGraphs parsing support."""

    def test_subgraphs_field_populated(self):
        """UEdGraph.subgraphs should be correctly assigned."""
        child_graph = _make_graph(name="ChildGraph")
        parent_graph = _make_graph(name="ParentGraph", subgraphs=[child_graph])

        assert len(parent_graph.subgraphs) == 1
        assert parent_graph.subgraphs[0].graph_name == "ChildGraph"


# ============================================================================
# Graph cycle detection tests
# ============================================================================

class TestGraphCycleDetection:
    """DFS cycle detection in execution chains."""

    def test_simple_cycle(self):
        """Simple cycle: A -> B -> A should be detected."""
        from uasset_read.graph.chain_builder import _detect_cycle

        adj = {"A": ["B"], "B": ["A"]}
        assert _detect_cycle(adj) is True


# ============================================================================
# Execution trace safety tests
# ============================================================================

class TestExecutionTraceSafety:
    """Execution trace should terminate safely on pathological inputs."""

    @dataclass
    class FakePinType:
        pin_category: str = ""

    @dataclass
    class FakePin:
        pin_id: str = ""
        pin_name: str = ""
        direction: int = 0
        pin_type: Optional[Any] = None
        linked_to_raw: List[str] = field(default_factory=list)

    @dataclass
    class FakeNodeData:
        b_defaults_to_pure: bool = False

    @dataclass
    class FakeNode:
        node_guid: Optional[str] = None
        class_name: str = "K2Node_CallFunction"
        pins: List[Any] = field(default_factory=list)
        node_data: Optional[Any] = None

    def test_no_guid_self_loop_terminates(self):
        """Single node without GUID should terminate immediately."""
        from uasset_read.graph.flow_builder import _trace_execution_from_event

        node = self.FakeNode(node_guid=None, class_name="K2Node_CallFunction")
        flow = _trace_execution_from_event(
            node, pin_lookup={}, node_lookup={}, node_name_lookup={},
            asset_context={},
        )
        assert len(flow) >= 1
        assert flow[0].get("warning") == "missing node_guid"


# ============================================================================
# Graph parser tests
# ============================================================================

class TestGraphParser:
    """Graph parser basic interface and cooked asset guard."""

    def test_cooked_package_returns_empty(self):
        """Cooked packages should skip graph parsing and return empty."""
        from uasset_read.graph.parser import extract_blueprint_graphs
        from uasset_read.constants import PKG_Cooked

        class FakeSummary:
            package_flags = PKG_Cooked

        result = extract_blueprint_graphs(
            archive=None,
            summary=FakeSummary(),
            name_map=[],
            import_map=[],
            export_map=[],
        )
        assert result == []
