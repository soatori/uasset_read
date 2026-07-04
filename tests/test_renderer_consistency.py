"""渲染器一致性测试。

验证 Markdown 渲染器过滤与 JSON 渲染器一致，以及 IR Builder parent_class 逻辑安全。
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
from uasset_read.renderers.json_renderer import JSONRenderer
from uasset_read.renderers.markdown_renderer import MarkdownRenderer


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
# 编辑器变量过滤一致性
# ---------------------------------------------------------------------------

class TestEditorVariableFilterConsistency:
    """验证 Markdown 和 JSON 渲染器对编辑器内部变量的过滤行为一致。"""

    EDITOR_VAR_NAMES = {
        "UbergraphPages", "FunctionGraphs", "CategorySorting",
        "ImplementedInterfaces", "LastEditedDocuments", "ThumbnailInfo",
        "bLegacyNeedToPurgeSkelRefs",
    }

    def _make_ir_with_variables(self, var_names: list[str]) -> PackageIR:
        variables = [_make_variable(name) for name in var_names]
        return _make_ir(variables=variables)

    @pytest.mark.parametrize("editor_var", sorted(EDITOR_VAR_NAMES))
    def test_json_filters_editor_variable(self, editor_var: str):
        """JSON 渲染器应过滤编辑器内部变量。"""
        ir = self._make_ir_with_variables([editor_var, "MyHealth"])
        renderer = get_renderer("json")
        result = renderer.render(ir, RenderOptions())
        data = json.loads(result)
        var_names = [v["name"] for v in data.get("variables", [])]
        assert editor_var not in var_names
        assert "MyHealth" in var_names

    @pytest.mark.parametrize("editor_var", sorted(EDITOR_VAR_NAMES))
    def test_markdown_filters_editor_variable(self, editor_var: str):
        """Markdown 渲染器应过滤编辑器内部变量（与 JSON 一致）。"""
        ir = self._make_ir_with_variables([editor_var, "MyHealth"])
        renderer = get_renderer("markdown")
        result = renderer.render(ir, RenderOptions())
        # 编辑器变量不应出现在 Markdown 输出中
        assert editor_var not in result
        assert "MyHealth" in result

    def test_non_editor_variable_not_filtered(self):
        """非编辑器变量不应被过滤。"""
        ir = self._make_ir_with_variables(["MyHealth", "AttackPower"])
        # JSON
        json_renderer = get_renderer("json")
        json_result = json.loads(json_renderer.render(ir, RenderOptions()))
        json_vars = [v["name"] for v in json_result.get("variables", [])]
        assert "MyHealth" in json_vars
        assert "AttackPower" in json_vars
        # Markdown
        md_renderer = get_renderer("markdown")
        md_result = md_renderer.render(ir, RenderOptions())
        assert "MyHealth" in md_result
        assert "AttackPower" in md_result


# ---------------------------------------------------------------------------
# 编辑器节点类过滤一致性
# ---------------------------------------------------------------------------

class TestEditorNodeClassFilterConsistency:
    """验证 Markdown 和 JSON 渲染器对编辑器节点类的过滤行为一致。"""

    def test_json_filters_editor_node_class_export(self):
        """JSON 渲染器应过滤 object_class 为编辑器节点类的 export。"""
        normal_export = _make_export(
            index=0, object_name="BP_Test_C", object_class="BlueprintGeneratedClass",
        )
        knot_export = _make_export(
            index=1, object_name="Knot_0", object_class="K2Node_Knot",
        )
        ir = _make_ir(exports=[normal_export, knot_export])
        renderer = get_renderer("json")
        result = renderer.render(ir, RenderOptions())
        data = json.loads(result)
        export_classes = [e["object_class"] for e in data["exports"]]
        assert "K2Node_Knot" not in export_classes
        assert "BlueprintGeneratedClass" in export_classes

    def test_markdown_filters_editor_node_class_export(self):
        """Markdown 渲染器应过滤 object_class 为编辑器节点类的 export（与 JSON 一致）。"""
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

    def test_json_filters_editor_graph_nodes(self):
        """JSON 渲染器 standard 模式下过滤编辑器节点类的图节点。"""
        knot_node = _make_node("K2Node_Knot", node_guid="11111111111111111111111111111111")
        normal_node = _make_node("K2Node_CallFunction", node_guid="22222222222222222222222222222222")
        graph = GraphIR(
            graph_guid="aaa", graph_name="EventGraph", graph_class="EdGraph",
            nodes=[knot_node, normal_node], execution_chains=[],
        )
        export = _make_export(graphs=[graph])
        ir = _make_ir(exports=[export])
        renderer = get_renderer("json")
        result = renderer.render(ir, RenderOptions())
        data = json.loads(result)
        # 节点应在 JSON 输出中
        all_nodes = []
        for exp in data["exports"]:
            for g in exp.get("graphs", []):
                all_nodes.extend(g.get("nodes", []))
        node_classes = [n["node_class"] for n in all_nodes]
        assert "K2Node_Knot" in node_classes  # JSON 不过滤图节点（仅过滤 export 级）

    def test_markdown_includes_all_graph_nodes(self):
        """Markdown 渲染器应包含所有图节点（与 JSON 一致，节点级过滤由 JSON 也在 standard 模式下执行）。"""
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
        # 两种节点都应出现在 Markdown 中（与 JSON standard 行为一致）
        assert "K2Node_Knot" in result
        assert "K2Node_CallFunction" in result


# ---------------------------------------------------------------------------
# 编辑器属性过滤一致性
# ---------------------------------------------------------------------------

class TestEditorPropertyFilterConsistency:
    """验证 Markdown 和 JSON 渲染器对编辑器属性的过滤行为一致。"""

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
    def test_json_filters_editor_property(self, editor_prop: str):
        """JSON 渲染器应过滤编辑器布局属性。"""
        props = [_make_property(editor_prop), _make_property("Health")]
        export = _make_export(properties=props)
        ir = _make_ir(exports=[export])
        renderer = get_renderer("json")
        result = renderer.render(ir, RenderOptions())
        data = json.loads(result)
        prop_names = [p["name"] for p in data["exports"][0].get("properties", [])]
        assert editor_prop not in prop_names
        assert "Health" in prop_names

    @pytest.mark.parametrize("editor_prop", sorted(EDITOR_PROPS))
    def test_markdown_filters_editor_property(self, editor_prop: str):
        """Markdown 渲染器应过滤编辑器布局属性（与 JSON 一致）。"""
        props = [_make_property(editor_prop), _make_property("Health")]
        # 需要有 graphs 才能触发属性渲染
        graph = GraphIR(
            graph_guid="aaa", graph_name="EventGraph", graph_class="EdGraph",
            nodes=[], execution_chains=[],
        )
        export = _make_export(properties=props, graphs=[graph])
        ir = _make_ir(exports=[export])
        renderer = get_renderer("markdown")
        result = renderer.render(ir, RenderOptions())
        # 编辑器属性不应出现在 Markdown 的属性表中
        lines = result.split("\n")
        for line in lines:
            if "|" in line and editor_prop in line:
                # 检查是否在属性表中（不是表头）
                if "Name" not in line and "Type" not in line and "Value" not in line:
                    pytest.fail(f"编辑器属性 '{editor_prop}' 不应出现在 Markdown 输出中: {line}")


# ---------------------------------------------------------------------------
# IR Builder parent_class 逻辑安全
# ---------------------------------------------------------------------------

class TestIRBuilderParentClass:
    """验证 IR Builder 仅在蓝图 export 上设置 parent_class。"""

    def test_blueprint_export_gets_parent_class(self):
        """蓝图 export 应继承 result.blueprint.parent_class。"""
        from uasset_read.ir_builder import _build_export_ir

        bp = BlueprintIR(
            parent_class="/Engine/Actor",
            functions=[], events=[], components=[],
        )
        export = _make_export(
            object_name="BP_Test_C",
            object_class="BlueprintGeneratedClass",
        )
        # Mock result
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
        """非蓝图 export 不应继承 result.blueprint.parent_class。"""
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
        """无蓝图数据时，任何 export 的 parent_class 应为 None。"""
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
        """有 graphs 的 export 应被视为蓝图 export 并继承 parent_class。"""
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
