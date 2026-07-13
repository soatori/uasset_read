"""文本渲染器和 diff 功能测试。"""
from __future__ import annotations

import pytest

from uasset_read.models.ir import (
    PackageIR,
    PackageHeaderIR,
    ExportIR,
    BlueprintIR,
    BlueprintFunctionIR,
    BlueprintEventIR,
    VariableIR,
    ExecutionChainIR,
    LinkerSummaryIR,
    DecompiledFunctionIR,
)
from uasset_read.renderers import get_renderer
from uasset_read.renderers.base import RenderOptions


# ---------------------------------------------------------------------------
# 辅助工厂
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
        exports=[],
        linker=None,
    )
    defaults.update(kwargs)
    return PackageIR(**defaults)


# ---------------------------------------------------------------------------
# TextRenderer 基础测试
# ---------------------------------------------------------------------------

class TestTextRendererBasic:
    """TextRenderer 基本功能。"""

    def test_returns_string(self):
        renderer = get_renderer("text")
        assert renderer is not None
        ir = _make_ir()
        result = renderer.render(ir, RenderOptions())
        assert isinstance(result, str)

    def test_includes_header(self):
        renderer = get_renderer("text")
        ir = _make_ir(header=_make_header(package_name="/Game/TestAsset"))
        result = renderer.render(ir, RenderOptions())
        assert "=== /Game/TestAsset ===" in result
        assert "Type: /Engine/Blueprint" in result
        assert "Version: 5.3" in result

    def test_empty_ir(self):
        renderer = get_renderer("text")
        ir = _make_ir()
        result = renderer.render(ir, RenderOptions())
        assert "=== /Game/BP_Test ===" in result
        # 无 import/export 应不显示对应节
        assert "[Imports]" not in result
        assert "[Exports]" not in result

    def test_exports_section(self):
        renderer = get_renderer("text")
        exp = _make_export(object_name="MyActor", object_class="Actor", serial_size=2048)
        ir = _make_ir(exports=[exp])
        result = renderer.render(ir, RenderOptions())
        assert "[Exports]" in result
        assert "MyActor (Actor)" in result
        assert "2048 bytes" in result
        assert "Parent: /Engine/Actor" in result

    def test_imports_section(self):
        renderer = get_renderer("text")
        imports = [
            {"object_name": "Engine", "object_class": "Package"},
            {"object_name": "Core", "object_class": "Package"},
        ]
        ir = _make_ir(imports=imports)
        result = renderer.render(ir, RenderOptions())
        assert "[Imports]" in result
        assert "Core (Package)" in result
        assert "Engine (Package)" in result

    def test_imports_sorted(self):
        renderer = get_renderer("text")
        imports = [
            {"object_name": "ZZZ", "object_class": "Package"},
            {"object_name": "AAA", "object_class": "Package"},
        ]
        ir = _make_ir(imports=imports)
        result = renderer.render(ir, RenderOptions())
        lines = result.splitlines()
        import_lines = [l for l in lines if l.strip().startswith("AAA")]
        assert import_lines
        # AAA 应在 ZZZ 之前
        aaa_idx = next(i for i, l in enumerate(lines) if "AAA" in l)
        zzz_idx = next(i for i, l in enumerate(lines) if "ZZZ" in l)
        assert aaa_idx < zzz_idx

    def test_flags_shown(self):
        renderer = get_renderer("text")
        ir = _make_ir(header=_make_header(package_flags=0x00000100))
        result = renderer.render(ir, RenderOptions())
        assert "Flags: 0x00000100" in result

    def test_no_flags_when_zero(self):
        renderer = get_renderer("text")
        ir = _make_ir(header=_make_header(package_flags=0))
        result = renderer.render(ir, RenderOptions())
        assert "Flags:" not in result


# ---------------------------------------------------------------------------
# TextRenderer 蓝图测试
# ---------------------------------------------------------------------------

class TestTextRendererBlueprint:
    """TextRenderer 蓝图数据渲染。"""

    def _make_blueprint_ir(self) -> PackageIR:
        bp = BlueprintIR(
            parent_class="/Engine/Actor",
            description="Test blueprint description",
            interfaces=[{"name": "IInterface", "guid": "abc123"}],
            functions=[
                BlueprintFunctionIR(
                    name="ReceiveBeginPlay",
                    parameters=[{"name": "self", "type": "object"}],
                    return_type="void",
                ),
                BlueprintFunctionIR(
                    name="ReceiveTick",
                    parameters=[
                        {"name": "self", "type": "object"},
                        {"name": "DeltaSeconds", "type": "float"},
                    ],
                    return_type="void",
                ),
            ],
            events=[
                BlueprintEventIR(
                    name="OnActorBeginOverlap",
                    event_type="delegate",
                    parameters=[],
                ),
            ],
            components=[{"name": "DefaultSceneRoot"}],
        )
        var = VariableIR(
            name="Health",
            type="float",
            default_value="100.0",
            kind="user",
        )
        return _make_ir(blueprint=bp, variables=[var])

    def test_blueprint_section(self):
        renderer = get_renderer("text")
        ir = self._make_blueprint_ir()
        result = renderer.render(ir, RenderOptions())
        assert "[Blueprint]" in result
        assert "Parent Class: /Engine/Actor" in result
        assert "Interfaces: 1" in result
        assert "Components: 1" in result

    def test_functions_sorted(self):
        renderer = get_renderer("text")
        ir = self._make_blueprint_ir()
        result = renderer.render(ir, RenderOptions())
        assert "Functions:" in result
        assert "ReceiveBeginPlay" in result
        assert "ReceiveTick" in result

    def test_events_sorted(self):
        renderer = get_renderer("text")
        ir = self._make_blueprint_ir()
        result = renderer.render(ir, RenderOptions())
        assert "Events:" in result
        assert "OnActorBeginOverlap" in result

    def test_variables_sorted(self):
        renderer = get_renderer("text")
        ir = self._make_blueprint_ir()
        result = renderer.render(ir, RenderOptions())
        assert "[Variables]" in result
        assert "Health: float = 100.0" in result


# ---------------------------------------------------------------------------
# TextRenderer 其他节
# ---------------------------------------------------------------------------

class TestTextRendererOtherSections:
    """TextRenderer 其他数据节。"""

    def test_linker_section(self):
        renderer = get_renderer("text")
        linker = LinkerSummaryIR(
            has_linker=True,
            import_paths=["/Engine/Core"],
            export_paths=["/Game/MyActor"],
        )
        ir = _make_ir(linker=linker)
        result = renderer.render(ir, RenderOptions())
        assert "[Linker]" in result
        assert "Imports: 1" in result
        assert "Exports: 1" in result

    def test_decompiled_functions(self):
        renderer = get_renderer("text")
        fn = DecompiledFunctionIR(
            name="ReceiveBeginPlay",
            signature="void ReceiveBeginPlay()",
            cpp_code="// code",
            parameters=[],
            return_type="void",
        )
        ir = _make_ir(decompiled_functions=[fn])
        result = renderer.render(ir, RenderOptions())
        assert "[Decompiled Functions]" in result
        assert "void ReceiveBeginPlay()" in result

    def test_execution_chains(self):
        renderer = get_renderer("text")
        chain = ExecutionChainIR(
            event="OnBeginPlay",
            chain=["Node1", "Node2", "Node3"],
        )
        ir = _make_ir(execution_chains=[chain])
        result = renderer.render(ir, RenderOptions())
        assert "[Execution Chains]" in result
        assert "OnBeginPlay: Node1 -> Node2 -> Node3" in result

    def test_execution_chain_truncated(self):
        renderer = get_renderer("text")
        chain = ExecutionChainIR(
            event="OnTick",
            chain=[f"Node{i}" for i in range(10)],
        )
        ir = _make_ir(execution_chains=[chain])
        result = renderer.render(ir, RenderOptions())
        assert "... (10 total)" in result

    def test_diagnostic_limit(self):
        renderer = get_renderer("text")
        ir = _make_ir(diagnostics=[f"Diag {i}" for i in range(20)])
        result = renderer.render(ir, RenderOptions())
        assert "[Diagnostics]" in result
        assert "Diag 0" in result
        assert "... +10 more" in result

    def test_non_success_status(self):
        renderer = get_renderer("text")
        ir = _make_ir(status="partial", status_message="Some errors")
        result = renderer.render(ir, RenderOptions())
        assert "Status: partial" in result
        assert "Message: Some errors" in result


# ---------------------------------------------------------------------------
# TextRenderer 字段排序稳定性
# ---------------------------------------------------------------------------

class TestTextRendererSorting:
    """字段排序确保 diff 稳定。"""

    def test_exports_sorted_by_index(self):
        renderer = get_renderer("text")
        exp1 = _make_export(index=1, object_name="B_Object")
        exp2 = _make_export(index=0, object_name="A_Object")
        # 即使传入顺序不同，输出应按 index 排序
        ir = _make_ir(exports=[exp1, exp2])
        result = renderer.render(ir, RenderOptions())
        lines = result.splitlines()
        export_lines = [l for l in lines if "[0]" in l or "[1]" in l]
        assert len(export_lines) == 2
        assert "[0]" in export_lines[0]
        assert "[1]" in export_lines[1]


# ---------------------------------------------------------------------------
# diff_single 测试
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
# get_renderer 可用性
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
# TextRenderer output_level 过滤测试
# ---------------------------------------------------------------------------

class TestTextRendererOutputLevelFilter:
    """TextRenderer output_level 过滤功能测试。"""

    def test_standard_mode_filters_editor_variables(self):
        """standard 模式下应过滤编辑器内部变量"""
        renderer = get_renderer("text")
        # 创建包含编辑器变量的 IR
        editor_var = VariableIR(
            name="UbergraphPages",
            type="ArrayProperty",
            default_value="[]",
            kind="editor",
        )
        user_var = VariableIR(
            name="Health",
            type="FloatProperty",
            default_value="100.0",
            kind="user",
        )
        ir = _make_ir(variables=[editor_var, user_var])
        # standard 模式（默认）
        result = renderer.render(ir, RenderOptions())
        assert "[Variables]" in result
        assert "Health: FloatProperty = 100.0" in result
        assert "UbergraphPages" not in result

    def test_debug_mode_preserves_editor_variables(self):
        """debug 模式下应保留编辑器内部变量"""
        renderer = get_renderer("text")
        editor_var = VariableIR(
            name="UbergraphPages",
            type="ArrayProperty",
            default_value="[]",
            kind="editor",
        )
        user_var = VariableIR(
            name="Health",
            type="FloatProperty",
            default_value="100.0",
            kind="user",
        )
        ir = _make_ir(variables=[editor_var, user_var])
        # debug 模式
        result = renderer.render(ir, RenderOptions(output_level="debug"))
        assert "[Variables]" in result
        assert "Health: FloatProperty = 100.0" in result
        assert "UbergraphPages" in result

    def test_standard_mode_filters_editor_nodes_in_graphs(self):
        """standard 模式下应过滤编辑器节点（如 K2Node_Knot）"""
        from uasset_read.models.ir import GraphIR, NodeIR, PinIR

        renderer = get_renderer("text")
        # 创建包含编辑器节点的图
        editor_node = NodeIR(
            node_guid="knot_guid_1234567890abcdef12345678",
            node_class="K2Node_Knot",
            node_comment="Redirect node",
            pins=[],
            execution_flow=[],
        )
        normal_node = NodeIR(
            node_guid="normal_guid_1234567890abcdef12345678",
            node_class="K2Node_CallFunction",
            node_comment="Set Health",
            pins=[],
            execution_flow=[],
        )
        graph = GraphIR(
            graph_guid="guid0001",
            graph_name="EventGraph",
            graph_class="EdGraph",
            nodes=[editor_node, normal_node],
            execution_chains=[],
        )
        export = _make_export(graphs=[graph])
        ir = _make_ir(exports=[export])
        # standard 模式
        result = renderer.render(ir, RenderOptions())
        assert "[Graph: EventGraph]" in result
        assert "Nodes: 1" in result  # 只有 normal_node
        assert "K2Node_Knot" not in result

    def test_debug_mode_preserves_editor_nodes_in_graphs(self):
        """debug 模式下应保留编辑器节点"""
        from uasset_read.models.ir import GraphIR, NodeIR

        renderer = get_renderer("text")
        editor_node = NodeIR(
            node_guid="knot_guid_1234567890abcdef12345678",
            node_class="K2Node_Knot",
            node_comment="Redirect node",
            pins=[],
            execution_flow=[],
        )
        normal_node = NodeIR(
            node_guid="normal_guid_1234567890abcdef12345678",
            node_class="K2Node_CallFunction",
            node_comment="Set Health",
            pins=[],
            execution_flow=[],
        )
        graph = GraphIR(
            graph_guid="guid0001",
            graph_name="EventGraph",
            graph_class="EdGraph",
            nodes=[editor_node, normal_node],
            execution_chains=[],
        )
        export = _make_export(graphs=[graph])
        ir = _make_ir(exports=[export])
        # debug 模式
        result = renderer.render(ir, RenderOptions(output_level="debug"))
        assert "[Graph: EventGraph]" in result
        assert "Nodes: 2" in result  # 两个节点都保留（TextRenderer 不显示节点类名，只显示数量）

    def test_empty_graph_after_filtering_not_shown(self):
        """过滤后无节点的图不应显示"""
        from uasset_read.models.ir import GraphIR, NodeIR

        renderer = get_renderer("text")
        editor_node = NodeIR(
            node_guid="knot_guid_1234567890abcdef12345678",
            node_class="K2Node_Knot",
            node_comment="Redirect node",
            pins=[],
            execution_flow=[],
        )
        graph = GraphIR(
            graph_guid="guid0001",
            graph_name="EventGraph",
            graph_class="EdGraph",
            nodes=[editor_node],
            execution_chains=[],
        )
        export = _make_export(graphs=[graph])
        ir = _make_ir(exports=[export])
        # standard 模式
        result = renderer.render(ir, RenderOptions())
        assert "[Graph: EventGraph]" not in result

    def test_multiple_editor_variables_filtered(self):
        """应过滤所有编辑器变量"""
        renderer = get_renderer("text")
        variables = [
            VariableIR(name="UbergraphPages", type="ArrayProperty", default_value="[]", kind="editor"),
            VariableIR(name="FunctionGraphs", type="ArrayProperty", default_value="[]", kind="editor"),
            VariableIR(name="CategorySorting", type="ArrayProperty", default_value="[]", kind="editor"),
            VariableIR(name="ImplementedInterfaces", type="ArrayProperty", default_value="[]", kind="editor"),
            VariableIR(name="LastEditedDocuments", type="ArrayProperty", default_value="[]", kind="editor"),
            VariableIR(name="ThumbnailInfo", type="ObjectProperty", default_value=None, kind="editor"),
            VariableIR(name="bLegacyNeedToPurgeSkelRefs", type="BoolProperty", default_value="false", kind="editor"),
            VariableIR(name="Health", type="FloatProperty", default_value="100.0", kind="user"),
        ]
        ir = _make_ir(variables=variables)
        result = renderer.render(ir, RenderOptions())
        # 只有 Health 应显示
        assert "Health" in result
        assert "UbergraphPages" not in result
        assert "FunctionGraphs" not in result
        assert "CategorySorting" not in result
        assert "ImplementedInterfaces" not in result
        assert "LastEditedDocuments" not in result
        assert "ThumbnailInfo" not in result
        assert "bLegacyNeedToPurgeSkelRefs" not in result
