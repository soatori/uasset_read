"""渲染器测试。"""
import pytest
from uasset_read.renderers.base import RenderOptions, IRenderer
from uasset_read.renderers import get_renderer, RENDERER_REGISTRY


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
        from uasset_read.renderers.json_renderer import JSONRenderer  # noqa: F401
        r = get_renderer("json")
        assert r.format_name == "json"

    def test_get_renderer_unknown(self):
        with pytest.raises(ValueError, match="Unknown render format"):
            get_renderer("nonexistent")

    def test_list_formats(self):
        from uasset_read.renderers.json_renderer import JSONRenderer  # noqa: F401
        from uasset_read.renderers import list_formats
        fmts = list_formats()
        assert "json" in fmts

    def test_duplicate_registration_raises(self):
        from uasset_read.renderers import register_renderer
        from uasset_read.renderers.base import IRenderer

        class _TestRenderer(IRenderer):
            def render(self, ir, options): return ""
            @property
            def format_name(self): return "_test_dup"

        register_renderer("_test_dup", _TestRenderer)
        with pytest.raises(ValueError, match="already registered"):
            register_renderer("_test_dup", _TestRenderer)
        # cleanup
        RENDERER_REGISTRY.pop("_test_dup", None)


class TestJSONRenderer:
    def test_render_minimal_ir(self):
        import json
        from uasset_read.renderers import get_renderer
        from uasset_read.models.ir import PackageIR, PackageHeaderIR
        from uasset_read.renderers.base import RenderOptions

        header = PackageHeaderIR(
            package_name="/Game/Test", package_class="Test_C",
            package_flags=0, total_export_count=0, total_import_count=0,
            ue_version="5.x")
        ir = PackageIR(header=header, name_map=["Test"], imports=[], exports=[], linker=None)

        renderer = get_renderer("json")
        output = renderer.render(ir, RenderOptions())

        data = json.loads(output)
        assert data["status"]["status"] == "success"
        assert data["summary"]["package_name"] == "/Game/Test"
        assert "blueprint" not in data

    def test_render_with_exports(self):
        import json
        from uasset_read.renderers import get_renderer
        from uasset_read.models.ir import (
            PackageIR, PackageHeaderIR, ExportIR, PropertyIR,
            GraphIR, NodeIR, PinIR, LinkerSummaryIR,
        )
        from uasset_read.renderers.base import RenderOptions

        header = PackageHeaderIR(
            package_name="/Game/TestBP", package_class="TestBP_C",
            package_flags=0, total_export_count=1, total_import_count=2,
            ue_version="5.3")
        prop = PropertyIR(name="Health", type="FloatProperty", value=100.0, array_index=0, guid=None)
        pin = PinIR(pin_name="Exec", pin_type="exec", pin_type_value=None, linked_to=["abcd12345678"], direction=1, default_value=None)
        node = NodeIR(node_guid="abcd1234567890abcdef1234567890ab", node_class="K2Node_CallFunction", node_comment="Set Health", pins=[pin], execution_flow=[])
        graph = GraphIR(graph_guid="guid0001", graph_name="EventGraph", graph_class="EdGraph", nodes=[node], execution_chains=[["N1", "N2"]])
        export = ExportIR(
            index=0, object_name="Default__TestBP_C", object_class="BlueprintGeneratedClass",
            serial_size=1024, outer_index_resolved=None, super_index_resolved=None,
            parent_class="Actor", properties=[prop], graphs=[graph], bulk_data=None)
        linker = LinkerSummaryIR(has_linker=True, import_paths=["/Engine/Core"], export_paths=["/Game/TestBP"])
        ir = PackageIR(header=header, name_map=["TestBP", "Health"], imports=[], exports=[export], linker=linker)

        renderer = get_renderer("json")
        output = renderer.render(ir, RenderOptions(include_function_graphs=True))

        data = json.loads(output)
        assert data["summary"]["package_name"] == "/Game/TestBP"
        assert len(data["exports"]) == 1
        assert data["exports"][0]["object_name"] == "Default__TestBP_C"
        assert len(data["exports"][0]["graphs"]) == 1
        assert "function_graphs" in data


class TestTextRenderer:
    def test_render_minimal_ir(self):
        from uasset_read.renderers import get_renderer
        from uasset_read.models.ir import PackageIR, PackageHeaderIR
        from uasset_read.renderers.base import RenderOptions

        header = PackageHeaderIR(
            package_name="/Game/Test", package_class="Test_C",
            package_flags=0, total_export_count=1, total_import_count=0,
            ue_version="5.x")
        ir = PackageIR(header=header, name_map=["Test"], imports=[], exports=[], linker=None)

        renderer = get_renderer("text")
        output = renderer.render(ir, RenderOptions())

        assert "Package: /Game/Test" in output
        assert "Class: Test_C" in output
        assert "Exports: 1" in output

    def test_render_with_exports(self):
        from uasset_read.renderers import get_renderer
        from uasset_read.models.ir import (
            PackageIR, PackageHeaderIR, ExportIR, PropertyIR,
        )
        from uasset_read.renderers.base import RenderOptions

        header = PackageHeaderIR(
            package_name="/Game/TestBP", package_class="TestBP_C",
            package_flags=0, total_export_count=1, total_import_count=1,
            ue_version="5.3")
        prop = PropertyIR(name="Health", type="FloatProperty", value=100.0, array_index=0, guid=None)
        export = ExportIR(
            index=0, object_name="Default__TestBP_C", object_class="BlueprintGeneratedClass",
            serial_size=512, outer_index_resolved=None, super_index_resolved=None,
            parent_class="Actor", properties=[prop], graphs=[], bulk_data=None)
        ir = PackageIR(header=header, name_map=["TestBP"], imports=[], exports=[export], linker=None)

        renderer = get_renderer("text")
        output = renderer.render(ir, RenderOptions())

        assert "Default__TestBP_C" in output
        assert "Health (FloatProperty)" in output
        assert "100.0" in output

    def test_render_summary(self):
        from uasset_read.renderers import get_renderer
        from uasset_read.models.ir import (
            PackageIR, PackageHeaderIR, ExportIR,
        )
        from uasset_read.renderers.base import RenderOptions

        header = PackageHeaderIR(
            package_name="/Game/TestBP", package_class="TestBP_C",
            package_flags=0, total_export_count=2, total_import_count=1,
            ue_version="5.3")
        export = ExportIR(
            index=0, object_name="Default__TestBP_C", object_class="BlueprintGeneratedClass",
            serial_size=256, outer_index_resolved=None, super_index_resolved=None,
            parent_class="Actor", properties=[], graphs=[], bulk_data=None)
        ir = PackageIR(header=header, name_map=["TestBP"], imports=[], exports=[export], linker=None)

        renderer = get_renderer("text_summary")
        output = renderer.render(ir, RenderOptions())

        assert "Package: /Game/TestBP" in output
        assert "Default__TestBP_C (BlueprintGeneratedClass)" in output
        assert "Parent: Actor" in output


class TestMarkdownRenderer:
    def test_render_minimal_ir(self):
        from uasset_read.renderers import get_renderer
        from uasset_read.models.ir import PackageIR, PackageHeaderIR
        from uasset_read.renderers.base import RenderOptions

        header = PackageHeaderIR(
            package_name="/Game/Test", package_class="Test_C",
            package_flags=0, total_export_count=0, total_import_count=0,
            ue_version="5.x")
        ir = PackageIR(header=header, name_map=["Test"], imports=[], exports=[], linker=None)

        renderer = get_renderer("markdown")
        output = renderer.render(ir, RenderOptions())

        assert "# Test" in output
        assert "| Class |" in output
        assert "| Package |" in output

    def test_render_with_mermaid(self):
        from uasset_read.renderers import get_renderer
        from uasset_read.models.ir import (
            PackageIR, PackageHeaderIR, ExportIR, GraphIR, NodeIR, PinIR,
        )
        from uasset_read.renderers.base import RenderOptions

        pin = PinIR(pin_name="Exec", pin_type="exec", pin_type_value=None, linked_to=["target1234"], direction=1, default_value=None)
        node = NodeIR(node_guid="abcd1234567890abcdef1234567890ab", node_class="K2Node_Event", node_comment="BeginPlay", pins=[pin], execution_flow=[])
        graph = GraphIR(graph_guid="guid0001", graph_name="EventGraph", graph_class="EdGraph", nodes=[node], execution_chains=[])
        export = ExportIR(
            index=0, object_name="Default__TestBP_C", object_class="BlueprintGeneratedClass",
            serial_size=1024, outer_index_resolved=None, super_index_resolved=None,
            parent_class=None, properties=[], graphs=[graph], bulk_data=None)
        header = PackageHeaderIR(
            package_name="/Game/TestBP", package_class="TestBP_C",
            package_flags=0, total_export_count=1, total_import_count=0,
            ue_version="5.3")
        ir = PackageIR(header=header, name_map=["TestBP"], imports=[], exports=[export], linker=None)

        renderer = get_renderer("markdown")
        output = renderer.render(ir, RenderOptions())

        assert "EventGraph" in output
        assert "```mermaid" in output
        assert "graph TD" in output
        assert "BeginPlay" in output


class TestBlueprintTextRenderer:
    def test_render_minimal_ir(self):
        from uasset_read.renderers import get_renderer
        from uasset_read.models.ir import PackageIR, PackageHeaderIR
        from uasset_read.renderers.base import RenderOptions

        header = PackageHeaderIR(
            package_name="/Game/TestBP", package_class="TestBP_C",
            package_flags=0, total_export_count=1, total_import_count=0,
            ue_version="5.x")
        ir = PackageIR(header=header, name_map=["TestBP"], imports=[], exports=[], linker=None)

        renderer = get_renderer("blueprint_text")
        output = renderer.render(ir, RenderOptions())

        assert "Package: /Game/TestBP" in output
        assert "Class: TestBP_C" in output

    def test_render_with_graphs(self):
        from uasset_read.renderers import get_renderer
        from uasset_read.models.ir import (
            PackageIR, PackageHeaderIR, ExportIR, GraphIR, NodeIR, PinIR,
        )
        from uasset_read.renderers.base import RenderOptions

        pin = PinIR(pin_name="Exec", pin_type="exec", pin_type_value=None, linked_to=[], direction=0, default_value=None)
        node = NodeIR(node_guid="abcd1234567890abcdef1234567890ab", node_class="K2Node_Event", node_comment="BeginPlay", pins=[pin], execution_flow=[])
        graph = GraphIR(graph_guid="guid0001", graph_name="EventGraph", graph_class="EdGraph", nodes=[node], execution_chains=[["N1", "N2"]])
        export = ExportIR(
            index=0, object_name="Default__TestBP_C", object_class="BlueprintGeneratedClass",
            serial_size=256, outer_index_resolved=None, super_index_resolved=None,
            parent_class="Actor", properties=[], graphs=[graph], bulk_data=None)
        header = PackageHeaderIR(
            package_name="/Game/TestBP", package_class="TestBP_C",
            package_flags=0, total_export_count=1, total_import_count=0,
            ue_version="5.3")
        ir = PackageIR(header=header, name_map=["TestBP"], imports=[], exports=[export], linker=None)

        renderer = get_renderer("blueprint_text")
        output = renderer.render(ir, RenderOptions())

        assert "EventGraph" in output
        assert "[Event]" in output
        assert "BeginPlay" in output
        assert "Pin(in): Exec (exec)" in output


class TestBlueprintUERenderer:
    def test_render_minimal_ir(self):
        from uasset_read.renderers import get_renderer
        from uasset_read.models.ir import PackageIR, PackageHeaderIR
        from uasset_read.renderers.base import RenderOptions

        header = PackageHeaderIR(
            package_name="/Game/TestBP", package_class="TestBP_C",
            package_flags=0, total_export_count=1, total_import_count=0,
            ue_version="5.x")
        ir = PackageIR(header=header, name_map=["TestBP"], imports=[], exports=[], linker=None)

        renderer = get_renderer("blueprint_ue_text")
        output = renderer.render(ir, RenderOptions())

        assert 'Begin Object Class="TestBP_C"' in output
        assert 'Name="/Game/TestBP"' in output
        assert "End Object" in output

    def test_render_with_properties(self):
        from uasset_read.renderers import get_renderer
        from uasset_read.models.ir import (
            PackageIR, PackageHeaderIR, ExportIR, PropertyIR,
        )
        from uasset_read.renderers.base import RenderOptions

        prop = PropertyIR(name="DisplayName", type="StrProperty", value="Test Actor", array_index=0, guid=None)
        export = ExportIR(
            index=0, object_name="Default__TestBP_C", object_class="BlueprintGeneratedClass",
            serial_size=128, outer_index_resolved=None, super_index_resolved=None,
            parent_class="Actor", properties=[prop], graphs=[], bulk_data=None)
        header = PackageHeaderIR(
            package_name="/Game/TestBP", package_class="TestBP_C",
            package_flags=0, total_export_count=1, total_import_count=0,
            ue_version="5.3")
        ir = PackageIR(header=header, name_map=["TestBP"], imports=[], exports=[export], linker=None)

        renderer = get_renderer("blueprint_ue_text")
        output = renderer.render(ir, RenderOptions())

        assert "DisplayName=Test Actor" in output


class TestCppSkeletonRenderer:
    def test_render_minimal_ir(self):
        from uasset_read.renderers import get_renderer
        from uasset_read.models.ir import PackageIR, PackageHeaderIR
        from uasset_read.renderers.base import RenderOptions

        header = PackageHeaderIR(
            package_name="/Game/TestBP", package_class="TestBP_C",
            package_flags=0, total_export_count=1, total_import_count=0,
            ue_version="5.x")
        ir = PackageIR(header=header, name_map=["TestBP"], imports=[], exports=[], linker=None)

        renderer = get_renderer("cpp_skeleton")
        output = renderer.render(ir, RenderOptions())

        assert "#pragma once" in output
        assert '#include "CoreMinimal.h"' in output
        assert "class TestBP" in output
        assert "GENERATED_BODY()" in output
        assert "UCLASS()" in output

    def test_render_with_properties(self):
        from uasset_read.renderers import get_renderer
        from uasset_read.models.ir import (
            PackageIR, PackageHeaderIR, ExportIR, PropertyIR,
        )
        from uasset_read.renderers.base import RenderOptions

        props = [
            PropertyIR(name="Health", type="FloatProperty", value=100.0, array_index=0, guid=None),
            PropertyIR(name="bIsAlive", type="BoolProperty", value=True, array_index=0, guid=None),
            PropertyIR(name="DisplayName", type="StrProperty", value="Test", array_index=0, guid=None),
        ]
        export = ExportIR(
            index=0, object_name="Default__TestBP_C", object_class="BlueprintGeneratedClass",
            serial_size=256, outer_index_resolved=None, super_index_resolved=None,
            parent_class="Actor", properties=props, graphs=[], bulk_data=None)
        header = PackageHeaderIR(
            package_name="/Game/TestBP", package_class="TestBP_C",
            package_flags=0, total_export_count=1, total_import_count=0,
            ue_version="5.3")
        ir = PackageIR(header=header, name_map=["TestBP"], imports=[], exports=[export], linker=None)

        renderer = get_renderer("cpp_skeleton")
        output = renderer.render(ir, RenderOptions())

        assert "float Health" in output
        assert "bool bIsAlive" in output
        assert "FString DisplayName" in output
        assert "UPROPERTY()" in output


class TestRendererListFormats:
    def test_all_formats_registered(self):
        from uasset_read.renderers import list_formats
        fmts = list_formats()
        assert "json" in fmts
        assert "json_summary" in fmts
        assert "text" in fmts
        assert "text_summary" in fmts
        assert "markdown" in fmts
        assert "blueprint_text" in fmts
        assert "blueprint_ue_text" in fmts
        assert "cpp_skeleton" in fmts
        assert len(fmts) == 8

    def test_get_renderer_all_registered(self):
        from uasset_read.renderers import get_renderer
        formats = [
            "json", "json_summary", "text", "text_summary",
            "markdown", "blueprint_text", "blueprint_ue_text", "cpp_skeleton",
        ]
        for fmt in formats:
            r = get_renderer(fmt)
            # Aliased formats (json_summary -> json, text_summary -> text_summary class)
            # may have different format_name than the registry key
            assert r.format_name in formats