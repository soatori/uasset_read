"""Regression tests for Enhanced Input Action rendering in Markdown renderer.

Task #485: trigger_events is list[dict], not dict.
"""
import pytest
from uasset_read.models.ir import (
    BlueprintIR, ExportIR, GraphIR, NodeIR, PackageHeaderIR, PackageIR, PinIR,
)
from uasset_read.renderers.base import RenderOptions
from uasset_read.renderers.markdown_renderer import MarkdownRenderer


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_node(
    node_class: str = "K2Node_Event",
    input_action_path: str | None = None,
    trigger_events: list[dict] | None = None,
    event_type: str | None = None,
) -> NodeIR:
    return NodeIR(
        node_guid="00000000000000000000000000000001",
        node_class=node_class,
        node_comment=None,
        pins=[],
        execution_flow=[],
        macro_expansion=None,
        input_action_path=input_action_path,
        trigger_events=trigger_events or [],
        event_type=event_type,
    )


def _make_package(*nodes: NodeIR) -> PackageIR:
    graph = GraphIR(
        graph_guid="00000000000000000000000000000002",
        graph_name="TestGraph",
        graph_class="EdGraph",
        nodes=list(nodes),
        execution_chains=[],
        graph_type=None,
    )
    export = ExportIR(
        index=0,
        object_name="TestBP",
        object_class="BlueprintGeneratedClass",
        graphs=[graph],
        serial_size=1024,
        outer_index_resolved=None,
        super_index_resolved=None,
        parent_class=None,
        properties=[],
        bulk_data=None,
    )
    header = PackageHeaderIR(
        package_name="TestPackage",
        package_class="BlueprintGeneratedClass",
        package_flags=0,
        total_export_count=1,
        total_import_count=0,
        ue_version="5.4",
    )
    return PackageIR(
        header=header,
        name_map=(),
        imports=[],
        exports=[export],
        linker=None,
        blueprint=BlueprintIR(parent_class=None),
        variables=[],
        function_graphs=[],
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestMarkdownInputActions:
    """Enhanced Input trigger_events is list[dict], not dict."""

    def test_trigger_list_with_multiple_events(self):
        """list[dict] trigger_events render each row correctly."""
        triggers = [
            {"trigger_name": "Triggered", "event_type": "Triggered"},
            {"trigger_name": "Completed", "event_type": "Completed"},
        ]
        node = _make_node(
            node_class="K2Node_EnhancedInputAction",
            input_action_path="/Game/IA_Jump",
            trigger_events=triggers,
        )
        pkg = _make_package(node)
        renderer = MarkdownRenderer()
        md = renderer.render(pkg, RenderOptions())

        assert "### Input Action Bindings" in md
        assert "/Game/IA_Jump" in md
        assert "| Triggered | Triggered |" in md
        assert "| Completed | Completed |" in md

    def test_empty_trigger_list(self):
        """Empty list renders dash placeholders."""
        node = _make_node(
            node_class="K2Node_EnhancedInputAction",
            input_action_path="/Game/IA_Sprint",
            trigger_events=[],
        )
        pkg = _make_package(node)
        renderer = MarkdownRenderer()
        md = renderer.render(pkg, RenderOptions())

        assert "/Game/IA_Sprint" in md
        assert "| — | — |" in md

    def test_single_trigger_event(self):
        """Single-item list still renders correctly."""
        triggers = [
            {"trigger_name": "Started", "event_type": "Started"},
        ]
        node = _make_node(
            node_class="K2Node_EnhancedInputAction",
            input_action_path="/Game/IA_Dash",
            trigger_events=triggers,
        )
        pkg = _make_package(node)
        renderer = MarkdownRenderer()
        md = renderer.render(pkg, RenderOptions())

        assert "| Started | Started |" in md

    def test_no_input_action_nodes(self):
        """Non-EnhancedInput nodes produce no input action table."""
        node = _make_node(node_class="K2Node_Event")
        pkg = _make_package(node)
        renderer = MarkdownRenderer()
        md = renderer.render(pkg, RenderOptions())

        assert "Input Action Bindings" not in md
