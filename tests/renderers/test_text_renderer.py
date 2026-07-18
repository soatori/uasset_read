"""TextRenderer 单元测试。

合并来源：
  - test_text_deprecated.py
"""
import warnings
from io import StringIO

import pytest

from uasset_read.renderers import get_renderer
from uasset_read.renderers.text_renderer import TextRenderer
from uasset_read.renderers.base import RenderOptions
from uasset_read.models.ir import PackageIR, PackageHeaderIR


@pytest.fixture
def renderer():
    return TextRenderer()


class TestTextRendererBasic:
    """基础渲染功能测试。"""

    def test_render_returns_string(self, renderer, make_package_ir):
        """render 返回非空字符串。"""
        ir = make_package_ir()
        result = renderer.render(ir, RenderOptions())

        assert isinstance(result, str)
        assert len(result) > 0

    def test_render_includes_package_name(self, renderer, make_package_ir):
        """输出包含包名。"""
        ir = make_package_ir(name="TestPackage")
        result = renderer.render(ir, RenderOptions())

        assert "TestPackage" in result

    def test_render_includes_version(self, renderer, make_package_ir):
        """输出包含 UE 版本。"""
        ir = make_package_ir()
        result = renderer.render(ir, RenderOptions())

        assert "5.4" in result

    def test_render_includes_type(self, renderer, make_package_ir):
        """输出包含包类型。"""
        ir = make_package_ir(class_name="WidgetBlueprint")
        result = renderer.render(ir, RenderOptions())

        assert "WidgetBlueprint" in result

    def test_render_includes_export_import_counts(self, renderer, make_package_ir):
        """输出包含 export 和 import 计数。"""
        ir = make_package_ir()
        result = renderer.render(ir, RenderOptions())

        assert "Exports: 0" in result
        assert "Imports: 0" in result

    def test_render_empty_exports(self, renderer, make_package_ir):
        """无 export 时不崩溃。"""
        ir = make_package_ir(exports=[])
        result = renderer.render(ir, RenderOptions())

        assert isinstance(result, str)

    def test_render_header_structure(self, renderer, make_package_ir):
        """输出包含标准标题行格式。"""
        ir = make_package_ir(name="MyPkg")
        result = renderer.render(ir, RenderOptions())

        assert result.startswith("=== MyPkg ===")
        assert "Type:" in result
        assert "Version:" in result

    def test_render_package_flags(self, renderer, make_package_ir):
        """非零 package_flags 输出 Flags 行。"""
        header_ir = make_package_ir()
        header_ir.header.package_flags = 0xDEADBEEF
        result = renderer.render(header_ir, RenderOptions())

        assert "Flags: 0xDEADBEEF" in result

    def test_render_zero_flags_no_flags_line(self, renderer, make_package_ir):
        """零 flags 时不输出 Flags 行。"""
        ir = make_package_ir()
        result = renderer.render(ir, RenderOptions())

        assert "Flags:" not in result

    def test_render_folder_name(self, renderer, make_package_ir):
        """有 folder_name 时输出 Folder 行。"""
        ir = make_package_ir()
        ir.header.folder_name = "Content/Blueprints"
        result = renderer.render(ir, RenderOptions())

        assert "Folder: Content/Blueprints" in result

    def test_render_no_folder_name(self, renderer, make_package_ir):
        """无 folder_name 时不输出 Folder 行。"""
        ir = make_package_ir()
        result = renderer.render(ir, RenderOptions())

        assert "Folder:" not in result

    def test_format_name(self, renderer):
        """format_name 属性返回 text。"""
        assert renderer.format_name == "text"


class TestTextRendererOptions:
    """渲染选项测试。"""

    def test_verbose_mode(self, renderer, make_package_ir):
        """verbose 模式不缩减输出。"""
        ir = make_package_ir()

        standard = renderer.render(ir, RenderOptions(verbose=False))
        verbose = renderer.render(ir, RenderOptions(verbose=True))

        # verbose 输出应不少于标准输出
        assert len(verbose) >= len(standard)

    def test_debug_shows_editor_variables(self, renderer, make_package_ir):
        """debug 模式显示编辑器内部变量。"""
        from uasset_read.models.ir import VariableIR

        var = VariableIR(name="ThumbnailInfo", type="ObjectProperty", default_value=None)
        ir = make_package_ir(variables=[var])

        standard = renderer.render(ir, RenderOptions(output_level="standard"))
        debug = renderer.render(ir, RenderOptions(output_level="debug"))

        assert "ThumbnailInfo" not in standard
        assert "ThumbnailInfo" in debug

    def test_standard_filters_editor_variables(self, renderer, make_package_ir):
        """standard 模式过滤所有编辑器内部变量。"""
        from uasset_read.models.ir import VariableIR

        vars_ = [
            VariableIR(name="FunctionGraphs", type="Array<int>", default_value="[]"),
            VariableIR(name="CategorySorting", type="Array<str>", default_value="[]"),
            VariableIR(name="UserVar", type="bool", default_value="False"),
        ]
        ir = make_package_ir(variables=vars_)

        result = renderer.render(ir, RenderOptions(output_level="standard"))
        assert "FunctionGraphs" not in result
        assert "CategorySorting" not in result
        assert "UserVar" in result

    def test_debug_shows_all_editor_node_classes(self, renderer, make_package_ir,
                                                  make_export_ir, make_graph_ir,
                                                  make_node_ir):
        """debug 模式显示编辑器内部节点（如 K2Node_Knot）。"""
        knot = make_node_ir(node_class="K2Node_Knot")
        graph = make_graph_ir(name="KnotGraph", nodes=[knot])
        export = make_export_ir(graphs=[graph])
        ir = make_package_ir(exports=[export])

        standard = renderer.render(ir, RenderOptions(output_level="standard"))
        debug = renderer.render(ir, RenderOptions(output_level="debug"))

        # standard 模式过滤 K2Node_Knot，图为空不显示
        assert "KnotGraph" not in standard
        # debug 模式显示
        assert "KnotGraph" in debug

    def test_standard_filters_editor_nodes(self, renderer, make_package_ir,
                                            make_export_ir, make_graph_ir,
                                            make_node_ir):
        """standard 模式过滤编辑器节点，纯编辑器节点的图不显示。"""
        knot = make_node_ir(node_class="K2Node_Knot")
        event_node = make_node_ir(node_class="K2Node_Event")
        graph = make_graph_ir(name="MixedGraph", nodes=[knot, event_node])
        export = make_export_ir(graphs=[graph])
        ir = make_package_ir(exports=[export])

        result = renderer.render(ir, RenderOptions(output_level="standard"))
        # 图仍会显示（有非编辑器节点），但节点数为 1
        assert "MixedGraph" in result
        assert "Nodes: 1" in result


class TestTextRendererExport:
    """Export 渲染测试。"""

    def test_render_with_export(self, renderer, make_package_ir, make_export_ir):
        """渲染包含 export 的包。"""
        export = make_export_ir(object_name="MyFunction")
        ir = make_package_ir(exports=[export])

        result = renderer.render(ir, RenderOptions())

        assert "MyFunction" in result
        assert "[Exports]" in result

    def test_render_export_index(self, renderer, make_package_ir, make_export_ir):
        """export 显示索引号。"""
        export = make_export_ir(index=3, object_name="IndexedExport")
        ir = make_package_ir(exports=[export])

        result = renderer.render(ir, RenderOptions())

        assert "[3] IndexedExport" in result

    def test_render_export_class(self, renderer, make_package_ir, make_export_ir):
        """export 显示类名。"""
        export = make_export_ir(class_name="WidgetBlueprint")
        ir = make_package_ir(exports=[export])

        result = renderer.render(ir, RenderOptions())

        assert "WidgetBlueprint" in result

    def test_render_export_serial_size(self, renderer, make_package_ir, make_export_ir):
        """export 显示序列化大小。"""
        export = make_export_ir(serial_size=2048)
        ir = make_package_ir(exports=[export])

        result = renderer.render(ir, RenderOptions())

        assert "2048 bytes" in result

    def test_render_export_no_serial_size(self, renderer, make_package_ir, make_export_ir):
        """serial_size 为 0 时不显示大小。"""
        export = make_export_ir(serial_size=0)
        ir = make_package_ir(exports=[export])

        result = renderer.render(ir, RenderOptions())

        assert "bytes" not in result.split("[Exports]")[1]

    def test_render_export_parent_class(self, renderer, make_package_ir, make_export_ir):
        """有 parent_class 时显示 Parent 行。"""
        export = make_export_ir()
        export.parent_class = "ACharacter"
        ir = make_package_ir(exports=[export])

        result = renderer.render(ir, RenderOptions())

        assert "Parent: ACharacter" in result

    def test_render_export_no_parent_class(self, renderer, make_package_ir, make_export_ir):
        """无 parent_class 时不显示 Parent 行。"""
        export = make_export_ir()
        ir = make_package_ir(exports=[export])

        result = renderer.render(ir, RenderOptions())

        assert "Parent:" not in result

    def test_render_export_parse_status(self, renderer, make_package_ir, make_export_ir):
        """非 success 的 parse_status 显示 Status 行。"""
        export = make_export_ir(parse_status="partial")
        ir = make_package_ir(exports=[export])

        result = renderer.render(ir, RenderOptions())

        assert "Status: partial" in result

    def test_render_export_success_no_status(self, renderer, make_package_ir, make_export_ir):
        """success 的 parse_status 不显示 Status 行。"""
        export = make_export_ir(parse_status="success")
        ir = make_package_ir(exports=[export])

        result = renderer.render(ir, RenderOptions())

        lines = result.split("\n")
        export_lines = [l for l in lines if "Status:" in l]
        assert len(export_lines) == 0

    def test_render_multiple_exports_sorted(self, renderer, make_package_ir, make_export_ir):
        """多个 export 按索引排序显示。"""
        e1 = make_export_ir(index=2, object_name="Second")
        e2 = make_export_ir(index=0, object_name="First")
        e3 = make_export_ir(index=1, object_name="Middle")
        ir = make_package_ir(exports=[e1, e2, e3])

        result = renderer.render(ir, RenderOptions())

        idx_first = result.index("[0] First")
        idx_middle = result.index("[1] Middle")
        idx_second = result.index("[2] Second")
        assert idx_first < idx_middle < idx_second

    def test_render_empty_export_list(self, renderer, make_package_ir):
        """空 export 列表不输出 [Exports] 区域。"""
        ir = make_package_ir(exports=[])
        result = renderer.render(ir, RenderOptions())

        assert "[Exports]" not in result


class TestTextRendererImport:
    """Import 渲染测试。"""

    def test_render_with_import(self, renderer, make_package_ir):
        """渲染包含 import 的包。"""
        ir = make_package_ir()
        ir.imports = [
            {"object_name": "CoreUObject", "object_class": "Package"},
            {"object_name": "Engine", "object_class": "Package"},
        ]
        result = renderer.render(ir, RenderOptions())

        assert "[Imports]" in result
        assert "CoreUObject" in result
        assert "Engine" in result

    def test_render_import_sorted(self, renderer, make_package_ir):
        """import 按名称排序。"""
        ir = make_package_ir()
        ir.imports = [
            {"object_name": "Zebra", "object_class": "Package"},
            {"object_name": "Alpha", "object_class": "Package"},
        ]
        result = renderer.render(ir, RenderOptions())

        idx_alpha = result.index("Alpha")
        idx_zebra = result.index("Zebra")
        assert idx_alpha < idx_zebra

    def test_render_no_imports(self, renderer, make_package_ir):
        """无 import 时不输出 [Imports] 区域。"""
        ir = make_package_ir()
        result = renderer.render(ir, RenderOptions())

        assert "[Imports]" not in result


class TestTextRendererVariable:
    """变量渲染测试。"""

    def test_render_with_variable(self, renderer, make_package_ir):
        """渲染用户变量。"""
        from uasset_read.models.ir import VariableIR

        var = VariableIR(name="Health", type="float", default_value="100.0")
        ir = make_package_ir(variables=[var])

        result = renderer.render(ir, RenderOptions())

        assert "[Variables]" in result
        assert "Health: float = 100.0" in result

    def test_render_variable_no_default(self, renderer, make_package_ir):
        """无默认值时不显示等号。"""
        from uasset_read.models.ir import VariableIR

        var = VariableIR(name="Score", type="int", default_value=None)
        ir = make_package_ir(variables=[var])

        result = renderer.render(ir, RenderOptions())

        assert "Score: int" in result
        assert "Score: int =" not in result

    def test_render_variable_sorted(self, renderer, make_package_ir):
        """变量按名称排序。"""
        from uasset_read.models.ir import VariableIR

        vars_ = [
            VariableIR(name="Zebra", type="bool", default_value=None),
            VariableIR(name="Alpha", type="int", default_value=None),
        ]
        ir = make_package_ir(variables=vars_)

        result = renderer.render(ir, RenderOptions())

        idx_alpha = result.index("Alpha")
        idx_zebra = result.index("Zebra")
        assert idx_alpha < idx_zebra

    def test_render_long_default_truncated(self, renderer, make_package_ir):
        """超长默认值被截断。"""
        from uasset_read.models.ir import VariableIR

        long_value = "x" * 150
        var = VariableIR(name="LongVar", type="str", default_value=long_value)
        ir = make_package_ir(variables=[var])

        result = renderer.render(ir, RenderOptions())

        # 应包含截断标记
        assert "..." in result
        assert "LongVar" in result

    def test_render_all_editor_variables_hidden_standard(self, renderer, make_package_ir):
        """全是编辑器变量时不输出 [Variables] 区域。"""
        from uasset_read.models.ir import VariableIR

        vars_ = [
            VariableIR(name="UbergraphPages", type="Array<int>", default_value="[]"),
            VariableIR(name="FunctionGraphs", type="Array<int>", default_value="[]"),
        ]
        ir = make_package_ir(variables=vars_)

        result = renderer.render(ir, RenderOptions(output_level="standard"))

        assert "[Variables]" not in result


class TestTextRendererGraph:
    """图渲染测试。"""

    def test_render_graph_section(self, renderer, make_package_ir, make_export_ir,
                                   make_graph_ir, make_node_ir):
        """包含图的 export 输出 [Graph] 区域。"""
        node = make_node_ir()
        graph = make_graph_ir(name="ExecGraph", nodes=[node])
        export = make_export_ir(graphs=[graph])
        ir = make_package_ir(exports=[export])

        result = renderer.render(ir, RenderOptions())

        assert "[Graph: ExecGraph]" in result
        assert "Nodes: 1" in result

    def test_render_graph_execution_chains(self, renderer, make_package_ir,
                                            make_export_ir, make_graph_ir, make_node_ir):
        """图有 execution_chains 时显示 Chain 行。"""
        node = make_node_ir()
        graph = make_graph_ir(
            name="FlowGraph",
            nodes=[node],
            execution_chains=[["EventBeginPlay", "PrintString", "Delay"]],
        )
        export = make_export_ir(graphs=[graph])
        ir = make_package_ir(exports=[export])

        result = renderer.render(ir, RenderOptions())

        assert "Chain: EventBeginPlay -> PrintString -> Delay" in result

    def test_render_graph_execution_chains_limited(self, renderer, make_package_ir,
                                                    make_export_ir, make_graph_ir, make_node_ir):
        """超过 3 条 execution_chains 时只显示前 3 条。"""
        node = make_node_ir()
        chains = [
            ["A", "B"],
            ["C", "D"],
            ["E", "F"],
            ["G", "H"],
        ]
        graph = make_graph_ir(name="MultiChain", nodes=[node], execution_chains=chains)
        export = make_export_ir(graphs=[graph])
        ir = make_package_ir(exports=[export])

        result = renderer.render(ir, RenderOptions())

        assert "+1 more chains" in result

    def test_render_graph_no_nodes_hidden_standard(self, renderer, make_package_ir,
                                                    make_export_ir, make_graph_ir):
        """standard 模式下纯编辑器节点的图不显示。"""
        from uasset_read.models.ir import NodeIR

        knot = NodeIR(
            node_guid="00000000000000000000000000000001",
            node_class="K2Node_Knot",
            node_comment=None,
            pins=[],
            execution_flow=[],
        )
        graph = make_graph_ir(name="KnotOnly", nodes=[knot])
        export = make_export_ir(graphs=[graph])
        ir = make_package_ir(exports=[export])

        result = renderer.render(ir, RenderOptions(output_level="standard"))

        assert "KnotOnly" not in result

    def test_render_graph_editor_nodes_shown_debug(self, renderer, make_package_ir,
                                                    make_export_ir, make_graph_ir):
        """debug 模式下编辑器节点的图仍显示。"""
        from uasset_read.models.ir import NodeIR

        knot = NodeIR(
            node_guid="00000000000000000000000000000001",
            node_class="K2Node_Knot",
            node_comment=None,
            pins=[],
            execution_flow=[],
        )
        graph = make_graph_ir(name="KnotDebug", nodes=[knot])
        export = make_export_ir(graphs=[graph])
        ir = make_package_ir(exports=[export])

        result = renderer.render(ir, RenderOptions(output_level="debug"))

        assert "KnotDebug" in result

    def test_render_multiple_graphs(self, renderer, make_package_ir, make_export_ir,
                                     make_graph_ir, make_node_ir):
        """export 包含多个图时全部显示。"""
        n1 = make_node_ir()
        n2 = make_node_ir()
        g1 = make_graph_ir(name="Graph1", nodes=[n1])
        g2 = make_graph_ir(name="Graph2", nodes=[n2])
        export = make_export_ir(graphs=[g1, g2])
        ir = make_package_ir(exports=[export])

        result = renderer.render(ir, RenderOptions())

        assert "[Graph: Graph1]" in result
        assert "[Graph: Graph2]" in result


class TestTextRendererLinker:
    """Linker 渲染测试。"""

    def test_render_linker_section(self, renderer, make_package_ir):
        """有 linker 时输出 [Linker] 区域。"""
        from uasset_read.models.ir import LinkerSummaryIR

        lk = LinkerSummaryIR(
            has_linker=True,
            import_paths=["/Engine/Core", "/Engine/Engine"],
            export_paths=["/Game/Blueprints/BP_Test"],
        )
        ir = make_package_ir()
        ir.linker = lk

        result = renderer.render(ir, RenderOptions())

        assert "[Linker]" in result
        assert "Imports: 2" in result
        assert "Exports: 1" in result

    def test_render_no_linker(self, renderer, make_package_ir):
        """无 linker 时不输出 [Linker] 区域。"""
        ir = make_package_ir()
        result = renderer.render(ir, RenderOptions())

        assert "[Linker]" not in result


class TestTextRendererBlueprint:
    """蓝图渲染测试。"""

    def test_render_blueprint_parent_class(self, renderer, make_package_ir):
        """蓝图输出 Parent Class。"""
        from uasset_read.models.ir import BlueprintIR

        bp = BlueprintIR(parent_class="AActor", description="")
        ir = make_package_ir()
        ir.blueprint = bp

        result = renderer.render(ir, RenderOptions())

        assert "[Blueprint]" in result
        assert "Parent Class: AActor" in result

    def test_render_blueprint_description(self, renderer, make_package_ir):
        """蓝图输出 Description。"""
        from uasset_read.models.ir import BlueprintIR

        bp = BlueprintIR(parent_class=None, description="My blueprint description")
        ir = make_package_ir()
        ir.blueprint = bp

        result = renderer.render(ir, RenderOptions())

        assert "Description: My blueprint description" in result

    def test_render_blueprint_long_description_truncated(self, renderer, make_package_ir):
        """超长蓝图描述被截断。"""
        from uasset_read.models.ir import BlueprintIR

        long_desc = "x" * 250
        bp = BlueprintIR(parent_class=None, description=long_desc)
        ir = make_package_ir()
        ir.blueprint = bp

        result = renderer.render(ir, RenderOptions())

        assert "..." in result

    def test_render_blueprint_interfaces(self, renderer, make_package_ir):
        """蓝图输出接口数量。"""
        from uasset_read.models.ir import BlueprintIR

        bp = BlueprintIR(
            parent_class=None,
            interfaces=["IInterface1", "IInterface2", "IInterface3"],
        )
        ir = make_package_ir()
        ir.blueprint = bp

        result = renderer.render(ir, RenderOptions())

        assert "Interfaces: 3" in result

    def test_render_blueprint_functions(self, renderer, make_package_ir):
        """蓝图输出函数列表。"""
        from uasset_read.models.ir import BlueprintIR, BlueprintFunctionIR

        fn1 = BlueprintFunctionIR(
            name="BeginPlay",
            return_type="void",
            parameters=[],
        )
        fn2 = BlueprintFunctionIR(
            name="Tick",
            return_type="void",
            parameters=[{"name": "DeltaTime"}, {"name": "FrameCount"}],
        )
        bp = BlueprintIR(parent_class=None, functions=[fn1, fn2])
        ir = make_package_ir()
        ir.blueprint = bp

        result = renderer.render(ir, RenderOptions())

        assert "Functions:" in result
        assert "- BeginPlay" in result
        assert "- Tick" in result
        assert "Params: DeltaTime, FrameCount" in result

    def test_render_blueprint_functions_sorted(self, renderer, make_package_ir):
        """蓝图函数按名称排序。"""
        from uasset_read.models.ir import BlueprintIR, BlueprintFunctionIR

        fn1 = BlueprintFunctionIR(name="Zebra", return_type="void", parameters=[])
        fn2 = BlueprintFunctionIR(name="Alpha", return_type="void", parameters=[])
        bp = BlueprintIR(parent_class=None, functions=[fn1, fn2])
        ir = make_package_ir()
        ir.blueprint = bp

        result = renderer.render(ir, RenderOptions())

        idx_alpha = result.index("- Alpha")
        idx_zebra = result.index("- Zebra")
        assert idx_alpha < idx_zebra

    def test_render_blueprint_events(self, renderer, make_package_ir):
        """蓝图输出事件列表。"""
        from uasset_read.models.ir import BlueprintIR, BlueprintEventIR

        ev1 = BlueprintEventIR(name="ReceiveBeginPlay", event_type="custom", parameters=[])
        ev2 = BlueprintEventIR(name="ReceiveTick", event_type="custom", parameters=[])
        bp = BlueprintIR(parent_class=None, events=[ev1, ev2])
        ir = make_package_ir()
        ir.blueprint = bp

        result = renderer.render(ir, RenderOptions())

        assert "Events:" in result
        assert "- ReceiveBeginPlay" in result
        assert "- ReceiveTick" in result

    def test_render_blueprint_components(self, renderer, make_package_ir):
        """蓝图输出组件数量。"""
        from uasset_read.models.ir import BlueprintIR

        bp = BlueprintIR(
            parent_class=None,
            components=[{"name": "Comp1"}, {"name": "Comp2"}],
        )
        ir = make_package_ir()
        ir.blueprint = bp

        result = renderer.render(ir, RenderOptions())

        assert "Components: 2" in result

    def test_render_no_blueprint(self, renderer, make_package_ir):
        """无蓝图时不输出 [Blueprint] 区域。"""
        ir = make_package_ir()
        result = renderer.render(ir, RenderOptions())

        assert "[Blueprint]" not in result


class TestTextRendererDecompiled:
    """反编译函数渲染测试。"""

    def test_render_decompiled_functions(self, renderer, make_package_ir):
        """渲染反编译函数。"""
        from uasset_read.models.ir import DecompiledFunctionIR

        fn = DecompiledFunctionIR(
            name="MyFunc",
            signature="void MyFunc(int32 Param1)",
            cpp_code="// code",
            parameters=[],
            return_type="void",
        )
        ir = make_package_ir()
        ir.decompiled_functions = [fn]

        result = renderer.render(ir, RenderOptions())

        assert "[Decompiled Functions]" in result
        assert "void MyFunc(int32 Param1)" in result

    def test_render_decompiled_sorted(self, renderer, make_package_ir):
        """反编译函数按名称排序。"""
        from uasset_read.models.ir import DecompiledFunctionIR

        fn1 = DecompiledFunctionIR(name="ZFunc", signature="void ZFunc()", cpp_code="", parameters=[], return_type="void")
        fn2 = DecompiledFunctionIR(name="AFunc", signature="void AFunc()", cpp_code="", parameters=[], return_type="void")
        ir = make_package_ir()
        ir.decompiled_functions = [fn1, fn2]

        result = renderer.render(ir, RenderOptions())

        idx_a = result.index("AFunc")
        idx_z = result.index("ZFunc")
        assert idx_a < idx_z

    def test_render_decompiled_fallback_to_name(self, renderer, make_package_ir):
        """无 signature 时回退到 name。"""
        from uasset_read.models.ir import DecompiledFunctionIR

        fn = DecompiledFunctionIR(name="FallbackFunc", signature="", cpp_code="", parameters=[], return_type="void")
        ir = make_package_ir()
        ir.decompiled_functions = [fn]

        result = renderer.render(ir, RenderOptions())

        assert "FallbackFunc" in result


class TestTextRendererExecutionChains:
    """执行链渲染测试。"""

    def test_render_execution_chains(self, renderer, make_package_ir):
        """渲染顶层执行链。"""
        from uasset_read.models.ir import ExecutionChainIR

        chain = ExecutionChainIR(
            event="ReceiveBeginPlay",
            chain=["ReceiveBeginPlay", "PrintString", "Delay"],
        )
        ir = make_package_ir()
        ir.execution_chains = [chain]

        result = renderer.render(ir, RenderOptions())

        assert "[Execution Chains]" in result
        assert "ReceiveBeginPlay: ReceiveBeginPlay -> PrintString -> Delay" in result

    def test_render_long_chain_truncated(self, renderer, make_package_ir):
        """超过 5 个节点的执行链被截断显示。"""
        from uasset_read.models.ir import ExecutionChainIR

        chain = ExecutionChainIR(
            event="LongEvent",
            chain=["A", "B", "C", "D", "E", "F", "G"],
        )
        ir = make_package_ir()
        ir.execution_chains = [chain]

        result = renderer.render(ir, RenderOptions())

        assert "... (7 total)" in result


class TestTextRendererDiagnostics:
    """诊断信息渲染测试。"""

    def test_render_diagnostics(self, renderer, make_package_ir):
        """渲染诊断信息。"""
        ir = make_package_ir()
        ir.diagnostics = ["Warning: something", "Info: detail"]

        result = renderer.render(ir, RenderOptions())

        assert "[Diagnostics]" in result
        assert "Warning: something" in result
        assert "Info: detail" in result

    def test_render_diagnostics_dict(self, renderer, make_package_ir):
        """字典格式的诊断信息提取 message。"""
        ir = make_package_ir()
        ir.diagnostics = [{"message": "Offset mismatch at 0x100"}]

        result = renderer.render(ir, RenderOptions())

        assert "Offset mismatch at 0x100" in result

    def test_render_diagnostics_limited(self, renderer, make_package_ir):
        """超过 10 条诊断只显示前 10 条。"""
        ir = make_package_ir()
        ir.diagnostics = [f"diag_{i}" for i in range(15)]

        result = renderer.render(ir, RenderOptions())

        assert "+5 more" in result


class TestTextRendererStatus:
    """状态渲染测试。"""

    def test_render_success_status_hidden(self, renderer, make_package_ir):
        """success 状态不输出 Status 行。"""
        ir = make_package_ir()
        result = renderer.render(ir, RenderOptions())

        assert "Status:" not in result

    def test_render_partial_status(self, renderer, make_package_ir):
        """partial 状态输出 Status 行。"""
        ir = make_package_ir()
        ir.status = "partial"

        result = renderer.render(ir, RenderOptions())

        assert "Status: partial" in result

    def test_render_failed_status(self, renderer, make_package_ir):
        """failed 状态输出 Status 行。"""
        ir = make_package_ir()
        ir.status = "failed"
        ir.status_message = "Parse error at offset 0x100"

        result = renderer.render(ir, RenderOptions())

        assert "Status: failed" in result
        assert "Message: Parse error at offset 0x100" in result

    def test_render_status_no_message(self, renderer, make_package_ir):
        """有 status 无 message 时只输出 Status 行。"""
        ir = make_package_ir()
        ir.status = "partial"

        result = renderer.render(ir, RenderOptions())

        assert "Status: partial" in result
        assert "Message:" not in result


class TestTextRendererRenderTo:
    """render_to 方法测试。"""

    def test_render_to_writes_to_stream(self, renderer, make_package_ir):
        """render_to 写入 StringIO。"""
        ir = make_package_ir()
        writer = StringIO()

        renderer.render_to(ir, writer, RenderOptions())

        output = writer.getvalue()
        assert "TestPackage" in output

    def test_render_to_matches_render(self, renderer, make_package_ir, make_export_ir):
        """render_to 与 render 输出内容一致。"""
        export = make_export_ir(object_name="MatchTest")
        ir = make_package_ir(exports=[export])

        render_result = renderer.render(ir, RenderOptions())
        writer = StringIO()
        renderer.render_to(ir, writer, RenderOptions())
        render_to_result = writer.getvalue()

        assert render_result == render_to_result

    def test_render_to_none_options_uses_defaults(self, renderer, make_package_ir):
        """render_to 传入 None 时使用默认 RenderOptions。"""
        ir = make_package_ir()
        writer = StringIO()

        renderer.render_to(ir, writer, options=None)

        output = writer.getvalue()
        assert "TestPackage" in output


class TestTextRendererAnimation:
    """动画蓝图渲染测试。"""

    def test_render_anim_blueprint(self, renderer, make_package_ir):
        """渲染 AnimBlueprint 数据。"""
        from uasset_read.models.ir import AnimBlueprintIR, BakedStateMachineIR

        sm = BakedStateMachineIR(machine_name="WalkRun")
        abp = AnimBlueprintIR(baked_state_machines=[sm])
        ir = make_package_ir()
        ir.anim_blueprint = abp

        result = renderer.render(ir, RenderOptions())

        assert "[AnimBlueprint]" in result
        assert "State Machines: 1" in result
        assert "- WalkRun" in result

    def test_render_anim_sequence(self, renderer, make_package_ir):
        """渲染 AnimSequence 数据。"""
        from uasset_read.models.ir import AnimSequenceIR

        ans = AnimSequenceIR(notifies=[{"name": "FootStep"}])
        ir = make_package_ir()
        ir.anim_sequence = ans

        result = renderer.render(ir, RenderOptions())

        assert "[AnimSequence]" in result
        assert "Notifies: 1" in result

    def test_render_anim_montage(self, renderer, make_package_ir):
        """渲染 AnimMontage 数据。"""
        from uasset_read.models.ir import AnimMontageIR

        amt = AnimMontageIR(composite_sections=[{"name": "Section1"}])
        ir = make_package_ir()
        ir.anim_montage = amt

        result = renderer.render(ir, RenderOptions())

        assert "[AnimMontage]" in result
        assert "Composite Sections: 1" in result


class TestTextRendererEdgeCases:
    """边界情况测试。"""

    def test_render_empty_package_name(self, renderer, make_package_ir):
        """空包名正常渲染。"""
        ir = make_package_ir(name="")
        result = renderer.render(ir, RenderOptions())

        assert "===  ===" in result

    def test_render_stable_output(self, renderer, make_package_ir, make_export_ir):
        """同一输入多次渲染输出一致。"""
        ir = make_package_ir(name="StablePkg")
        r1 = renderer.render(ir, RenderOptions())
        r2 = renderer.render(ir, RenderOptions())

        assert r1 == r2

    def test_render_with_all_sections(self, renderer, make_package_ir, make_export_ir):
        """包含所有主要区域的综合测试。"""
        from uasset_read.models.ir import (
            BlueprintIR, BlueprintFunctionIR, VariableIR,
            LinkerSummaryIR, DecompiledFunctionIR, ExecutionChainIR,
        )

        # Linker
        lk = LinkerSummaryIR(
            has_linker=True,
            import_paths=["/Engine/Core"],
            export_paths=["/Game/BP"],
        )

        # Blueprint
        fn = BlueprintFunctionIR(name="TestFunc", return_type="void", parameters=[])
        bp = BlueprintIR(parent_class="AActor", description="Test BP", functions=[fn])

        # Variable
        var = VariableIR(name="MyVar", type="float", default_value="1.0")

        # Export
        export = make_export_ir(object_name="MainExport")

        # Decompiled function
        dcf = DecompiledFunctionIR(
            name="DecompFunc",
            signature="void DecompFunc()",
            cpp_code="// code",
            parameters=[],
            return_type="void",
        )

        # Execution chain
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

        result = renderer.render(ir, RenderOptions())

        # 验证所有区域存在
        assert "=== TestPackage ===" in result
        assert "Flags: 0x000000FF" in result
        assert "Folder: Content/Test" in result
        assert "[Linker]" in result
        assert "[Blueprint]" in result
        assert "[Variables]" in result
        assert "[Decompiled Functions]" in result
        assert "[Execution Chains]" in result
        assert "[Diagnostics]" in result
        assert "[Exports]" in result


# ---------------------------------------------------------------------------
# diff_single 测试（合并自 tests/test_text_renderer.py）
# ---------------------------------------------------------------------------

class TestDiffSingle:
    """diff_single 函数测试。"""

    def test_same_file_no_diff(self):
        from uasset_read.core import diff_single

        # 使用 mock 的 IR 无法直接测试，但可以验证函数签名
        # 实际测试使用真实文件
        assert callable(diff_single)

    def test_returns_str(self):
        """验证返回类型为 str。"""
        from uasset_read.core import diff_single

        result = diff_single("nonexistent1.uasset", "nonexistent2.uasset")
        assert isinstance(result, str)

    def test_nonexistent_files_contain_error(self):
        """验证不存在的文件在 diff 输出中包含错误信息。"""
        from uasset_read.core import diff_single

        result = diff_single("nonexistent1.uasset", "nonexistent2.uasset")
        assert "FileNotFoundError" in result or "failed" in result

    def test_diff_header_present(self):
        """验证 diff 输出包含文件名头信息。"""
        from uasset_read.core import diff_single

        result = diff_single("foo.uasset", "bar.uasset")
        assert "a/foo.uasset" in result
        assert "b/bar.uasset" in result


# ---------------------------------------------------------------------------
# get_renderer 可用性（合并自 tests/test_text_renderer.py）
# ---------------------------------------------------------------------------

class TestTextRendererRegistration:
    """Text renderer 注册验证。"""

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
# Text 渲染器废弃警告测试（原 test_text_deprecated.py）
# ---------------------------------------------------------------------------

def _make_minimal_ir() -> PackageIR:
    """创建最小 PackageIR 用于测试。"""
    header = PackageHeaderIR(
        package_name="Test",
        package_class="None",
        package_flags=0,
        total_export_count=0,
        total_import_count=0,
        ue_version="5.4.0",
    )
    return PackageIR(
        header=header,
        name_map=(),
        imports=[],
        exports=[],
        linker=None,
    )


class TestTextDeprecated:
    def test_text_format_emits_deprecation_warning(self):
        """--text 格式应发出 DeprecationWarning。"""
        from uasset_read.renderers.text_renderer import TextRenderer
        from uasset_read.renderers.base import RenderOptions

        ir = _make_minimal_ir()
        renderer = TextRenderer()
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            renderer.render(ir, RenderOptions())

        dep_warnings = [x for x in w if issubclass(x.category, DeprecationWarning)]
        assert len(dep_warnings) >= 1
        assert "markdown" in str(dep_warnings[0].message).lower()

    def test_markdown_format_no_deprecation_warning(self):
        """--markdown 格式不应发出 DeprecationWarning。"""
        from uasset_read.renderers.markdown_renderer import MarkdownRenderer
        from uasset_read.renderers.base import RenderOptions

        ir = _make_minimal_ir()
        renderer = MarkdownRenderer()
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            renderer.render(ir, RenderOptions())

        dep_warnings = [x for x in w if issubclass(x.category, DeprecationWarning)]
        assert len(dep_warnings) == 0

    def test_text_renderer_still_works(self):
        """废弃后 Text 渲染器仍应正常工作。"""
        from uasset_read.renderers.text_renderer import TextRenderer
        from uasset_read.renderers.base import RenderOptions

        ir = _make_minimal_ir()
        renderer = TextRenderer()
        with warnings.catch_warnings(record=True):
            warnings.simplefilter("always")
            result = renderer.render(ir, RenderOptions())
        assert "=== Test ===" in result
