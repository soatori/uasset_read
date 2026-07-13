"""测试嵌套子图解析支持 (Issue #178)。"""
import pytest
from unittest.mock import MagicMock

from uasset_read.models.core import UEdGraph, UEdGraphNode
from uasset_read.models.ir import GraphIR, NodeIR, PinIR
from uasset_read.ir_builder import _build_graph_ir, _build_node_ir


class TestSubgraphParsing:
    """测试嵌套子图解析。"""

    def test_uegraph_subgraphs_field(self):
        """测试 UEdGraph 支持 subgraphs 字段。"""
        graph = UEdGraph(
            graph_name="TestGraph",
            graph_class="AnimationGraph",
        )
        assert hasattr(graph, "subgraphs")
        assert graph.subgraphs == []

    def test_uegraph_with_subgraphs(self):
        """测试带有子图的 UEdGraph。"""
        child_graph = UEdGraph(
            graph_name="ChildGraph",
            graph_class="AnimationStateGraph",
        )
        parent_graph = UEdGraph(
            graph_name="ParentGraph",
            graph_class="AnimationStateMachineGraph",
            subgraphs=[child_graph],
        )
        assert len(parent_graph.subgraphs) == 1
        assert parent_graph.subgraphs[0].graph_name == "ChildGraph"

    def test_graphir_subgraphs_field(self):
        """测试 GraphIR 支持 subgraphs 字段。"""
        graph_ir = GraphIR(
            graph_guid="test-guid",
            graph_name="TestGraph",
            graph_class="AnimationGraph",
            nodes=[],
            execution_chains=[],
        )
        assert hasattr(graph_ir, "subgraphs")
        assert graph_ir.subgraphs == []

    def test_graphir_with_subgraphs(self):
        """测试带有子图的 GraphIR。"""
        child_ir = GraphIR(
            graph_guid="child-guid",
            graph_name="ChildGraph",
            graph_class="AnimationStateGraph",
            nodes=[],
            execution_chains=[],
        )
        parent_ir = GraphIR(
            graph_guid="parent-guid",
            graph_name="ParentGraph",
            graph_class="AnimationStateMachineGraph",
            nodes=[],
            execution_chains=[],
            subgraphs=[child_ir],
        )
        assert len(parent_ir.subgraphs) == 1
        assert parent_ir.subgraphs[0].graph_name == "ChildGraph"

    def test_graphir_graph_type(self):
        """测试 GraphIR 支持 graph_type 字段。"""
        graph_ir = GraphIR(
            graph_guid="test-guid",
            graph_name="StateMachine",
            graph_class="AnimationStateMachineGraph",
            nodes=[],
            execution_chains=[],
            graph_type="state_machine",
        )
        assert graph_ir.graph_type == "state_machine"

    def test_build_graph_ir_with_subgraphs(self):
        """测试 _build_graph_ir 正确构建嵌套子图。"""
        # 创建子图
        child_node = UEdGraphNode(
            node_guid="child-node-guid",
            node_comment="State Result",
            class_name="AnimGraphNode_StateResult",
            pins=[],
        )
        child_graph = UEdGraph(
            graph_name="Idle Loop",
            graph_class="AnimationStateGraph",
            nodes=[child_node],
        )

        # 创建父图
        parent_node = UEdGraphNode(
            node_guid="parent-node-guid",
            node_comment="State Machine",
            class_name="AnimGraphNode_StateMachine",
            pins=[],
        )
        parent_graph = UEdGraph(
            graph_name="AnimGraph",
            graph_class="AnimationGraph",
            nodes=[parent_node],
            subgraphs=[child_graph],
        )

        # 构建 IR
        graph_ir = _build_graph_ir(parent_graph)

        # 验证
        assert graph_ir.graph_name == "AnimGraph"
        assert len(graph_ir.nodes) == 1
        assert len(graph_ir.subgraphs) == 1
        assert graph_ir.subgraphs[0].graph_name == "Idle Loop"
        assert graph_ir.subgraphs[0].graph_class == "AnimationStateGraph"

    def test_nested_subgraphs(self):
        """测试多层嵌套子图。"""
        # 创建最深层子图
        deep_graph = UEdGraph(
            graph_name="DeepGraph",
            graph_class="AnimationStateGraph",
        )

        # 创建中间层子图
        mid_graph = UEdGraph(
            graph_name="MidGraph",
            graph_class="AnimationStateMachineGraph",
            subgraphs=[deep_graph],
        )

        # 创建顶层图
        top_graph = UEdGraph(
            graph_name="TopGraph",
            graph_class="AnimationGraph",
            subgraphs=[mid_graph],
        )

        # 构建 IR
        graph_ir = _build_graph_ir(top_graph)

        # 验证多层嵌套
        assert len(graph_ir.subgraphs) == 1
        assert graph_ir.subgraphs[0].graph_name == "MidGraph"
        assert len(graph_ir.subgraphs[0].subgraphs) == 1
        assert graph_ir.subgraphs[0].subgraphs[0].graph_name == "DeepGraph"


class TestAnimGraphNodeParsing:
    """测试 AnimGraphNode 解析。"""

    def test_anim_graph_node_data_structure(self):
        """测试 AnimGraphNode node_data 结构。"""
        from uasset_read.serializers.graph_node import _read_anim_graph_node

        # 模拟 raw_properties
        raw_properties = {
            "EditorStateMachineGraph": 123,
            "EditorStateMachineGraphPackageIndex": 123,
        }

        # 调用函数
        result = _read_anim_graph_node(
            archive=None,
            name_map=[],
            summary=None,
            export_map=[],
            import_map=[],
            linker=None,
            class_name="AnimGraphNode_StateMachine",
            raw_properties=raw_properties,
        )

        # 验证
        assert result["node_type"] == "AnimGraphNode_StateMachine"
        # 无 linker 且 export_map 为空时，subgraph_references 不会被添加
        # 因为 PackageIndex 无法解析（pkg_idx > len(export_map)）
        # 但 node_type 应该正确设置


class TestJsonRendererSubgraphs:
    """测试 JSON 渲染器支持嵌套子图。"""

    def test_json_renderer_includes_subgraphs(self):
        """测试 JSON 输出包含嵌套子图。"""
        from uasset_read.renderers.json_renderer import JSONRenderer
        from uasset_read.models.ir import PackageIR, PackageHeaderIR

        # 创建带子图的 GraphIR
        child_ir = GraphIR(
            graph_guid="child-guid",
            graph_name="ChildGraph",
            graph_class="AnimationStateGraph",
            nodes=[],
            execution_chains=[],
        )
        graph_ir = GraphIR(
            graph_guid="parent-guid",
            graph_name="ParentGraph",
            graph_class="AnimationStateMachineGraph",
            nodes=[],
            execution_chains=[],
            subgraphs=[child_ir],
            graph_type="state_machine",
        )

        # 创建 ExportIR
        from uasset_read.models.ir import ExportIR
        export_ir = ExportIR(
            index=0,
            object_name="TestExport",
            object_class="AnimBlueprint",
            serial_size=100,
            outer_index_resolved=None,
            super_index_resolved=None,
            parent_class=None,
            properties=[],
            graphs=[graph_ir],
            bulk_data=None,
        )

        # 创建 PackageIR
        header = PackageHeaderIR(
            package_name="TestPackage",
            package_class="AnimBlueprint",
            package_flags=0,
            total_export_count=1,
            total_import_count=0,
            ue_version="5.x",
        )
        package_ir = PackageIR(
            header=header,
            name_map=[],
            imports=[],
            exports=[export_ir],
            linker=None,
        )

        # 渲染
        renderer = JSONRenderer()
        from uasset_read.renderers.base import RenderOptions
        options = RenderOptions(output_level="debug")
        output = renderer.render(package_ir, options)

        # 验证 JSON 输出包含子图
        import json
        data = json.loads(output)
        graphs = data["exports"][0]["graphs"]
        assert len(graphs) == 1
        assert "subgraphs" in graphs[0]
        assert len(graphs[0]["subgraphs"]) == 1
        assert graphs[0]["subgraphs"][0]["graph_name"] == "ChildGraph"
        assert graphs[0]["graph_type"] == "state_machine"
