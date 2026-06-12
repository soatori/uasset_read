"""渲染器测试。"""
import json

import pytest

from uasset_read.models.ir import (
    ExportIR,
    GraphIR,
    LinkerSummaryIR,
    NodeIR,
    PackageHeaderIR,
    PackageIR,
    PinIR,
    PropertyIR,
)
from uasset_read.renderers import RENDERER_REGISTRY, get_renderer, list_formats
from uasset_read.renderers.base import IRenderer, RenderOptions


class TestRenderOptions:
    def test_defaults(self):
        opts = RenderOptions()
        assert opts.verbose is False
        assert opts.indent == 2
        assert opts.include_schema is False

    def test_custom(self):
        opts = RenderOptions(verbose=True, indent=4, include_function_graphs=True)
        assert opts.verbose is True
        assert opts.indent == 4


class TestRendererRegistry:
    def test_get_renderer_json(self):
        renderer = get_renderer("json")
        assert renderer.format_name == "json"

    def test_get_renderer_markdown(self):
        renderer = get_renderer("markdown")
        assert renderer.format_name == "markdown"

    def test_get_renderer_unknown(self):
        with pytest.raises(ValueError, match="Unknown render format"):
            get_renderer("nonexistent")

    def test_list_formats_only_public_release_formats(self):
        assert list_formats() == ["json", "markdown"]

    def test_duplicate_registration_raises(self):
        from uasset_read.renderers import register_renderer

        class _TestRenderer(IRenderer):
            def render(self, ir, options):
                return ""

            @property
            def format_name(self):
                return "_test_dup"

        register_renderer("_test_dup", _TestRenderer)
        with pytest.raises(ValueError, match="already registered"):
            register_renderer("_test_dup", _TestRenderer)
        RENDERER_REGISTRY.pop("_test_dup", None)


class TestJSONRenderer:
    def test_render_minimal_ir(self):
        header = PackageHeaderIR(
            package_name="/Game/Test",
            package_class="Test_C",
            package_flags=0,
            total_export_count=0,
            total_import_count=0,
            ue_version="5.x",
        )
        ir = PackageIR(header=header, name_map=["Test"], imports=[], exports=[], linker=None)

        output = get_renderer("json").render(ir, RenderOptions())

        data = json.loads(output)
        assert data["status"]["status"] == "success"
        assert data["summary"]["package_name"] == "/Game/Test"
        assert "blueprint" not in data

    def test_render_with_exports(self):
        header = PackageHeaderIR(
            package_name="/Game/TestBP",
            package_class="TestBP_C",
            package_flags=0,
            total_export_count=1,
            total_import_count=2,
            ue_version="5.3",
        )
        prop = PropertyIR(name="Health", type="FloatProperty", value=100.0, array_index=0, guid=None)
        pin = PinIR(
            pin_name="Exec",
            pin_type="exec",
            pin_type_value=None,
            linked_to=["abcd12345678"],
            direction=1,
            default_value=None,
        )
        node = NodeIR(
            node_guid="abcd1234567890abcdef1234567890ab",
            node_class="K2Node_CallFunction",
            node_comment="Set Health",
            pins=[pin],
            execution_flow=[],
        )
        graph = GraphIR(
            graph_guid="guid0001",
            graph_name="EventGraph",
            graph_class="EdGraph",
            nodes=[node],
            execution_chains=[["N1", "N2"]],
        )
        export = ExportIR(
            index=0,
            object_name="Default__TestBP_C",
            object_class="BlueprintGeneratedClass",
            serial_size=1024,
            outer_index_resolved=None,
            super_index_resolved=None,
            parent_class="Actor",
            properties=[prop],
            graphs=[graph],
            bulk_data=None,
        )
        linker = LinkerSummaryIR(has_linker=True, import_paths=["/Engine/Core"], export_paths=["/Game/TestBP"])
        ir = PackageIR(header=header, name_map=["TestBP", "Health"], imports=[], exports=[export], linker=linker)

        output = get_renderer("json").render(ir, RenderOptions(include_function_graphs=True))

        data = json.loads(output)
        assert data["summary"]["package_name"] == "/Game/TestBP"
        assert len(data["exports"]) == 1
        assert data["exports"][0]["object_name"] == "Default__TestBP_C"
        assert len(data["exports"][0]["graphs"]) == 1
        assert "function_graphs" in data


class TestMarkdownRenderer:
    def test_render_minimal_ir(self):
        header = PackageHeaderIR(
            package_name="/Game/Test",
            package_class="Test_C",
            package_flags=0,
            total_export_count=0,
            total_import_count=0,
            ue_version="5.x",
        )
        ir = PackageIR(header=header, name_map=["Test"], imports=[], exports=[], linker=None)

        output = get_renderer("markdown").render(ir, RenderOptions())

        assert "# Test" in output
        assert "| Class |" in output
        assert "| Package |" in output

    def test_render_with_mermaid(self):
        pin = PinIR(
            pin_name="Exec",
            pin_type="exec",
            pin_type_value=None,
            linked_to=["target1234"],
            direction=1,
            default_value=None,
        )
        node = NodeIR(
            node_guid="abcd1234567890abcdef1234567890ab",
            node_class="K2Node_Event",
            node_comment="BeginPlay",
            pins=[pin],
            execution_flow=[],
        )
        graph = GraphIR(
            graph_guid="guid0001",
            graph_name="EventGraph",
            graph_class="EdGraph",
            nodes=[node],
            execution_chains=[],
        )
        export = ExportIR(
            index=0,
            object_name="Default__TestBP_C",
            object_class="BlueprintGeneratedClass",
            serial_size=1024,
            outer_index_resolved=None,
            super_index_resolved=None,
            parent_class=None,
            properties=[],
            graphs=[graph],
            bulk_data=None,
        )
        header = PackageHeaderIR(
            package_name="/Game/TestBP",
            package_class="TestBP_C",
            package_flags=0,
            total_export_count=1,
            total_import_count=0,
            ue_version="5.3",
        )
        ir = PackageIR(header=header, name_map=["TestBP"], imports=[], exports=[export], linker=None)

        output = get_renderer("markdown").render(ir, RenderOptions())

        assert "EventGraph" in output
        assert "```mermaid" in output
        assert "graph TD" in output
        assert "BeginPlay" in output
