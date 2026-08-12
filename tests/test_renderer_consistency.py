"""Renderer consistency tests.

Verify Markdown renderer filtering behavior and IR Builder parent_class logic safety.
"""
from __future__ import annotations

import json

import pytest

from uasset_read.models.ir import (
    PackageIR,
    PackageHeaderIR,
    ExportIR,
    GraphIR,
    NodeIR,
    PinIR,
    PropertyIR,
    BlueprintIR,
    BlueprintFunctionIR,
    BlueprintEventIR,
    VariableIR,
    ExecutionChainIR,
    LinkerSummaryIR,
    DecompiledFunctionIR,
)
from uasset_read.renderers import get_renderer
from uasset_read.renderers.base import RenderOptions, is_blueprint_export
from uasset_read.renderers.markdown_renderer import MarkdownRenderer


# ---------------------------------------------------------------------------
# Helper factories
# ---------------------------------------------------------------------------

def _make_header(**kwargs) -> PackageHeaderIR:
    defaults = dict(
        package_name="/Game/BP_Test",
        package_class="/Engine/Blueprint",
        package_flags=0,
        total_export_count=1,
        total_import_count=0,
        ue_version="5.3",
    )
    defaults.update(kwargs)
    return PackageHeaderIR(**defaults)


def _make_export(**kwargs) -> ExportIR:
    defaults = dict(
        index=0,
        object_name="BP_Test_C",
        object_class="BlueprintGeneratedClass",
        serial_size=1024,
        outer_index_resolved=None,
        super_index_resolved=None,
        parent_class="/Engine/Actor",
        properties=[],
        graphs=[],
        bulk_data=None,
    )
    defaults.update(kwargs)
    return ExportIR(**defaults)


def _make_ir(**kwargs) -> PackageIR:
    defaults = dict(
        header=_make_header(),
        name_map=[],
        imports=[],
        exports=[_make_export()],
        linker=LinkerSummaryIR(has_linker=False, import_paths=[], export_paths=[]),
    )
    defaults.update(kwargs)
    return PackageIR(**defaults)


def _make_variable(name: str, **kwargs) -> VariableIR:
    defaults = dict(
        name=name,
        type="bool",
        default_value="False",
        kind="user",
    )
    defaults.update(kwargs)
    return VariableIR(**defaults)


def _make_node(node_class: str, **kwargs) -> NodeIR:
    defaults = dict(
        node_guid="aabbccdd00112233aabbccdd00112233",
        node_class=node_class,
        node_comment=None,
        pins=[],
        execution_flow=[],
    )
    defaults.update(kwargs)
    return NodeIR(**defaults)


def _make_property(name: str, **kwargs) -> PropertyIR:
    defaults = dict(
        name=name,
        type="IntProperty",
        value=0,
        array_index=-1,
        guid=None,
    )
    defaults.update(kwargs)
    return PropertyIR(**defaults)


# ---------------------------------------------------------------------------
# Editor variable filtering -- Markdown only (JSON uses semantic pipeline)
# ---------------------------------------------------------------------------

class TestEditorVariableFilterConsistency:
    """Verify Markdown renderer filters editor internal variables."""

    EDITOR_VAR_NAMES = {
        "UbergraphPages", "FunctionGraphs", "CategorySorting",
        "ImplementedInterfaces", "LastEditedDocuments", "ThumbnailInfo",
        "bLegacyNeedToPurgeSkelRefs",
    }

    def _make_ir_with_variables(self, var_names: list[str]) -> PackageIR:
        variables = [_make_variable(name) for name in var_names]
        return _make_ir(variables=variables)

    @pytest.mark.parametrize("editor_var", sorted(EDITOR_VAR_NAMES))
    def test_markdown_filters_editor_variable(self, editor_var: str):
        """Markdown renderer should filter editor internal variables."""
        ir = self._make_ir_with_variables([editor_var, "MyHealth"])
        renderer = get_renderer("markdown")
        result = renderer.render(ir, RenderOptions())
        assert editor_var not in result
        assert "MyHealth" in result

    def test_non_editor_variable_not_filtered(self):
        """Non-editor variables should not be filtered."""
        ir = self._make_ir_with_variables(["MyHealth", "AttackPower"])
        md_renderer = get_renderer("markdown")
        md_result = md_renderer.render(ir, RenderOptions())
        assert "MyHealth" in md_result
        assert "AttackPower" in md_result


# ---------------------------------------------------------------------------
# Editor node class filtering -- Markdown only
# ---------------------------------------------------------------------------

class TestEditorNodeClassFilterConsistency:
    """Verify Markdown renderer filters editor node classes."""

    def test_markdown_filters_editor_node_class_export(self):
        """Markdown renderer should filter editor node class exports."""
        normal_export = _make_export(
            index=0, object_name="BP_Test_C", object_class="BlueprintGeneratedClass",
        )
        knot_export = _make_export(
            index=1, object_name="Knot_0", object_class="K2Node_Knot",
        )
        ir = _make_ir(exports=[normal_export, knot_export])
        renderer = get_renderer("markdown")
        result = renderer.render(ir, RenderOptions())
        assert "K2Node_Knot" not in result

    def test_markdown_includes_all_graph_nodes(self):
        """Markdown renderer should include all graph nodes."""
        knot_node = _make_node("K2Node_Knot", node_guid="11111111111111111111111111111111")
        normal_node = _make_node("K2Node_CallFunction", node_guid="22222222222222222222222222222222")
        graph = GraphIR(
            graph_guid="aaa", graph_name="EventGraph", graph_class="EdGraph",
            nodes=[knot_node, normal_node], execution_chains=[],
        )
        export = _make_export(graphs=[graph])
        ir = _make_ir(exports=[export])
        renderer = get_renderer("markdown")
        result = renderer.render(ir, RenderOptions())
        assert "K2Node_Knot" in result
        assert "K2Node_CallFunction" in result


# ---------------------------------------------------------------------------
# Editor property filtering -- Markdown only
# ---------------------------------------------------------------------------

class TestEditorPropertyFilterConsistency:
    """Verify Markdown renderer filters editor layout properties."""

    EDITOR_PROPS = {
        "NodePosX", "NodePosY", "NodeWidth", "NodeHeight",
        "NodeGuid", "NodeComment", "bIsCommentBubbleVisible",
        "CommentColor", "FontSize",
        "bCommentBubbleVisible_InDetailsPanel",
        "bCommentBubblePinned", "bCommentBubbleVisible",
        "Schema", "GraphGuid", "ErrorType",
        "AdvancedPinDisplay", "MoveMode",
        "EventReference", "bOverrideFunction",
    }

    @pytest.mark.parametrize("editor_prop", sorted(EDITOR_PROPS))
    def test_markdown_filters_editor_property(self, editor_prop: str):
        """Markdown renderer should filter editor layout properties."""
        props = [_make_property(editor_prop), _make_property("Health")]
        graph = GraphIR(
            graph_guid="aaa", graph_name="EventGraph", graph_class="EdGraph",
            nodes=[], execution_chains=[],
        )
        export = _make_export(properties=props, graphs=[graph])
        ir = _make_ir(exports=[export])
        renderer = get_renderer("markdown")
        result = renderer.render(ir, RenderOptions())
        lines = result.split("\n")
        for line in lines:
            if "|" in line and editor_prop in line:
                if "Name" not in line and "Type" not in line and "Value" not in line:
                    pytest.fail(f"Editor property '{editor_prop}' should not appear in Markdown output: {line}")


# ---------------------------------------------------------------------------
# IR Builder parent_class logic safety
# ---------------------------------------------------------------------------

class TestIRBuilderParentClass:
    """Verify IR Builder only sets parent_class on blueprint exports."""

    def test_blueprint_export_gets_parent_class(self):
        """Blueprint export should inherit result.blueprint.parent_class."""
        from uasset_read.ir_builder import _build_export_ir

        bp = BlueprintIR(
            parent_class="/Engine/Actor",
            functions=[], events=[], components=[],
        )
        export = _make_export(
            object_name="BP_Test_C",
            object_class="BlueprintGeneratedClass",
        )

        class MockResult:
            blueprint = bp
            import_map = []
            export_map = []
            linker = None
        result = MockResult()
        result.blueprint = bp
        result.import_map = []
        result.export_map = []
        result.linker = None

        export_ir = _build_export_ir(0, export, result)
        assert export_ir.parent_class == "/Engine/Actor"

    def test_non_blueprint_export_no_parent_class(self):
        """Non-blueprint export should not inherit result.blueprint.parent_class."""
        from uasset_read.ir_builder import _build_export_ir

        bp = BlueprintIR(
            parent_class="/Engine/Actor",
            functions=[], events=[], components=[],
        )
        export = _make_export(
            object_name="SM_Chair",
            object_class="StaticMesh",
        )

        class MockResult:
            blueprint = bp
            import_map = []
            export_map = []
            linker = None
        result = MockResult()
        result.blueprint = bp
        result.import_map = []
        result.export_map = []
        result.linker = None

        export_ir = _build_export_ir(0, export, result)
        assert export_ir.parent_class is None

    def test_no_blueprint_no_parent_class(self):
        """Without blueprint data, any export's parent_class should be None."""
        from uasset_read.ir_builder import _build_export_ir

        export = _make_export(
            object_name="BP_Test_C",
            object_class="BlueprintGeneratedClass",
        )

        class MockResult:
            blueprint = None
            import_map = []
            export_map = []
            linker = None
        result = MockResult()
        result.blueprint = None
        result.import_map = []
        result.export_map = []
        result.linker = None

        export_ir = _build_export_ir(0, export, result)
        assert export_ir.parent_class is None

    def test_graph_having_export_gets_parent_class(self):
        """Export with graphs should be treated as blueprint export and inherit parent_class."""
        from uasset_read.ir_builder import _build_export_ir

        bp = BlueprintIR(
            parent_class="/Engine/Actor",
            functions=[], events=[], components=[],
        )
        graph = GraphIR(
            graph_guid="aaa", graph_name="EventGraph", graph_class="EdGraph",
            nodes=[], execution_chains=[],
        )
        export = _make_export(
            object_name="BP_GraphExport",
            object_class="SomeClass",
            graphs=[graph],
        )

        class MockResult:
            blueprint = bp
            import_map = []
            export_map = []
            linker = None
        result = MockResult()
        result.blueprint = bp
        result.import_map = []
        result.export_map = []
        result.linker = None

        export_ir = _build_export_ir(0, export, result)
        assert export_ir.parent_class == "/Engine/Actor"
