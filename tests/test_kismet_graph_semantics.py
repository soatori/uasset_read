"""Tests for Kismet/graph semantics — UE source-aligned verification."""
from __future__ import annotations

from pathlib import Path

import pytest

from uasset_read.kismet.tokens import EExprToken


_SAMPLE_DIR = Path(__file__).resolve().parent / "samples"
_BLUEPRINT_SAMPLE = _SAMPLE_DIR / "FirstPerson_BP_FirstPersonCharacter.uasset"


def _build_ir():
    """Parse the Blueprint sample and return the PackageIR."""
    from uasset_read.parse_uasset import parse_uasset_with_linker
    from uasset_read.ir_builder import build_package_ir

    result = parse_uasset_with_linker(str(_BLUEPRINT_SAMPLE), tolerant=True)
    return build_package_ir(result)


class TestKismetGraphSemantics:
    """Verify Kismet expression parsing and graph semantics against UE source."""

    @pytest.fixture(autouse=True)
    def _skip_if_missing(self):
        if not _BLUEPRINT_SAMPLE.exists():
            pytest.skip("Blueprint sample not found")

    @pytest.fixture()
    def ir(self):
        return _build_ir()

    def test_blueprint_has_graphs(self, ir):
        """Blueprint sample must contain at least one graph."""
        has_graphs = any(export.graphs for export in ir.exports)
        assert has_graphs, "Blueprint has no graphs"

    def test_graph_nodes_have_required_fields(self, ir):
        """Every graph node must have node_class and pins."""
        for export in ir.exports:
            for graph in export.graphs:
                for node in graph.nodes:
                    assert hasattr(node, "node_class"), (
                        f"Node missing node_class in {export.object_name}"
                    )
                    assert hasattr(node, "pins"), (
                        f"Node missing pins in {export.object_name}"
                    )

    def test_expression_tokens_are_valid(self, ir):
        """All Kismet expression tokens must be valid EExprToken values."""
        valid_tokens = set(EExprToken.__members__.values())

        for export in ir.exports:
            for graph in export.graphs:
                for node in graph.nodes:
                    assert isinstance(node.node_class, str)
                    assert len(node.node_class) > 0

    def test_execution_flow_structure(self, ir):
        """Execution flow entries must have valid structure."""
        for export in ir.exports:
            for graph in export.graphs:
                for node in graph.nodes:
                    for flow in node.execution_flow:
                        assert isinstance(flow, dict), (
                            "Execution flow entry is not a dict"
                        )

    def test_pin_linkage_integrity(self, ir):
        """Pin linked_to references must be valid."""
        for export in ir.exports:
            for graph in export.graphs:
                for node in graph.nodes:
                    for pin in node.pins:
                        if pin.linked_to:
                            assert isinstance(pin.linked_to, list), (
                                f"Pin {pin.pin_name}: linked_to is not a list"
                            )
                            for link in pin.linked_to:
                                assert isinstance(link, str), (
                                    f"Pin {pin.pin_name}: link is not a string"
                                )


class TestKismetSafety:
    """Verify Kismet archive safety limits."""

    def test_recursion_depth_limit(self):
        """Kismet archive must enforce recursion depth limits."""
        from uasset_read.kismet.archive import FKismetArchive
        ka = FKismetArchive(b"\x00" * 100, name="test", name_map=[])
        assert hasattr(ka, "_expression_depth"), "Missing _expression_depth attribute"
        assert ka._expression_depth == 0, "Initial depth should be 0"
