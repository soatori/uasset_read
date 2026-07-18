"""渲染器文本输出测试 — 合并自 test_text_renderer / test_markdown_renderer。

覆盖范围：
- TextRenderer 基础渲染、选项、Export、Import、Variable、Graph、Linker、Blueprint
- TextRenderer 反编译函数、执行链、诊断、状态、render_to、动画
- TextRenderer 废弃警告、diff_single、注册验证
- MarkdownRenderer 基础渲染、导出表、图渲染、属性、变量
- MarkdownRenderer 蓝图详情、Event Graph、Functions、Asset Registry、诊断、边界
"""
from __future__ import annotations

import warnings
from io import StringIO

import pytest

from uasset_read.renderers import get_renderer
from uasset_read.renderers.text_renderer import TextRenderer
from uasset_read.renderers.markdown_renderer import MarkdownRenderer
from uasset_read.renderers.base import RenderOptions, EDITOR_PROPERTY_NAMES, EDITOR_VARIABLE_NAMES
from uasset_read.models.ir import (
    PackageIR, PackageHeaderIR, ExportIR, GraphIR, NodeIR, PinIR,
    PropertyIR, BlueprintIR, BlueprintFunctionIR, BlueprintEventIR,
    VariableIR, ExecutionChainIR, LinkerSummaryIR, DecompiledFunctionIR,
    AnimBlueprintIR, AnimSequenceIR, AnimMontageIR, BakedStateMachineIR,
)


# ===========================================================================
# TextRenderer — 基础渲染功能 (test_text_renderer)
# ===========================================================================


@pytest.fixture
def text_renderer():
    return TextRenderer()


@pytest.fixture
def md_renderer():
    return MarkdownRenderer()


class TestTextRendererBasic:
    def test_render_returns_string(self, text_renderer, make_package_ir):
        ir = make_package_ir()
        result = text_renderer.render(ir, RenderOptions())
        assert isinstance(result, str)
        assert len(result) > 0

    def test_render_includes_package_name(self, text_renderer, make_package_ir):
        ir = make_package_ir(name="TestPackage")
        result = text_renderer.render(ir, RenderOptions())
        assert "TestPackage" in result

    def test_render_includes_version(self, text_renderer, make_package_ir):
        ir = make_package_ir()
        result = text_renderer.render(ir, RenderOptions())
        assert "5.4" in result

    def test_render_includes_type(self, text_renderer, make_package_ir):
        ir = make_package_ir(class_name="WidgetBlueprint")
        result = text_renderer.render(ir, RenderOptions())
        assert "WidgetBlueprint" in result

    def test_render_includes_export_import_counts(self, text_renderer, make_package_ir):
        ir = make_package_ir()
        result = text_renderer.render(ir, RenderOptions())
        assert "Exports: 0" in result
        assert "Imports: 0" in result

    def test_render_empty_exports(self, text_renderer, make_package_ir):
        ir = make_package_ir(exports=[])
        result = text_renderer.render(ir, RenderOptions())
        assert isinstance(result, str)

    def test_render_header_structure(self, text_renderer, make_package_ir):
        ir = make_package_ir(name="MyPkg")
        result = text_renderer.render(ir, RenderOptions())
        assert result.startswith("=== MyPkg ===")
        assert "Type:" in result
        assert "Version:" in result

    def test_render_package_flags(self, text_renderer, make_package_ir):
        header_ir = make_package_ir()
        header_ir.header.package_flags = 0xDEADBEEF
        result = text_renderer.render(header_ir, RenderOptions())
        assert "Flags: 0xDEADBEEF" in result

    def test_render_zero_flags_no_flags_line(self, text_renderer, make_package_ir):
        ir = make_package_ir()
        result = text_renderer.render(ir, RenderOptions())
        assert "Flags:" not in result

    def test_render_folder_name(self, text_renderer, make_package_ir):
        ir = make_package_ir()
        ir.header.folder_name = "Content/Blueprints"
        result = text_renderer.render(ir, RenderOptions())
        assert "Folder: Content/Blueprints" in result

    def test_render_no_folder_name(self, text_renderer, make_package_ir):
        ir = make_package_ir()
        result = text_renderer.render(ir, RenderOptions())
        assert "Folder:" not in result

    def test_format_name(self, text_renderer):
        assert text_renderer.format_name == "text"


class TestTextRendererOptions:
    def test_verbose_mode(self, text_renderer, make_package_ir):
        ir = make_package_ir()
        standard = text_renderer.render(ir, RenderOptions(verbose=False))
        verbose = text_renderer.render(ir, RenderOptions(verbose=True))
        assert len(verbose) >= len(standard)

    def test_debug_shows_editor_variables(self, text_renderer, make_package_ir):
        var = VariableIR(name="ThumbnailInfo", type="ObjectProperty", default_value=None)
        ir = make_package_ir(variables=[var])
        standard = text_renderer.render(ir, RenderOptions(output_level="standard"))
        debug = text_renderer.render(ir, RenderOptions(output_level="debug"))
        assert "ThumbnailInfo" not in standard
        assert "ThumbnailInfo" in debug

    def test_standard_filters_editor_variables(self, text_renderer, make_package_ir):
        vars_ = [
            VariableIR(name="FunctionGraphs", type="Array<int>", default_value="[]"),
            VariableIR(name="CategorySorting", type="Array<str>", default_value="[]"),
            VariableIR(name="UserVar", type="bool", default_value="False"),
        ]
        ir = make_package_ir(variables=vars_)
        result = text_renderer.render(ir, RenderOptions(output_level="standard"))
        assert "FunctionGraphs" not in result
        assert "CategorySorting" not in result
        assert "UserVar" in result

    def test_debug_shows_editor_node_classes(self, text_renderer, make_package_ir, make_export_ir, make_graph_ir, make_node_ir):
        knot = make_node_ir(node_class="K2Node_Knot")
        graph = make_graph_ir(name="KnotGraph", nodes=[knot])
        export = make_export_ir(graphs=[graph])
        ir = make_package_ir(exports=[export])
        standard = text_renderer.render(ir, RenderOptions(output_level="standard"))
        debug = text_renderer.render(ir, RenderOptions(output_level="debug"))
        assert "KnotGraph" not in standard
        assert "KnotGraph" in debug

    def test_standard_filters_editor_nodes(self, text_renderer, make_package_ir, make_export_ir, make_graph_ir, make_node_ir):
        knot = make_node_ir(node_class="K2Node_Knot")
        event_node = make_node_ir(node_class="K2Node_Event")
        graph = make_graph_ir(name="MixedGraph", nodes=[knot, event_node])
        export = make_export_ir(graphs=[graph])
        ir = make_package_ir(exports=[export])
        result = text_renderer.render(ir, RenderOptions(output_level="standard"))
        assert "MixedGraph" in result
        assert "Nodes: 1" in result


class TestTextRendererExport:
    def test_render_with_export(self, text_renderer, make_package_ir, make_export_ir):
        export = make_export_ir(object_name="MyFunction")
        ir = make_package_ir(exports=[export])
        result = text_renderer.render(ir, RenderOptions())
        assert "MyFunction" in result
        assert "[Exports]" in result

    def test_render_export_index(self, text_renderer, make_package_ir, make_export_ir):
        export = make_export_ir(index=3, object_name="IndexedExport")
        ir = make_package_ir(exports=[export])
        result = text_renderer.render(ir, RenderOptions())
        assert "[3] IndexedExport" in result

    def test_render_export_class(self, text_renderer, make_package_ir, make_export_ir):
        export = make_export_ir(class_name="WidgetBlueprint")
        ir = make_package_ir(exports=[export])
        result = text_renderer.render(ir, RenderOptions())
        assert "WidgetBlueprint" in result

    def test_render_export_serial_size(self, text_renderer, make_package_ir, make_export_ir):
        export = make_export_ir(serial_size=2048)
        ir = make_package_ir(exports=[export])
        result = text_renderer.render(ir, RenderOptions())
        assert "2048 bytes" in result

    def test_render_export_no_serial_size(self, text_renderer, make_package_ir, make_export_ir):
        export = make_export_ir(serial_size=0)
        ir = make_package_ir(exports=[export])
        result = text_renderer.render(ir, RenderOptions())
        assert "bytes" not in result.split("[Exports]")[1]

    def test_render_export_parent_class(self, text_renderer, make_package_ir, make_export_ir):
        export = make_export_ir()
        export.parent_class = "ACharacter"
        ir = make_package_ir(exports=[export])
        result = text_renderer.render(ir, RenderOptions())
        assert "Parent: ACharacter" in result

    def test_render_export_parse_status(self, text_renderer, make_package_ir, make_export_ir):
        export = make_export_ir(parse_status="partial")
        ir = make_package_ir(exports=[export])
        result = text_renderer.render(ir, RenderOptions())
        assert "Status: partial" in result

    def test_render_export_success_no_status(self, text_renderer, make_package_ir, make_export_ir):
        export = make_export_ir(parse_status="success")
        ir = make_package_ir(exports=[export])
        result = text_renderer.render(ir, RenderOptions())
        lines = result.split("\n")
        export_lines = [l for l in lines if "Status:" in l]
        assert len(export_lines) == 0

    def test_render_multiple_exports_sorted(self, text_renderer, make_package_ir, make_export_ir):
        e1 = make_export_ir(index=2, object_name="Second")
        e2 = make_export_ir(index=0, object_name="First")
        e3 = make_export_ir(index=1, object_name="Middle")
        ir = make_package_ir(exports=[e1, e2, e3])
        result = text_renderer.render(ir, RenderOptions())
        idx_first = result.index("[0] First")
        idx_middle = result.index("[1] Middle")
        idx_second = result.index("[2] Second")
        assert idx_first < idx_middle < idx_second

    def test_render_empty_export_list(self, text_renderer, make_package_ir):
        ir = make_package_ir(exports=[])
        result = text_renderer.render(ir, RenderOptions())
        assert "[Exports]" not in result


class TestTextRendererImport:
    def test_render_with_import(self, text_renderer, make_package_ir):
        ir = make_package_ir()
        ir.imports = [{"object_name": "CoreUObject", "object_class": "Package"}, {"object_name": "Engine", "object_class": "Package"}]
        result = text_renderer.render(ir, RenderOptions())
        assert "[Imports]" in result
        assert "CoreUObject" in result

    def test_render_import_sorted(self, text_renderer, make_package_ir):
        ir = make_package_ir()
        ir.imports = [{"object_name": "Zebra", "object_class": "Package"}, {"object_name": "Alpha", "object_class": "Package"}]
        result = text_renderer.render(ir, RenderOptions())
        idx_alpha = result.index("Alpha")
        idx_zebra = result.index("Zebra")
        assert idx_alpha < idx_zebra

    def test_render_no_imports(self, text_renderer, make_package_ir):
        ir = make_package_ir()
        result = text_renderer.render(ir, RenderOptions())
        assert "[Imports]" not in result


class TestTextRendererVariable:
    def test_render_with_variable(self, text_renderer, make_package_ir):
        var = VariableIR(name="Health", type="float", default_value="100.0")
        ir = make_package_ir(variables=[var])
        result = text_renderer.render(ir, RenderOptions())
        assert "[Variables]" in result
        assert "Health: float = 100.0" in result

    def test_render_variable_no_default(self, text_renderer, make_package_ir):
        var = VariableIR(name="Score", type="int", default_value=None)
        ir = make_package_ir(variables=[var])
        result = text_renderer.render(ir, RenderOptions())
        assert "Score: int" in result
        assert "Score: int =" not in result

    def test_render_variable_sorted(self, text_renderer, make_package_ir):
        vars_ = [VariableIR(name="Zebra", type="bool", default_value=None), VariableIR(name="Alpha", type="int", default_value=None)]
        ir = make_package_ir(variables=vars_)
        result = text_renderer.render(ir, RenderOptions())
        idx_alpha = result.index("Alpha")
        idx_zebra = result.index("Zebra")
        assert idx_alpha < idx_zebra

    def test_render_long_default_truncated(self, text_renderer, make_package_ir):
        long_value = "x" * 150
        var = VariableIR(name="LongVar", type="str", default_value=long_value)
        ir = make_package_ir(variables=[var])
        result = text_renderer.render(ir, RenderOptions())
        assert "..." in result
        assert "LongVar" in result

    def test_render_all_editor_variables_hidden_standard(self, text_renderer, make_package_ir):
        vars_ = [VariableIR(name="UbergraphPages", type="Array<int>", default_value="[]"), VariableIR(name="FunctionGraphs", type="Array<int>", default_value="[]")]
        ir = make_package_ir(variables=vars_)
        result = text_renderer.render(ir, RenderOptions(output_level="standard"))
        assert "[Variables]" not in result


class TestTextRendererGraph:
    def test_render_graph_section(self, text_renderer, make_package_ir, make_export_ir, make_graph_ir, make_node_ir):
        node = make_node_ir()
        graph = make_graph_ir(name="ExecGraph", nodes=[node])
        export = make_export_ir(graphs=[graph])
        ir = make_package_ir(exports=[export])
        result = text_renderer.render(ir, RenderOptions())
        assert "[Graph: ExecGraph]" in result
        assert "Nodes: 1" in result

    def test_render_graph_execution_chains(self, text_renderer, make_package_ir, make_export_ir, make_graph_ir, make_node_ir):
        node = make_node_ir()
        graph = make_graph_ir(name="FlowGraph", nodes=[node], execution_chains=[["EventBeginPlay", "PrintString", "Delay"]])
        export = make_export_ir(graphs=[graph])
        ir = make_package_ir(exports=[export])
        result = text_renderer.render(ir, RenderOptions())
        assert "Chain: EventBeginPlay -> PrintString -> Delay" in result

    def test_render_graph_execution_chains_limited(self, text_renderer, make_package_ir, make_export_ir, make_graph_ir, make_node_ir):
        node = make_node_ir()
        chains = [["A", "B"], ["C", "D"], ["E", "F"], ["G", "H"]]
        graph = make_graph_ir(name="MultiChain", nodes=[node], execution_chains=chains)
        export = make_export_ir(graphs=[graph])
        ir = make_package_ir(exports=[export])
        result = text_renderer.render(ir, RenderOptions())
        assert "+1 more chains" in result

    def test_render_graph_no_nodes_hidden_standard(self, text_renderer, make_package_ir, make_export_ir, make_graph_ir):
        from uasset_read.models.ir import NodeIR
        knot = NodeIR(node_guid="00000000000000000000000000000001", node_class="K2Node_Knot", node_comment=None, pins=[], execution_flow=[])
        graph = make_graph_ir(name="KnotOnly", nodes=[knot])
        export = make_export_ir(graphs=[graph])
        ir = make_package_ir(exports=[export])
        result = text_renderer.render(ir, RenderOptions(output_level="standard"))
        assert "KnotOnly" not in result

    def test_render_multiple_graphs(self, text_renderer, make_package_ir, make_export_ir, make_graph_ir, make_node_ir):
        n1 = make_node_ir()
        n2 = make_node_ir()
        g1 = make_graph_ir(name="Graph1", nodes=[n1])
        g2 = make_graph_ir(name="Graph2", nodes=[n2])
        export = make_export_ir(graphs=[g1, g2])
        ir = make_package_ir(exports=[export])
        result = text_renderer.render(ir, RenderOptions())
        assert "[Graph: Graph1]" in result
        assert "[Graph: Graph2]" in result


class TestTextRendererLinker:
    def test_render_linker_section(self, text_renderer, make_package_ir):
        lk = LinkerSummaryIR(has_linker=True, import_paths=["/Engine/Core", "/Engine/Engine"], export_paths=["/Game/Blueprints/BP_Test"])
        ir = make_package_ir()
        ir.linker = lk
        result = text_renderer.render(ir, RenderOptions())
        assert "[Linker]" in result
        assert "Imports: 2" in result

    def test_render_no_linker(self, text_renderer, make_package_ir):
        ir = make_package_ir()
        result = text_renderer.render(ir, RenderOptions())
        assert "[Linker]" not in result


class TestTextRendererBlueprint:
    def test_render_blueprint_parent_class(self, text_renderer, make_package_ir):
        bp = BlueprintIR(parent_class="AActor", description="")
        ir = make_package_ir()
        ir.blueprint = bp
        result = text_renderer.render(ir, RenderOptions())
        assert "[Blueprint]" in result
        assert "Parent Class: AActor" in result

    def test_render_blueprint_description(self, text_renderer, make_package_ir):
        bp = BlueprintIR(parent_class=None, description="My blueprint description")
        ir = make_package_ir()
        ir.blueprint = bp
        result = text_renderer.render(ir, RenderOptions())
        assert "Description: My blueprint description" in result

    def test_render_blueprint_long_description_truncated(self, text_renderer, make_package_ir):
        long_desc = "x" * 250
        bp = BlueprintIR(parent_class=None, description=long_desc)
        ir = make_package_ir()
        ir.blueprint = bp
        result = text_renderer.render(ir, RenderOptions())
        assert "..." in result

    def test_render_blueprint_interfaces(self, text_renderer, make_package_ir):
        bp = BlueprintIR(parent_class=None, interfaces=["IInterface1", "IInterface2", "IInterface3"])
        ir = make_package_ir()
        ir.blueprint = bp
        result = text_renderer.render(ir, RenderOptions())
        assert "Interfaces: 3" in result

    def test_render_blueprint_functions(self, text_renderer, make_package_ir):
        fn1 = BlueprintFunctionIR(name="BeginPlay", return_type="void", parameters=[])
        fn2 = BlueprintFunctionIR(name="Tick", return_type="void", parameters=[{"name": "DeltaTime"}, {"name": "FrameCount"}])
        bp = BlueprintIR(parent_class=None, functions=[fn1, fn2])
        ir = make_package_ir()
        ir.blueprint = bp
        result = text_renderer.render(ir, RenderOptions())
        assert "Functions:" in result
        assert "- BeginPlay" in result
        assert "- Tick" in result
        assert "Params: DeltaTime, FrameCount" in result

    def test_render_blueprint_functions_sorted(self, text_renderer, make_package_ir):
        fn1 = BlueprintFunctionIR(name="Zebra", return_type="void", parameters=[])
        fn2 = BlueprintFunctionIR(name="Alpha", return_type="void", parameters=[])
        bp = BlueprintIR(parent_class=None, functions=[fn1, fn2])
        ir = make_package_ir()
        ir.blueprint = bp
        result = text_renderer.render(ir, RenderOptions())
        idx_alpha = result.index("- Alpha")
        idx_zebra = result.index("- Zebra")
        assert idx_alpha < idx_zebra

    def test_render_blueprint_events(self, text_renderer, make_package_ir):
        ev1 = BlueprintEventIR(name="ReceiveBeginPlay", event_type="custom", parameters=[])
        ev2 = BlueprintEventIR(name="ReceiveTick", event_type="custom", parameters=[])
        bp = BlueprintIR(parent_class=None, events=[ev1, ev2])
        ir = make_package_ir()
        ir.blueprint = bp
        result = text_renderer.render(ir, RenderOptions())
        assert "Events:" in result
        assert "- ReceiveBeginPlay" in result

    def test_render_blueprint_components(self, text_renderer, make_package_ir):
        bp = BlueprintIR(parent_class=None, components=[{"name": "Comp1"}, {"name": "Comp2"}])
        ir = make_package_ir()
        ir.blueprint = bp
        result = text_renderer.render(ir, RenderOptions())
        assert "Components: 2" in result

    def test_render_no_blueprint(self, text_renderer, make_package_ir):
        ir = make_package_ir()
        result = text_renderer.render(ir, RenderOptions())
        assert "[Blueprint]" not in result


class TestTextRendererDecompiled:
    def test_render_decompiled_functions(self, text_renderer, make_package_ir):
        fn = DecompiledFunctionIR(name="MyFunc", signature="void MyFunc(int32 Param1)", cpp_code="// code", parameters=[], return_type="void")
        ir = make_package_ir()
        ir.decompiled_functions = [fn]
        result = text_renderer.render(ir, RenderOptions())
        assert "[Decompiled Functions]" in result
        assert "void MyFunc(int32 Param1)" in result

    def test_render_decompiled_sorted(self, text_renderer, make_package_ir):
        fn1 = DecompiledFunctionIR(name="ZFunc", signature="void ZFunc()", cpp_code="", parameters=[], return_type="void")
        fn2 = DecompiledFunctionIR(name="AFunc", signature="void AFunc()", cpp_code="", parameters=[], return_type="void")
        ir = make_package_ir()
        ir.decompiled_functions = [fn1, fn2]
        result = text_renderer.render(ir, RenderOptions())
        idx_a = result.index("AFunc")
        idx_z = result.index("ZFunc")
        assert idx_a < idx_z


class TestTextRendererExecutionChains:
    def test_render_execution_chains(self, text_renderer, make_package_ir):
        chain = ExecutionChainIR(event="ReceiveBeginPlay", chain=["ReceiveBeginPlay", "PrintString", "Delay"])
        ir = make_package_ir()
        ir.execution_chains = [chain]
        result = text_renderer.render(ir, RenderOptions())
        assert "[Execution Chains]" in result
        assert "ReceiveBeginPlay: ReceiveBeginPlay -> PrintString -> Delay" in result

    def test_render_long_chain_truncated(self, text_renderer, make_package_ir):
        chain = ExecutionChainIR(event="LongEvent", chain=["A", "B", "C", "D", "E", "F", "G"])
        ir = make_package_ir()
        ir.execution_chains = [chain]
        result = text_renderer.render(ir, RenderOptions())
        assert "... (7 total)" in result


class TestTextRendererDiagnostics:
    def test_render_diagnostics(self, text_renderer, make_package_ir):
        ir = make_package_ir()
        ir.diagnostics = ["Warning: something", "Info: detail"]
        result = text_renderer.render(ir, RenderOptions())
        assert "[Diagnostics]" in result
        assert "Warning: something" in result

    def test_render_diagnostics_dict(self, text_renderer, make_package_ir):
        ir = make_package_ir()
        ir.diagnostics = [{"message": "Offset mismatch at 0x100"}]
        result = text_renderer.render(ir, RenderOptions())
        assert "Offset mismatch at 0x100" in result

    def test_render_diagnostics_limited(self, text_renderer, make_package_ir):
        ir = make_package_ir()
        ir.diagnostics = [f"diag_{i}" for i in range(15)]
        result = text_renderer.render(ir, RenderOptions())
        assert "+5 more" in result


class TestTextRendererStatus:
    def test_render_success_status_hidden(self, text_renderer, make_package_ir):
        ir = make_package_ir()
        result = text_renderer.render(ir, RenderOptions())
        assert "Status:" not in result

    def test_render_partial_status(self, text_renderer, make_package_ir):
        ir = make_package_ir()
        ir.status = "partial"
        result = text_renderer.render(ir, RenderOptions())
        assert "Status: partial" in result

    def test_render_failed_status(self, text_renderer, make_package_ir):
        ir = make_package_ir()
        ir.status = "failed"
        ir.status_message = "Parse error at offset 0x100"
        result = text_renderer.render(ir, RenderOptions())
        assert "Status: failed" in result
        assert "Message: Parse error at offset 0x100" in result


class TestTextRendererRenderTo:
    def test_render_to_writes_to_stream(self, text_renderer, make_package_ir):
        ir = make_package_ir()
        writer = StringIO()
        text_renderer.render_to(ir, writer, RenderOptions())
        output = writer.getvalue()
        assert "TestPackage" in output

    def test_render_to_matches_render(self, text_renderer, make_package_ir, make_export_ir):
        export = make_export_ir(object_name="MatchTest")
        ir = make_package_ir(exports=[export])
        render_result = text_renderer.render(ir, RenderOptions())
        writer = StringIO()
        text_renderer.render_to(ir, writer, RenderOptions())
        render_to_result = writer.getvalue()
        assert render_result == render_to_result


class TestTextRendererAnimation:
    def test_render_anim_blueprint(self, text_renderer, make_package_ir):
        sm = BakedStateMachineIR(machine_name="WalkRun")
        abp = AnimBlueprintIR(baked_state_machines=[sm])
        ir = make_package_ir()
        ir.anim_blueprint = abp
        result = text_renderer.render(ir, RenderOptions())
        assert "[AnimBlueprint]" in result
        assert "State Machines: 1" in result
        assert "- WalkRun" in result

    def test_render_anim_sequence(self, text_renderer, make_package_ir):
        ans = AnimSequenceIR(notifies=[{"name": "FootStep"}])
        ir = make_package_ir()
        ir.anim_sequence = ans
        result = text_renderer.render(ir, RenderOptions())
        assert "[AnimSequence]" in result
        assert "Notifies: 1" in result

    def test_render_anim_montage(self, text_renderer, make_package_ir):
        amt = AnimMontageIR(composite_sections=[{"name": "Section1"}])
        ir = make_package_ir()
        ir.anim_montage = amt
        result = text_renderer.render(ir, RenderOptions())
        assert "[AnimMontage]" in result
        assert "Composite Sections: 1" in result


class TestTextRendererEdgeCases:
    def test_render_empty_package_name(self, text_renderer, make_package_ir):
        ir = make_package_ir(name="")
        result = text_renderer.render(ir, RenderOptions())
        assert "===  ===" in result

    def test_render_stable_output(self, text_renderer, make_package_ir, make_export_ir):
        ir = make_package_ir(name="StablePkg")
        r1 = text_renderer.render(ir, RenderOptions())
        r2 = text_renderer.render(ir, RenderOptions())
        assert r1 == r2

    def test_render_with_all_sections(self, text_renderer, make_package_ir, make_export_ir):
        lk = LinkerSummaryIR(has_linker=True, import_paths=["/Engine/Core"], export_paths=["/Game/BP"])
        fn = BlueprintFunctionIR(name="TestFunc", return_type="void", parameters=[])
        bp = BlueprintIR(parent_class="AActor", description="Test BP", functions=[fn])
        var = VariableIR(name="MyVar", type="float", default_value="1.0")
        export = make_export_ir(object_name="MainExport")
        dcf = DecompiledFunctionIR(name="DecompFunc", signature="void DecompFunc()", cpp_code="// code", parameters=[], return_type="void")
        ec = ExecutionChainIR(event="BeginPlay", chain=["BeginPlay", "EndPlay"])
        ir = make_package_ir(exports=[export])
        ir.header.package_flags = 0xFF
        ir.header.folder_name = "Content/Test"
        ir.linker = lk
        ir.blueprint = bp
        ir.variables = [var]
        ir.decompiled_functions = [dcf]
        ir.execution_chains = [ec]
        ir.diagnostics = ["All sections present"]
        result = text_renderer.render(ir, RenderOptions())
        assert "=== TestPackage ===" in result
        assert "[Linker]" in result
        assert "[Blueprint]" in result
        assert "[Variables]" in result
        assert "[Decompiled Functions]" in result
        assert "[Execution Chains]" in result
        assert "[Diagnostics]" in result
        assert "[Exports]" in result


# ---------------------------------------------------------------------------
# diff_single 测试
# ---------------------------------------------------------------------------


class TestDiffSingle:
    def test_same_file_no_diff(self):
        from uasset_read.core import diff_single
        assert callable(diff_single)

    def test_returns_str(self):
        from uasset_read.core import diff_single
        result = diff_single("nonexistent1.uasset", "nonexistent2.uasset")
        assert isinstance(result, str)

    def test_nonexistent_files_contain_error(self):
        from uasset_read.core import diff_single
        result = diff_single("nonexistent1.uasset", "nonexistent2.uasset")
        assert "FileNotFoundError" in result or "failed" in result

    def test_diff_header_present(self):
        from uasset_read.core import diff_single
        result = diff_single("foo.uasset", "bar.uasset")
        assert "a/foo.uasset" in result
        assert "b/bar.uasset" in result


# ---------------------------------------------------------------------------
# Text renderer 注册验证
# ---------------------------------------------------------------------------


class TestTextRendererRegistration:
    def test_text_renderer_registered(self):
        renderer = get_renderer("text")
        assert renderer is not None
        assert type(renderer).__name__ == "TextRenderer"

    def test_json_renderer_still_works(self):
        renderer = get_renderer("json")
        assert renderer is not None

    def test_markdown_renderer_still_works(self):
        renderer = get_renderer("markdown")
        assert renderer is not None


# ---------------------------------------------------------------------------
# Text 渲染器废弃警告测试
# ---------------------------------------------------------------------------


def _make_minimal_ir() -> PackageIR:
    header = PackageHeaderIR(
        package_name="Test", package_class="None", package_flags=0,
        total_export_count=0, total_import_count=0, ue_version="5.4.0",
    )
    return PackageIR(header=header, name_map=(), imports=[], exports=[], linker=None)


class TestTextDeprecated:
    def test_text_format_emits_deprecation_warning(self):
        ir = _make_minimal_ir()
        renderer = TextRenderer()
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            renderer.render(ir, RenderOptions())
        dep_warnings = [x for x in w if issubclass(x.category, DeprecationWarning)]
        assert len(dep_warnings) >= 1
        assert "markdown" in str(dep_warnings[0].message).lower()

    def test_markdown_format_no_deprecation_warning(self):
        ir = _make_minimal_ir()
        renderer = MarkdownRenderer()
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            renderer.render(ir, RenderOptions())
        dep_warnings = [x for x in w if issubclass(x.category, DeprecationWarning)]
        assert len(dep_warnings) == 0

    def test_text_renderer_still_works(self):
        ir = _make_minimal_ir()
        renderer = TextRenderer()
        with warnings.catch_warnings(record=True):
            warnings.simplefilter("always")
            result = renderer.render(ir, RenderOptions())
        assert "=== Test ===" in result


# ===========================================================================
# MarkdownRenderer 测试 (test_markdown_renderer)
# ===========================================================================


class TestMarkdownRendererBasicMD:
    def test_render_returns_string(self, md_renderer, make_package_ir):
        ir = make_package_ir()
        result = md_renderer.render(ir, RenderOptions())
        assert isinstance(result, str)
        assert len(result) > 0

    def test_render_includes_package_name(self, md_renderer, make_package_ir):
        ir = make_package_ir(name="TestBP")
        result = md_renderer.render(ir, RenderOptions())
        assert "# TestBP" in result

    def test_render_includes_asset_overview(self, md_renderer, make_package_ir):
        ir = make_package_ir()
        result = md_renderer.render(ir, RenderOptions())
        assert "## Asset Overview" in result
        assert "| Field | Value |" in result

    def test_render_overview_contains_metadata(self, md_renderer, make_package_ir):
        ir = make_package_ir(name="PkgName")
        result = md_renderer.render(ir, RenderOptions())
        assert "PkgName" in result
        assert "| Package |" in result
        assert "| Class |" in result

    def test_render_empty_content(self, md_renderer, make_package_ir):
        ir = make_package_ir(exports=[])
        result = md_renderer.render(ir, RenderOptions())
        assert isinstance(result, str)
        assert "## Asset Overview" in result

    def test_format_name(self, md_renderer):
        assert md_renderer.format_name == "markdown"

    def test_package_name_with_slash(self, md_renderer, make_package_ir):
        ir = make_package_ir(name="Game/Characters/BP_Hero")
        result = md_renderer.render(ir, RenderOptions())
        assert "# BP_Hero" in result
        assert "Game/Characters/BP_Hero" in result


class TestMarkdownRendererExportsMD:
    def test_blueprint_export_included(self, md_renderer, make_package_ir, make_export_ir):
        export = make_export_ir(object_name="BP_TestCharacter_C")
        ir = make_package_ir(exports=[export])
        result = md_renderer.render(ir, RenderOptions())
        assert "## Exports" in result
        assert "BP_TestCharacter_C" in result

    def test_non_blueprint_export_excluded(self, md_renderer, make_package_ir, make_export_ir):
        export = make_export_ir(object_name="SomeData", class_name="DataTable")
        ir = make_package_ir(exports=[export])
        result = md_renderer.render(ir, RenderOptions())
        assert "## Exports" not in result
        assert "SomeData" not in result

    def test_export_with_graphs_shown(self, md_renderer, make_package_ir, make_export_ir, make_graph_ir):
        graph = make_graph_ir(name="EventGraph")
        export = make_export_ir(object_name="TestExport", class_name="SomeClass", graphs=[graph])
        ir = make_package_ir(exports=[export])
        result = md_renderer.render(ir, RenderOptions())
        assert "## Exports" in result
        assert "TestExport" in result

    def test_export_table_columns(self, md_renderer, make_package_ir, make_export_ir):
        export = make_export_ir(object_name="BP_Test_C", serial_size=2048)
        ir = make_package_ir(exports=[export])
        result = md_renderer.render(ir, RenderOptions())
        assert "| Name | Class | Size | Properties |" in result
        assert "2048" in result

    def test_editor_node_class_excluded(self, md_renderer, make_package_ir, make_export_ir):
        export = make_export_ir(object_name="K2Node_Knot_C", class_name="K2Node_Knot")
        ir = make_package_ir(exports=[export])
        result = md_renderer.render(ir, RenderOptions())
        assert "## Exports" not in result

    def test_multiple_exports(self, md_renderer, make_package_ir, make_export_ir):
        e1 = make_export_ir(index=0, object_name="BP_First_C")
        e2 = make_export_ir(index=1, object_name="BP_Second_C")
        ir = make_package_ir(exports=[e1, e2])
        result = md_renderer.render(ir, RenderOptions())
        assert "BP_First_C" in result
        assert "BP_Second_C" in result
        assert result.index("BP_First_C") < result.index("BP_Second_C")


class TestMarkdownRendererGraphsMD:
    def test_graph_heading(self, md_renderer, make_package_ir, make_export_ir, make_graph_ir):
        graph = make_graph_ir(name="EventGraph")
        export = make_export_ir(graphs=[graph])
        ir = make_package_ir(exports=[export])
        result = md_renderer.render(ir, RenderOptions())
        assert "## Graph: EventGraph" in result

    def test_graph_node_count(self, md_renderer, make_package_ir, make_export_ir, make_graph_ir, make_node_ir):
        n1 = make_node_ir()
        n2 = make_node_ir()
        graph = make_graph_ir(name="G", nodes=[n1, n2])
        export = make_export_ir(graphs=[graph])
        ir = make_package_ir(exports=[export])
        result = md_renderer.render(ir, RenderOptions())
        assert "**Nodes**: 2" in result

    def test_mermaid_code_block(self, md_renderer, make_package_ir, make_export_ir, make_graph_ir, make_node_ir):
        node = make_node_ir(node_comment="MyNode")
        graph = make_graph_ir(name="EventGraph", nodes=[node])
        export = make_export_ir(graphs=[graph])
        ir = make_package_ir(exports=[export])
        result = md_renderer.render(ir, RenderOptions())
        assert "```mermaid" in result
        assert "graph TD" in result

    def test_mermaid_uses_node_comment(self, md_renderer, make_package_ir, make_export_ir, make_graph_ir, make_node_ir):
        node = make_node_ir(node_comment="BeginPlay")
        graph = make_graph_ir(nodes=[node])
        export = make_export_ir(graphs=[graph])
        ir = make_package_ir(exports=[export])
        result = md_renderer.render(ir, RenderOptions())
        assert "BeginPlay" in result

    def test_mermaid_fallback_to_node_class(self, md_renderer, make_package_ir, make_export_ir, make_graph_ir, make_node_ir):
        node = make_node_ir(node_comment=None, node_class="K2Node_Event")
        graph = make_graph_ir(nodes=[node])
        export = make_export_ir(graphs=[graph])
        ir = make_package_ir(exports=[export])
        result = md_renderer.render(ir, RenderOptions())
        assert "K2Node_Event" in result

    def test_mermaid_edges_from_pin_links(self, md_renderer, make_package_ir, make_export_ir, make_graph_ir):
        pin_b = PinIR(pin_name="In", pin_type="exec", linked_to=[], direction="input", default_value=None, pin_guid="22222222222222222222222222222222")
        node_b = NodeIR(node_guid="bbbbbbbb000000000000000000000002", node_class="K2Node_Event", node_comment="NodeB", pins=[pin_b], execution_flow=[])
        pin_a = PinIR(pin_name="Out", pin_type="exec", linked_to=["22222222222222222222222222222222"], direction="output", default_value=None, pin_guid="11111111111111111111111111111111")
        node_a = NodeIR(node_guid="aaaaaaaa000000000000000000000001", node_class="K2Node_Event", node_comment="NodeA", pins=[pin_a], execution_flow=[])
        graph = make_graph_ir(nodes=[node_a, node_b])
        export = make_export_ir(graphs=[graph])
        ir = make_package_ir(exports=[export])
        result = md_renderer.render(ir, RenderOptions())
        assert "aaaaaaaa --> bbbbbbbb" in result

    def test_mermaid_self_loop_filtered(self, md_renderer, make_package_ir, make_export_ir, make_graph_ir):
        pin_self = PinIR(pin_name="Loop", pin_type="exec", linked_to=["self_pin_guid_self_pin_guid_self"], direction="output", default_value=None, pin_guid="self_pin_guid_self_pin_guid_self")
        node_self = NodeIR(node_guid="self_node_self_node_self_node_no", node_class="K2Node_Knot", node_comment="SelfLoop", pins=[pin_self], execution_flow=[])
        graph = make_graph_ir(nodes=[node_self])
        export = make_export_ir(graphs=[graph])
        ir = make_package_ir(exports=[export])
        result = md_renderer.render(ir, RenderOptions())
        assert "self_nod" not in result or "-->" not in result.split("self_nod")[0].split("\n")[-1]

    def test_empty_graph_no_mermaid(self, md_renderer, make_package_ir, make_export_ir, make_graph_ir):
        graph = make_graph_ir(name="EmptyGraph", nodes=[])
        export = make_export_ir(graphs=[graph])
        ir = make_package_ir(exports=[export])
        result = md_renderer.render(ir, RenderOptions())
        assert "```mermaid" not in result

    def test_graph_execution_chains_count(self, md_renderer, make_package_ir, make_export_ir, make_graph_ir):
        graph = make_graph_ir(name="EventGraph", execution_chains=[["A", "B"], ["C", "D"]])
        export = make_export_ir(graphs=[graph])
        ir = make_package_ir(exports=[export])
        result = md_renderer.render(ir, RenderOptions())
        assert "**Execution Chains**: 2" in result


class TestMarkdownRendererPropertiesMD:
    def test_properties_table(self, md_renderer, make_package_ir, make_export_ir, make_graph_ir):
        prop = PropertyIR(name="Health", type="FloatProperty", value=100.0, array_index=0, guid=None)
        graph = make_graph_ir(nodes=[])
        export = make_export_ir(properties=[prop], graphs=[graph])
        ir = make_package_ir(exports=[export])
        result = md_renderer.render(ir, RenderOptions())
        assert "### Properties" in result
        assert "| Name | Type | Value |" in result
        assert "Health" in result

    def test_editor_property_filtered(self, md_renderer, make_package_ir, make_export_ir, make_graph_ir):
        props = [PropertyIR(name="NodePosX", type="int", value=100, array_index=0, guid=None), PropertyIR(name="GameProp", type="int", value=42, array_index=0, guid=None)]
        graph = make_graph_ir(nodes=[])
        export = make_export_ir(properties=props, graphs=[graph])
        ir = make_package_ir(exports=[export])
        result = md_renderer.render(ir, RenderOptions())
        assert "NodePosX" not in result
        assert "GameProp" in result

    def test_all_editor_properties_no_section(self, md_renderer, make_package_ir, make_export_ir, make_graph_ir):
        props = [PropertyIR(name="NodePosX", type="int", value=0, array_index=0, guid=None), PropertyIR(name="NodePosY", type="int", value=0, array_index=0, guid=None)]
        graph = make_graph_ir(nodes=[])
        export = make_export_ir(properties=props, graphs=[graph])
        ir = make_package_ir(exports=[export])
        result = md_renderer.render(ir, RenderOptions())
        assert "### Properties" not in result

    def test_null_property_value(self, md_renderer, make_package_ir, make_export_ir, make_graph_ir):
        prop = PropertyIR(name="OptionalRef", type="ObjectProperty", value=None, array_index=0, guid=None)
        graph = make_graph_ir(nodes=[])
        export = make_export_ir(properties=[prop], graphs=[graph])
        ir = make_package_ir(exports=[export])
        result = md_renderer.render(ir, RenderOptions())
        assert "null" in result

    def test_properties_rendered_without_graphs(self, md_renderer, make_package_ir, make_export_ir):
        prop = PropertyIR(name="Health", type="FloatProperty", value=100.0, array_index=0, guid=None)
        export = make_export_ir(object_name="BP_Test_C", properties=[prop], graphs=[])
        ir = make_package_ir(exports=[export])
        result = md_renderer.render(ir, RenderOptions())
        assert "### Properties" in result
        assert "Health" in result


class TestMarkdownRendererVariablesMD:
    def test_variables_section(self, md_renderer, make_package_ir):
        var = VariableIR(name="Health", type="FloatProperty", default_value="100.0")
        ir = make_package_ir(variables=[var])
        result = md_renderer.render(ir, RenderOptions())
        assert "## Variables" in result
        assert "| Name | Type | Default Value |" in result

    def test_editor_variable_filtered(self, md_renderer, make_package_ir):
        var = VariableIR(name="UbergraphPages", type="ArrayProperty", default_value="[]")
        ir = make_package_ir(variables=[var])
        result = md_renderer.render(ir, RenderOptions())
        assert "## Variables" not in result

    def test_mixed_variables_filtered_correctly(self, md_renderer, make_package_ir):
        vars_ = [VariableIR(name="UbergraphPages", type="ArrayProperty", default_value="[]"), VariableIR(name="Health", type="FloatProperty", default_value="100.0")]
        ir = make_package_ir(variables=vars_)
        result = md_renderer.render(ir, RenderOptions())
        assert "Health" in result
        assert "UbergraphPages" not in result

    def test_no_variables_no_section(self, md_renderer, make_package_ir):
        ir = make_package_ir(variables=[])
        result = md_renderer.render(ir, RenderOptions())
        assert "## Variables" not in result


class TestMarkdownRendererBlueprintDetailsMD:
    def test_blueprint_parent_class(self, md_renderer, make_package_ir):
        ir_obj = make_package_ir()
        ir_obj.blueprint = BlueprintIR(parent_class="Character", description="Test blueprint")
        result = md_renderer.render(ir_obj, RenderOptions())
        assert "## Blueprint Details" in result
        assert "Character" in result

    def test_blueprint_description(self, md_renderer, make_package_ir):
        ir_obj = make_package_ir()
        ir_obj.blueprint = BlueprintIR(parent_class="Actor", description="A test description")
        result = md_renderer.render(ir_obj, RenderOptions())
        assert "A test description" in result

    def test_blueprint_interfaces(self, md_renderer, make_package_ir):
        ir_obj = make_package_ir()
        ir_obj.blueprint = BlueprintIR(parent_class="Actor", interfaces=[{"name": "IInteractable"}])
        result = md_renderer.render(ir_obj, RenderOptions())
        assert "IInteractable" in result

    def test_no_blueprint_no_details(self, md_renderer, make_package_ir):
        ir = make_package_ir()
        result = md_renderer.render(ir, RenderOptions())
        assert "## Blueprint Details" not in result


class TestMarkdownRendererEventGraphMD:
    def test_event_graph_section(self, md_renderer, make_package_ir):
        ir_obj = make_package_ir()
        event = BlueprintEventIR(name="ReceiveBeginPlay", event_type="custom", parameters=[])
        ir_obj.blueprint = BlueprintIR(parent_class="Actor", events=[event])
        result = md_renderer.render(ir_obj, RenderOptions())
        assert "## Event Graph" in result
        assert "### ReceiveBeginPlay" in result

    def test_event_graph_cpp_block(self, md_renderer, make_package_ir):
        ir_obj = make_package_ir()
        event = BlueprintEventIR(name="ReceiveTick", event_type="custom", parameters=[])
        ir_obj.blueprint = BlueprintIR(parent_class="Actor", events=[event])
        result = md_renderer.render(ir_obj, RenderOptions())
        assert "```cpp" in result

    def test_event_with_decompiled_function(self, md_renderer, make_package_ir):
        decompiled = DecompiledFunctionIR(name="ReceiveBeginPlay", signature="void ATestActor::ReceiveBeginPlay()", cpp_code="    Super::ReceiveBeginPlay();\n    // custom logic", parameters=[], return_type="void")
        event = BlueprintEventIR(name="ReceiveBeginPlay", event_type="custom", parameters=[])
        ir_obj = make_package_ir()
        ir_obj.blueprint = BlueprintIR(parent_class="Actor", events=[event])
        ir_obj.decompiled_functions = [decompiled]
        result = md_renderer.render(ir_obj, RenderOptions())
        assert "ATestActor::ReceiveBeginPlay()" in result

    def test_event_with_execution_chain(self, md_renderer, make_package_ir):
        event = BlueprintEventIR(name="ReceiveBeginPlay", event_type="custom", parameters=[])
        chain = ExecutionChainIR(event="ReceiveBeginPlay", chain=["BeginPlay", "SpawnActor", "PlaySound"])
        ir_obj = make_package_ir()
        ir_obj.blueprint = BlueprintIR(parent_class="Actor", events=[event])
        ir_obj.execution_chains = [chain]
        result = md_renderer.render(ir_obj, RenderOptions())
        assert "Execution Chain:" in result
        assert "BeginPlay -> SpawnActor -> PlaySound" in result

    def test_execution_chain_standalone(self, md_renderer, make_package_ir):
        chain = ExecutionChainIR(event="CustomEvent", chain=["Step1", "Step2"])
        ir_obj = make_package_ir()
        ir_obj.execution_chains = [chain]
        result = md_renderer.render(ir_obj, RenderOptions())
        assert "### CustomEvent" in result
        assert "Step1 -> Step2" in result


class TestMarkdownRendererFunctionsMD:
    def test_decompiled_function_section(self, md_renderer, make_package_ir):
        func = DecompiledFunctionIR(name="DoSomething", signature="void ATestActor::DoSomething(float Value)", cpp_code="    Health = Value;", parameters=[{"name": "Value", "param_type": "float"}], return_type="void")
        ir_obj = make_package_ir()
        ir_obj.decompiled_functions = [func]
        result = md_renderer.render(ir_obj, RenderOptions())
        assert "## Functions" in result
        assert "### DoSomething" in result

    def test_function_parameter_table(self, md_renderer, make_package_ir):
        func = DecompiledFunctionIR(name="CalcDamage", signature="", cpp_code="", parameters=[{"name": "Base", "param_type": "float"}, {"name": "Multiplier", "param_type": "float", "default_value": "1.0"}], return_type="float")
        ir_obj = make_package_ir()
        ir_obj.decompiled_functions = [func]
        result = md_renderer.render(ir_obj, RenderOptions())
        assert "| Parameter | Type | Default |" in result
        assert "Base" in result
        assert "1.0" in result

    def test_function_without_signature_generates_one(self, md_renderer, make_package_ir):
        func = DecompiledFunctionIR(name="GenSig", signature="", cpp_code="", parameters=[{"name": "X", "param_type": "int"}], return_type="void")
        ir_obj = make_package_ir()
        ir_obj.decompiled_functions = [func]
        result = md_renderer.render(ir_obj, RenderOptions())
        assert "**Signature:** `void GenSig(int X)`" in result

    def test_function_heuristic_warning(self, md_renderer, make_package_ir):
        func = DecompiledFunctionIR(name="HeuristicFunc", signature="void HeuristicFunc()", cpp_code="    // code", parameters=[], return_type="void", bytecode_confidence="heuristic")
        ir_obj = make_package_ir()
        ir_obj.decompiled_functions = [func]
        result = md_renderer.render(ir_obj, RenderOptions())
        assert "[!WARNING]" in result
        assert "启发式恢复" in result

    def test_no_functions_no_section(self, md_renderer, make_package_ir):
        ir = make_package_ir()
        result = md_renderer.render(ir, RenderOptions())
        assert "## Functions" not in result


class TestMarkdownRendererAssetRegistryMD:
    def test_asset_registry_section(self, md_renderer, make_package_ir):
        ir_obj = make_package_ir()
        ir_obj.asset_registry_data = {"objects": [{"object_path": "/Game/Characters/BP_Hero", "object_class_name": "BlueprintGeneratedClass", "tags": {"Source": "Editor"}}]}
        result = md_renderer.render(ir_obj, RenderOptions())
        assert "## Asset Registry Data" in result
        assert "/Game/Characters/BP_Hero" in result

    def test_no_asset_registry_no_section(self, md_renderer, make_package_ir):
        ir = make_package_ir()
        result = md_renderer.render(ir, RenderOptions())
        assert "## Asset Registry Data" not in result

    def test_empty_asset_registry_no_section(self, md_renderer, make_package_ir):
        ir_obj = make_package_ir()
        ir_obj.asset_registry_data = {"objects": []}
        result = md_renderer.render(ir_obj, RenderOptions())
        assert "## Asset Registry Data" not in result


class TestMarkdownRendererDiagnosticsMD:
    def test_diagnostics_section(self, md_renderer, make_package_ir):
        class FakeDiag:
            def to_dict(self):
                return {"kind": "offset_mismatch", "module": "export[0]", "object_name": "BP_Test", "field": "SerialSize", "error": "expected 1024, got 2048"}
        ir_obj = make_package_ir()
        ir_obj.diagnostics = [FakeDiag()]
        result = md_renderer.render(ir_obj, RenderOptions())
        assert "## 诊断信息" in result
        assert "offset_mismatch" in result

    def test_no_diagnostics_no_section(self, md_renderer, make_package_ir):
        ir = make_package_ir()
        result = md_renderer.render(ir, RenderOptions())
        assert "## 诊断信息" not in result


class TestMarkdownRendererEdgeCasesMD:
    def test_special_characters_escaped(self, md_renderer, make_package_ir, make_export_ir):
        export = make_export_ir(object_name="BP|Test_C")
        ir = make_package_ir(exports=[export])
        result = md_renderer.render(ir, RenderOptions())
        assert "BP\\|Test_C" in result

    def test_empty_graph_name(self, md_renderer, make_package_ir, make_export_ir, make_graph_ir):
        graph = make_graph_ir(name="")
        export = make_export_ir(graphs=[graph])
        ir = make_package_ir(exports=[export])
        result = md_renderer.render(ir, RenderOptions())
        assert "## Graph: " in result

    def test_empty_node_comment_and_class(self, md_renderer, make_package_ir, make_export_ir, make_graph_ir, make_node_ir):
        node = make_node_ir(node_comment=None, node_class="")
        graph = make_graph_ir(nodes=[node])
        export = make_export_ir(graphs=[graph])
        ir = make_package_ir(exports=[export])
        result = md_renderer.render(ir, RenderOptions())
        assert isinstance(result, str)

    def test_long_property_value_truncated(self, md_renderer, make_package_ir, make_export_ir, make_graph_ir):
        long_val = "A" * 100
        prop = PropertyIR(name="LongProp", type="StrProperty", value=long_val, array_index=0, guid=None)
        graph = make_graph_ir(nodes=[])
        export = make_export_ir(properties=[prop], graphs=[graph])
        ir = make_package_ir(exports=[export])
        result = md_renderer.render(ir, RenderOptions())
        assert "A" * 50 in result
        assert "A" * 51 not in result
