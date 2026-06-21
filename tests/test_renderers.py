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
    def test_json_excludes_redundant_fields(self):
        """JSON 输出不应包含 name_map, imports, linker 等冗余字段"""
        import json
        from uasset_read.renderers.json_renderer import JSONRenderer
        from uasset_read.renderers.base import RenderOptions
        from uasset_read.models.ir import PackageIR, PackageHeaderIR

        # 创建最小 IR
        ir = PackageIR(
            header=PackageHeaderIR(
                package_name="/Game/Test",
                package_class="",
                package_flags=0,
                total_export_count=0,
                total_import_count=0,
                ue_version="5.x",
            ),
            name_map=["test"],
            imports=[],
            exports=[],
            linker=None,
        )
        ir.status = "success"

        renderer = JSONRenderer()
        options = RenderOptions()
        result = renderer.render(ir, options)
        data = json.loads(result)

        # 验证不包含冗余字段
        assert "name_map" not in data, "name_map 应被移除"
        assert "imports" not in data, "imports 应被移除"
        assert "linker" not in data, "linker 应被移除"
        assert "resolved_depends_map" not in data, "resolved_depends_map 应被移除"
        assert "depends_map" not in data, "depends_map 应被移除"
        assert "soft_package_references" not in data, "soft_package_references 应被移除"

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


class TestRendererListFormats:
    def test_all_formats_registered(self):
        from uasset_read.renderers import list_formats
        fmts = list_formats()
        assert "json" in fmts
        assert "markdown" in fmts
        assert len(fmts) == 2

    def test_get_renderer_all_registered(self):
        from uasset_read.renderers import get_renderer
        formats = ["json", "markdown"]
        for fmt in formats:
            r = get_renderer(fmt)
            assert r.format_name == fmt


class TestJSONOnlyBlueprintExports:
    """验证 JSON 输出只包含蓝图相关 export。"""

    def test_json_only_blueprint_exports(self):
        """JSON 输出应只包含蓝图相关 export（类名以 _C 结尾或有 graphs）"""
        import json
        from uasset_read.renderers.json_renderer import JSONRenderer
        from uasset_read.renderers.base import RenderOptions
        from uasset_read.models.ir import (
            PackageIR, PackageHeaderIR, ExportIR, GraphIR,
        )

        # 创建两个 export：一个蓝图，一个非蓝图
        bp_export = ExportIR(
            index=0,
            object_name="BP_Test_C",
            object_class="",
            serial_size=100,
            outer_index_resolved=None,
            super_index_resolved=None,
            parent_class="/Script/Engine.Actor",
            properties=[],
            graphs=[GraphIR(graph_guid="abc", graph_name="EventGraph", graph_class="EdGraph", nodes=[], execution_chains=[])],
            bulk_data=None,
            asset_type_data=None,
            parse_status="success",
            fallback_reason=None,
            error_message=None,
            ue_export_raw=None,
            diagnostics={},
        )

        non_bp_export = ExportIR(
            index=1,
            object_name="BodySetup",
            object_class="",
            serial_size=200,
            outer_index_resolved=None,
            super_index_resolved=None,
            parent_class=None,
            properties=[],
            graphs=[],
            bulk_data=None,
            asset_type_data=None,
            parse_status="success",
            fallback_reason=None,
            error_message=None,
            ue_export_raw=None,
            diagnostics={},
        )

        ir = PackageIR(
            header=PackageHeaderIR(
                package_name="/Game/Test",
                package_class="",
                package_flags=0,
                total_export_count=2,
                total_import_count=0,
                ue_version="5.x",
            ),
            name_map=[],
            imports=[],
            exports=[bp_export, non_bp_export],
            linker=None,
        )
        ir.status = "success"

        renderer = JSONRenderer()
        options = RenderOptions()
        result = renderer.render(ir, options)
        data = json.loads(result)

        # 验证只包含蓝图 export
        assert len(data["exports"]) == 1, f"应只有 1 个蓝图 export，实际有 {len(data['exports'])}"
        assert data["exports"][0]["object_name"] == "BP_Test_C", "应保留蓝图 export"

    def test_export_name_ends_with_c_is_blueprint(self):
        """类名以 _C 结尾的 export 应被视为蓝图 export"""
        import json
        from uasset_read.renderers.json_renderer import JSONRenderer
        from uasset_read.renderers.base import RenderOptions
        from uasset_read.models.ir import PackageIR, PackageHeaderIR, ExportIR

        export = ExportIR(
            index=0,
            object_name="Default__MyBP_C",
            object_class="BlueprintGeneratedClass",
            serial_size=512,
            outer_index_resolved=None,
            super_index_resolved=None,
            parent_class="Actor",
            properties=[],
            graphs=[],
            bulk_data=None,
        )

        ir = PackageIR(
            header=PackageHeaderIR(
                package_name="/Game/MyBP", package_class="MyBP_C",
                package_flags=0, total_export_count=1, total_import_count=0,
                ue_version="5.x",
            ),
            name_map=[], imports=[], exports=[export],
            linker=None,
        )
        ir.status = "success"

        renderer = JSONRenderer()
        result = renderer.render(ir, RenderOptions())
        data = json.loads(result)

        assert len(data["exports"]) == 1, "以 _C 结尾的 export 应保留"
        assert data["exports"][0]["object_name"] == "Default__MyBP_C"

    def test_export_with_graphs_is_blueprint(self):
        """有 graphs 数据的 export 即使不以 _C 结尾也应保留"""
        import json
        from uasset_read.renderers.json_renderer import JSONRenderer
        from uasset_read.renderers.base import RenderOptions
        from uasset_read.models.ir import (
            PackageIR, PackageHeaderIR, ExportIR, GraphIR,
        )

        export = ExportIR(
            index=0,
            object_name="SomeFunc",
            object_class="",
            serial_size=256,
            outer_index_resolved=None,
            super_index_resolved=None,
            parent_class=None,
            properties=[],
            graphs=[GraphIR(graph_guid="g1", graph_name="FuncGraph", graph_class="EdGraph", nodes=[], execution_chains=[])],
            bulk_data=None,
        )

        ir = PackageIR(
            header=PackageHeaderIR(
                package_name="/Game/Test", package_class="",
                package_flags=0, total_export_count=1, total_import_count=0,
                ue_version="5.x",
            ),
            name_map=[], imports=[], exports=[export],
            linker=None,
        )
        ir.status = "success"

        renderer = JSONRenderer()
        result = renderer.render(ir, RenderOptions())
        data = json.loads(result)

        assert len(data["exports"]) == 1, "有 graphs 的 export 应保留"
        assert data["exports"][0]["object_name"] == "SomeFunc"

    def test_no_blueprint_exports_empty_list(self):
        """如果没有蓝图 export，exports 应为空列表"""
        import json
        from uasset_read.renderers.json_renderer import JSONRenderer
        from uasset_read.renderers.base import RenderOptions
        from uasset_read.models.ir import PackageIR, PackageHeaderIR, ExportIR

        export = ExportIR(
            index=0,
            object_name="TextureAsset",
            object_class="Texture2D",
            serial_size=1024,
            outer_index_resolved=None,
            super_index_resolved=None,
            parent_class=None,
            properties=[],
            graphs=[],
            bulk_data=None,
        )

        ir = PackageIR(
            header=PackageHeaderIR(
                package_name="/Game/Tex", package_class="",
                package_flags=0, total_export_count=1, total_import_count=0,
                ue_version="5.x",
            ),
            name_map=[], imports=[], exports=[export],
            linker=None,
        )
        ir.status = "success"

        renderer = JSONRenderer()
        result = renderer.render(ir, RenderOptions())
        data = json.loads(result)

        assert len(data["exports"]) == 0, "无蓝图 export 时应为空列表"


class TestMarkdownOnlyBlueprintExports:
    """验证 Markdown 输出只包含蓝图相关 export。"""

    def test_markdown_only_blueprint_exports(self):
        """Markdown Export 表格应只包含蓝图相关 export"""
        from uasset_read.renderers.markdown_renderer import MarkdownRenderer
        from uasset_read.renderers.base import RenderOptions
        from uasset_read.models.ir import (
            PackageIR, PackageHeaderIR, ExportIR, GraphIR,
        )

        bp_export = ExportIR(
            index=0,
            object_name="BP_Test_C",
            object_class="",
            serial_size=100,
            outer_index_resolved=None,
            super_index_resolved=None,
            parent_class="/Script/Engine.Actor",
            properties=[],
            graphs=[GraphIR(graph_guid="abc", graph_name="EventGraph", graph_class="EdGraph", nodes=[], execution_chains=[])],
            bulk_data=None,
            asset_type_data=None,
            parse_status="success",
            fallback_reason=None,
            error_message=None,
            ue_export_raw=None,
            diagnostics={},
        )

        non_bp_export = ExportIR(
            index=1,
            object_name="BodySetup",
            object_class="",
            serial_size=200,
            outer_index_resolved=None,
            super_index_resolved=None,
            parent_class=None,
            properties=[],
            graphs=[],
            bulk_data=None,
            asset_type_data=None,
            parse_status="success",
            fallback_reason=None,
            error_message=None,
            ue_export_raw=None,
            diagnostics={},
        )

        ir = PackageIR(
            header=PackageHeaderIR(
                package_name="/Game/Test",
                package_class="",
                package_flags=0,
                total_export_count=2,
                total_import_count=0,
                ue_version="5.x",
            ),
            name_map=[],
            imports=[],
            exports=[bp_export, non_bp_export],
            linker=None,
        )
        ir.status = "success"

        renderer = MarkdownRenderer()
        options = RenderOptions()
        result = renderer.render(ir, options)

        # 验证只包含蓝图 export
        assert "BP_Test_C" in result, "应包含蓝图 export"
        assert "BodySetup" not in result, "不应包含非蓝图 export"

    def test_export_name_ends_with_c_is_blueprint(self):
        """类名以 _C 结尾的 export 应被视为蓝图 export"""
        from uasset_read.renderers.markdown_renderer import MarkdownRenderer
        from uasset_read.renderers.base import RenderOptions
        from uasset_read.models.ir import PackageIR, PackageHeaderIR, ExportIR

        export = ExportIR(
            index=0,
            object_name="Default__MyBP_C",
            object_class="BlueprintGeneratedClass",
            serial_size=512,
            outer_index_resolved=None,
            super_index_resolved=None,
            parent_class="Actor",
            properties=[],
            graphs=[],
            bulk_data=None,
        )

        ir = PackageIR(
            header=PackageHeaderIR(
                package_name="/Game/MyBP", package_class="MyBP_C",
                package_flags=0, total_export_count=1, total_import_count=0,
                ue_version="5.x",
            ),
            name_map=[], imports=[], exports=[export],
            linker=None,
        )
        ir.status = "success"

        renderer = MarkdownRenderer()
        result = renderer.render(ir, RenderOptions())

        assert "Default__MyBP_C" in result, "以 _C 结尾的 export 应在 Markdown 中保留"

    def test_export_with_graphs_is_blueprint(self):
        """有 graphs 数据的 export 即使不以 _C 结尾也应保留"""
        from uasset_read.renderers.markdown_renderer import MarkdownRenderer
        from uasset_read.renderers.base import RenderOptions
        from uasset_read.models.ir import (
            PackageIR, PackageHeaderIR, ExportIR, GraphIR,
        )

        export = ExportIR(
            index=0,
            object_name="SomeFunc",
            object_class="",
            serial_size=256,
            outer_index_resolved=None,
            super_index_resolved=None,
            parent_class=None,
            properties=[],
            graphs=[GraphIR(graph_guid="g1", graph_name="FuncGraph", graph_class="EdGraph", nodes=[], execution_chains=[])],
            bulk_data=None,
        )

        ir = PackageIR(
            header=PackageHeaderIR(
                package_name="/Game/Test", package_class="",
                package_flags=0, total_export_count=1, total_import_count=0,
                ue_version="5.x",
            ),
            name_map=[], imports=[], exports=[export],
            linker=None,
        )
        ir.status = "success"

        renderer = MarkdownRenderer()
        result = renderer.render(ir, RenderOptions())

        assert "SomeFunc" in result, "有 graphs 的 export 应在 Markdown 中保留"

    def test_no_blueprint_exports_no_exports_table(self):
        """如果没有蓝图 export，不应输出 Exports 表格"""
        from uasset_read.renderers.markdown_renderer import MarkdownRenderer
        from uasset_read.renderers.base import RenderOptions
        from uasset_read.models.ir import PackageIR, PackageHeaderIR, ExportIR

        export = ExportIR(
            index=0,
            object_name="TextureAsset",
            object_class="Texture2D",
            serial_size=1024,
            outer_index_resolved=None,
            super_index_resolved=None,
            parent_class=None,
            properties=[],
            graphs=[],
            bulk_data=None,
        )

        ir = PackageIR(
            header=PackageHeaderIR(
                package_name="/Game/Tex", package_class="",
                package_flags=0, total_export_count=1, total_import_count=0,
                ue_version="5.x",
            ),
            name_map=[], imports=[], exports=[export],
            linker=None,
        )
        ir.status = "success"

        renderer = MarkdownRenderer()
        result = renderer.render(ir, RenderOptions())

        assert "## Exports" not in result, "无蓝图 export 时不应输出 Exports 表格"
        assert "TextureAsset" not in result, "非蓝图 export 不应出现在输出中"


class TestJSONExportExcludesRawFields:
    """验证 JSON export 不包含冗余字段。"""

    def test_json_export_excludes_raw_fields(self):
        """JSON export 不应包含 ue_export_raw, diagnostics, outer_index_resolved 等"""
        import json
        from uasset_read.renderers.json_renderer import JSONRenderer
        from uasset_read.renderers.base import RenderOptions
        from uasset_read.models.ir import (
            PackageIR, PackageHeaderIR, ExportIR, ExportRawIR,
        )

        # 创建带 export 的 IR（使用蓝图类名以通过过滤）
        export = ExportIR(
            index=0,
            object_name="TestExport_C",
            object_class="",
            serial_size=100,
            outer_index_resolved="/Game/Test",
            super_index_resolved="/Script/Engine.Actor",
            parent_class="/Script/Engine.Actor",
            properties=[],
            graphs=[],
            bulk_data=None,
            asset_type_data=None,
            parse_status="success",
            fallback_reason=None,
            error_message=None,
            ue_export_raw=ExportRawIR(),
            diagnostics={"test": "data"},
        )

        ir = PackageIR(
            header=PackageHeaderIR(
                package_name="/Game/Test",
                package_class="",
                package_flags=0,
                total_export_count=1,
                total_import_count=0,
                ue_version="5.x",
            ),
            name_map=[],
            imports=[],
            exports=[export],
            linker=None,
        )
        ir.status = "success"

        renderer = JSONRenderer()
        options = RenderOptions()
        result = renderer.render(ir, options)
        data = json.loads(result)

        export_data = data["exports"][0]

        # 验证保留的字段
        assert "object_name" in export_data
        assert "object_class" in export_data
        assert "serial_size" in export_data
        assert "parent_class" in export_data
        assert "properties" in export_data
        assert "graphs" in export_data

        # 验证移除的字段
        assert "ue_export_raw" not in export_data, "ue_export_raw 应被移除"
        assert "diagnostics" not in export_data, "diagnostics 应被移除"
        assert "outer_index_resolved" not in export_data, "outer_index_resolved 应被移除"
        assert "super_index_resolved" not in export_data, "super_index_resolved 应被移除"
        assert "index" not in export_data, "index 应被移除（无用）"
        assert "bulk_data" not in export_data, "bulk_data 应被移除"
        assert "asset_type_data" not in export_data, "asset_type_data 应被移除"


class TestMarkdownExcludesLinkerSection:
    """验证 Markdown 输出不包含冗余的 Linker 小节。"""

    def test_markdown_excludes_linker_section(self):
        """Markdown 输出不应包含 Linker 小节"""
        from uasset_read.renderers.markdown_renderer import MarkdownRenderer
        from uasset_read.renderers.base import RenderOptions
        from uasset_read.models.ir import PackageIR, PackageHeaderIR, LinkerSummaryIR

        ir = PackageIR(
            header=PackageHeaderIR(
                package_name="/Game/Test",
                package_class="",
                package_flags=0,
                total_export_count=0,
                total_import_count=0,
                ue_version="5.x",
            ),
            name_map=[],
            imports=[],
            exports=[],
            linker=LinkerSummaryIR(
                has_linker=True,
                import_paths=["/Script/Engine"],
                export_paths=["/Game/Test"],
            ),
        )
        ir.status = "success"

        renderer = MarkdownRenderer()
        options = RenderOptions()
        result = renderer.render(ir, options)

        # 验证不包含 Linker 小节
        assert "## Linker" not in result, "Linker 小节应被移除"
        assert "Has Linker" not in result, "Has Linker 应被移除"


class TestOnlyJsonAndMarkdownFormats:
    """验证只支持 json 和 markdown 两种格式。"""

    def test_only_json_and_markdown_formats(self):
        """应只支持 json 和 markdown 两种格式"""
        from uasset_read.renderers import list_formats

        formats = list_formats()
        assert "json" in formats, "json 格式应存在"
        assert "markdown" in formats, "markdown 格式应存在"
        assert "text" not in formats, "text 格式应被移除"
        assert "text_summary" not in formats, "text_summary 格式应被移除"
        assert "blueprint_text" not in formats, "blueprint_text 格式应被移除"
        assert "blueprint_ue_text" not in formats, "blueprint_ue_text 格式应被移除"
        assert "cpp_skeleton" not in formats, "cpp_skeleton 格式应被移除"
        assert "json_summary" not in formats, "json_summary 格式应被移除"