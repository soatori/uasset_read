"""MarkdownRenderer 单元测试。"""

import pytest

from uasset_read.renderers.markdown_renderer import MarkdownRenderer
from uasset_read.renderers.base import RenderOptions, EDITOR_PROPERTY_NAMES, EDITOR_VARIABLE_NAMES


@pytest.fixture
def renderer():
    return MarkdownRenderer()


class TestMarkdownRendererBasic:
    """基础渲染功能测试。"""

    def test_render_returns_string(self, renderer, make_package_ir):
        """render 返回非空字符串。"""
        ir = make_package_ir()
        result = renderer.render(ir, RenderOptions())

        assert isinstance(result, str)
        assert len(result) > 0

    def test_render_includes_package_name(self, renderer, make_package_ir):
        """输出包含包名作为标题。"""
        ir = make_package_ir(name="TestBP")
        result = renderer.render(ir, RenderOptions())

        assert "# TestBP" in result

    def test_render_includes_asset_overview(self, renderer, make_package_ir):
        """输出包含 Asset Overview 表格。"""
        ir = make_package_ir()
        result = renderer.render(ir, RenderOptions())

        assert "## Asset Overview" in result
        assert "| Field | Value |" in result

    def test_render_overview_contains_metadata(self, renderer, make_package_ir):
        """Asset Overview 包含元数据字段。"""
        ir = make_package_ir(name="PkgName")
        result = renderer.render(ir, RenderOptions())

        assert "PkgName" in result
        assert "| Package |" in result
        assert "| Class |" in result
        assert "| Flags |" in result
        assert "| Exports |" in result
        assert "| Imports |" in result
        assert "| UE Version |" in result

    def test_render_empty_content(self, renderer, make_package_ir):
        """无 export 时不崩溃，输出基本结构。"""
        ir = make_package_ir(exports=[])
        result = renderer.render(ir, RenderOptions())

        assert isinstance(result, str)
        assert "# " in result
        assert "## Asset Overview" in result

    def test_format_name(self, renderer):
        """format_name 属性返回 markdown。"""
        assert renderer.format_name == "markdown"

    def test_package_name_with_slash(self, renderer, make_package_ir):
        """包名含 / 时取最后一段作为标题。"""
        ir = make_package_ir(name="Game/Characters/BP_Hero")
        result = renderer.render(ir, RenderOptions())

        # 标题用最后一段
        assert "# BP_Hero" in result
        # Overview 表用完整路径
        assert "Game/Characters/BP_Hero" in result


class TestMarkdownRendererExports:
    """导出表渲染测试。"""

    def test_blueprint_export_included(self, renderer, make_package_ir, make_export_ir):
        """蓝图 export（_C 后缀）在 Exports 表中显示。"""
        export = make_export_ir(object_name="BP_TestCharacter_C")
        ir = make_package_ir(exports=[export])
        result = renderer.render(ir, RenderOptions())

        assert "## Exports" in result
        assert "BP_TestCharacter_C" in result

    def test_non_blueprint_export_excluded(self, renderer, make_package_ir, make_export_ir):
        """非蓝图 export（无 _C 后缀且无 graph）不显示。"""
        export = make_export_ir(
            object_name="SomeData",
            class_name="DataTable",
        )
        ir = make_package_ir(exports=[export])
        result = renderer.render(ir, RenderOptions())

        assert "## Exports" not in result
        assert "SomeData" not in result

    def test_export_with_graphs_shown(self, renderer, make_package_ir, make_export_ir,
                                      make_graph_ir):
        """有 graph 的 export 即使无 _C 后缀也显示。"""
        graph = make_graph_ir(name="EventGraph")
        export = make_export_ir(
            object_name="TestExport",
            class_name="SomeClass",
            graphs=[graph],
        )
        ir = make_package_ir(exports=[export])
        result = renderer.render(ir, RenderOptions())

        assert "## Exports" in result
        assert "TestExport" in result

    def test_export_table_columns(self, renderer, make_package_ir, make_export_ir):
        """Exports 表包含 Name、Class、Size、Properties 列。"""
        export = make_export_ir(object_name="BP_Test_C", serial_size=2048)
        ir = make_package_ir(exports=[export])
        result = renderer.render(ir, RenderOptions())

        assert "| Name | Class | Size | Properties |" in result
        assert "2048" in result

    def test_editor_node_class_excluded(self, renderer, make_package_ir, make_export_ir):
        """编辑器节点类（如 K2Node_Knot）不在 Exports 中显示。"""
        export = make_export_ir(
            object_name="K2Node_Knot_C",
            class_name="K2Node_Knot",
        )
        ir = make_package_ir(exports=[export])
        result = renderer.render(ir, RenderOptions())

        assert "## Exports" not in result

    def test_multiple_exports(self, renderer, make_package_ir, make_export_ir):
        """多个蓝图 export 按顺序渲染。"""
        e1 = make_export_ir(index=0, object_name="BP_First_C")
        e2 = make_export_ir(index=1, object_name="BP_Second_C")
        ir = make_package_ir(exports=[e1, e2])
        result = renderer.render(ir, RenderOptions())

        # 两个 export 都应出现
        assert "BP_First_C" in result
        assert "BP_Second_C" in result
        # BP_First_C 在 BP_Second_C 之前
        assert result.index("BP_First_C") < result.index("BP_Second_C")


class TestMarkdownRendererGraphs:
    """图渲染测试。"""

    def test_graph_heading(self, renderer, make_package_ir, make_export_ir, make_graph_ir):
        """渲染图时生成 Graph: {name} 标题。"""
        graph = make_graph_ir(name="EventGraph")
        export = make_export_ir(graphs=[graph])
        ir = make_package_ir(exports=[export])
        result = renderer.render(ir, RenderOptions())

        assert "## Graph: EventGraph" in result

    def test_graph_node_count(self, renderer, make_package_ir, make_export_ir,
                              make_graph_ir, make_node_ir):
        """图标题下方显示节点数量。"""
        n1 = make_node_ir()
        n2 = make_node_ir()
        graph = make_graph_ir(name="G", nodes=[n1, n2])
        export = make_export_ir(graphs=[graph])
        ir = make_package_ir(exports=[export])
        result = renderer.render(ir, RenderOptions())

        assert "**Nodes**: 2" in result

    def test_mermaid_code_block(self, renderer, make_package_ir, make_export_ir,
                                make_graph_ir, make_node_ir):
        """有节点时生成 Mermaid 代码块。"""
        node = make_node_ir(node_comment="MyNode")
        graph = make_graph_ir(name="EventGraph", nodes=[node])
        export = make_export_ir(graphs=[graph])
        ir = make_package_ir(exports=[export])
        result = renderer.render(ir, RenderOptions())

        assert "```mermaid" in result
        assert "graph TD" in result

    def test_mermaid_uses_node_comment(self, renderer, make_package_ir, make_export_ir,
                                       make_graph_ir, make_node_ir):
        """Mermaid 节点标签优先使用 node_comment。"""
        node = make_node_ir(node_comment="BeginPlay")
        graph = make_graph_ir(nodes=[node])
        export = make_export_ir(graphs=[graph])
        ir = make_package_ir(exports=[export])
        result = renderer.render(ir, RenderOptions())

        assert "BeginPlay" in result

    def test_mermaid_fallback_to_node_class(self, renderer, make_package_ir, make_export_ir,
                                            make_graph_ir, make_node_ir):
        """无 node_comment 时 Mermaid 使用 node_class 作为标签。"""
        node = make_node_ir(node_comment=None, node_class="K2Node_Event")
        graph = make_graph_ir(nodes=[node])
        export = make_export_ir(graphs=[graph])
        ir = make_package_ir(exports=[export])
        result = renderer.render(ir, RenderOptions())

        assert "K2Node_Event" in result

    def test_mermaid_edges_from_pin_links(self, renderer, make_package_ir, make_export_ir,
                                          make_graph_ir):
        """Pin 的 linked_to 生成 Mermaid 边连接，使用 Node GUID。"""
        from uasset_read.models.ir import PinIR, NodeIR

        pin_b = PinIR(
            pin_name="In", pin_type="exec", linked_to=[],
            direction="input", default_value=None,
            pin_guid="22222222222222222222222222222222",
        )
        node_b = NodeIR(
            node_guid="bbbbbbbb000000000000000000000002",
            node_class="K2Node_Event", node_comment="NodeB",
            pins=[pin_b], execution_flow=[],
        )

        pin_a = PinIR(
            pin_name="Out", pin_type="exec",
            linked_to=["22222222222222222222222222222222"],
            direction="output", default_value=None,
            pin_guid="11111111111111111111111111111111",
        )
        node_a = NodeIR(
            node_guid="aaaaaaaa000000000000000000000001",
            node_class="K2Node_Event", node_comment="NodeA",
            pins=[pin_a], execution_flow=[],
        )

        graph = make_graph_ir(nodes=[node_a, node_b])
        export = make_export_ir(graphs=[graph])
        ir = make_package_ir(exports=[export])
        result = renderer.render(ir, RenderOptions())

        # 边使用 Node GUID 的前 8 位，而非 Pin GUID
        assert "aaaaaaaa" in result
        assert "bbbbbbbb" in result
        assert "aaaaaaaa --> bbbbbbbb" in result

    def test_mermaid_edges_use_node_guid_not_pin_guid(self, renderer, make_package_ir,
                                                      make_export_ir, make_graph_ir):
        """边使用 Node GUID 而非 Pin GUID 作为目标节点。"""
        from uasset_read.models.ir import PinIR, NodeIR

        # Pin GUID 和 Node GUID 完全不同
        pin_target = PinIR(
            pin_name="In", pin_type="exec", linked_to=[],
            direction="input", default_value=None,
            pin_guid="pin_guid_pin_guid_pin_guid_pingu",
        )
        node_target = NodeIR(
            node_guid="node_guid_node_guid_node_guid_no",
            node_class="K2Node_CallFunction", node_comment="TargetNode",
            pins=[pin_target], execution_flow=[],
        )

        pin_source = PinIR(
            pin_name="Out", pin_type="exec",
            linked_to=["pin_guid_pin_guid_pin_guid_pingu"],
            direction="output", default_value=None,
            pin_guid="src_pin_guid_src_pin_guid_srcpi",
        )
        node_source = NodeIR(
            node_guid="src_node_guid_src_node_guid_srn",
            node_class="K2Node_Event", node_comment="SourceNode",
            pins=[pin_source], execution_flow=[],
        )

        graph = make_graph_ir(nodes=[node_source, node_target])
        export = make_export_ir(graphs=[graph])
        ir = make_package_ir(exports=[export])
        result = renderer.render(ir, RenderOptions())

        # 边应使用 Node GUID 前 8 位，而非 Pin GUID
        assert "node_gui" in result  # node_guid 前 8 位
        assert "src_node" in result  # src_node_guid 前 8 位
        assert "pin_gui" not in result  # pin_guid 不应出现在边中

    def test_mermaid_self_loop_filtered(self, renderer, make_package_ir, make_export_ir,
                                        make_graph_ir):
        """自连接边被过滤。"""
        from uasset_read.models.ir import PinIR, NodeIR

        # Pin 的 linked_to 指向自身节点的 Pin
        pin_self = PinIR(
            pin_name="Loop", pin_type="exec",
            linked_to=["self_pin_guid_self_pin_guid_self"],
            direction="output", default_value=None,
            pin_guid="self_pin_guid_self_pin_guid_self",
        )
        node_self = NodeIR(
            node_guid="self_node_self_node_self_node_no",
            node_class="K2Node_Knot", node_comment="SelfLoop",
            pins=[pin_self], execution_flow=[],
        )

        graph = make_graph_ir(nodes=[node_self])
        export = make_export_ir(graphs=[graph])
        ir = make_package_ir(exports=[export])
        result = renderer.render(ir, RenderOptions())

        # 不应有自连接边
        assert "self_nod" not in result or "-->" not in result.split("self_nod")[0].split("\n")[-1]

    def test_mermaid_unresolvable_pin_guid_skipped(self, renderer, make_package_ir,
                                                   make_export_ir, make_graph_ir):
        """无法解析的 Pin GUID 引用被跳过，不生成边。"""
        from uasset_read.models.ir import PinIR, NodeIR

        pin_a = PinIR(
            pin_name="Out", pin_type="exec",
            linked_to=["nonexistent_pin_guid_nonexist"],
            direction="output", default_value=None,
            pin_guid="aaaaaaaa111111111111111111111111",
        )
        node_a = NodeIR(
            node_guid="aaaaaaaa000000000000000000000001",
            node_class="K2Node_Event", node_comment="NodeA",
            pins=[pin_a], execution_flow=[],
        )

        graph = make_graph_ir(nodes=[node_a])
        export = make_export_ir(graphs=[graph])
        ir = make_package_ir(exports=[export])
        result = renderer.render(ir, RenderOptions())

        # 无有效连接时不应有边
        assert "-->" not in result

    def test_empty_graph_no_mermaid(self, renderer, make_package_ir, make_export_ir, make_graph_ir):
        """无节点的图不生成 Mermaid 代码块。"""
        graph = make_graph_ir(name="EmptyGraph", nodes=[])
        export = make_export_ir(graphs=[graph])
        ir = make_package_ir(exports=[export])
        result = renderer.render(ir, RenderOptions())

        assert "```mermaid" not in result

    def test_graph_execution_chains_count(self, renderer, make_package_ir, make_export_ir,
                                          make_graph_ir):
        """有 execution_chains 时显示链数量。"""
        graph = make_graph_ir(
            name="EventGraph",
            execution_chains=[["A", "B"], ["C", "D"]],
        )
        export = make_export_ir(graphs=[graph])
        ir = make_package_ir(exports=[export])
        result = renderer.render(ir, RenderOptions())

        assert "**Execution Chains**: 2" in result

    def test_graph_type_shown(self, renderer, make_package_ir, make_export_ir, make_graph_ir):
        """有 graph_type 时显示类型。"""
        graph = make_graph_ir(name="EventGraph", graph_type="EventGraph")
        export = make_export_ir(graphs=[graph])
        ir = make_package_ir(exports=[export])
        result = renderer.render(ir, RenderOptions())

        assert "**Type**: EventGraph" in result


class TestMarkdownRendererProperties:
    """属性渲染测试。"""

    def test_properties_table(self, renderer, make_package_ir, make_export_ir, make_graph_ir):
        """export 属性在 Properties 表中显示。"""
        from uasset_read.models.ir import PropertyIR

        prop = PropertyIR(name="Health", type="FloatProperty", value=100.0,
                          array_index=0, guid=None)
        graph = make_graph_ir(nodes=[])
        export = make_export_ir(properties=[prop], graphs=[graph])
        ir = make_package_ir(exports=[export])
        result = renderer.render(ir, RenderOptions())

        assert "### Properties" in result
        assert "| Name | Type | Value |" in result
        assert "Health" in result
        assert "FloatProperty" in result

    def test_editor_property_filtered(self, renderer, make_package_ir, make_export_ir, make_graph_ir):
        """编辑器布局属性（如 NodePosX）被过滤。"""
        from uasset_read.models.ir import PropertyIR

        props = [
            PropertyIR(name="NodePosX", type="int", value=100, array_index=0, guid=None),
            PropertyIR(name="GameProp", type="int", value=42, array_index=0, guid=None),
        ]
        graph = make_graph_ir(nodes=[])
        export = make_export_ir(properties=props, graphs=[graph])
        ir = make_package_ir(exports=[export])
        result = renderer.render(ir, RenderOptions())

        assert "NodePosX" not in result
        assert "GameProp" in result

    def test_all_editor_properties_no_section(self, renderer, make_package_ir, make_export_ir, make_graph_ir):
        """全部为编辑器属性时不输出 Properties 章节。"""
        from uasset_read.models.ir import PropertyIR

        props = [
            PropertyIR(name="NodePosX", type="int", value=0, array_index=0, guid=None),
            PropertyIR(name="NodePosY", type="int", value=0, array_index=0, guid=None),
        ]
        graph = make_graph_ir(nodes=[])
        export = make_export_ir(properties=props, graphs=[graph])
        ir = make_package_ir(exports=[export])
        result = renderer.render(ir, RenderOptions())

        assert "### Properties" not in result

    def test_null_property_value(self, renderer, make_package_ir, make_export_ir, make_graph_ir):
        """属性值为 null 时显示 null。"""
        from uasset_read.models.ir import PropertyIR

        prop = PropertyIR(name="OptionalRef", type="ObjectProperty", value=None,
                          array_index=0, guid=None)
        graph = make_graph_ir(nodes=[])
        export = make_export_ir(properties=[prop], graphs=[graph])
        ir = make_package_ir(exports=[export])
        result = renderer.render(ir, RenderOptions())

        assert "null" in result

    def test_properties_rendered_without_graphs(self, renderer, make_package_ir, make_export_ir):
        """export 无 graph 时仍渲染属性表格（回归测试 #362）。"""
        from uasset_read.models.ir import PropertyIR

        prop = PropertyIR(name="Health", type="FloatProperty", value=100.0,
                          array_index=0, guid=None)
        export = make_export_ir(object_name="BP_Test_C", properties=[prop], graphs=[])
        ir = make_package_ir(exports=[export])
        result = renderer.render(ir, RenderOptions())

        assert "### Properties" in result
        assert "Health" in result
        assert "FloatProperty" in result


class TestMarkdownRendererVariables:
    """变量渲染测试。"""

    def test_variables_section(self, renderer, make_package_ir):
        """用户变量在 Variables 表中显示。"""
        from uasset_read.models.ir import VariableIR

        var = VariableIR(name="Health", type="FloatProperty", default_value="100.0")
        ir = make_package_ir(variables=[var])
        result = renderer.render(ir, RenderOptions())

        assert "## Variables" in result
        assert "| Name | Type | Default Value |" in result
        assert "Health" in result
        assert "FloatProperty" in result

    def test_editor_variable_filtered(self, renderer, make_package_ir):
        """编辑器内部变量被过滤。"""
        from uasset_read.models.ir import VariableIR

        var = VariableIR(name="UbergraphPages", type="ArrayProperty", default_value="[]")
        ir = make_package_ir(variables=[var])
        result = renderer.render(ir, RenderOptions())

        # 全部为编辑器变量时，Variables 章节不输出
        assert "## Variables" not in result

    def test_mixed_variables_filtered_correctly(self, renderer, make_package_ir):
        """混合变量时只过滤编辑器变量。"""
        from uasset_read.models.ir import VariableIR

        vars_ = [
            VariableIR(name="UbergraphPages", type="ArrayProperty", default_value="[]"),
            VariableIR(name="Health", type="FloatProperty", default_value="100.0"),
        ]
        ir = make_package_ir(variables=vars_)
        result = renderer.render(ir, RenderOptions())

        assert "Health" in result
        assert "UbergraphPages" not in result

    def test_no_variables_no_section(self, renderer, make_package_ir):
        """无变量时不输出 Variables 章节。"""
        ir = make_package_ir(variables=[])
        result = renderer.render(ir, RenderOptions())

        assert "## Variables" not in result


class TestMarkdownRendererBlueprintDetails:
    """蓝图详情渲染测试。"""

    def test_blueprint_parent_class(self, renderer, make_package_ir):
        """蓝图详情显示 Parent Class。"""
        from uasset_read.models.ir import BlueprintIR

        ir_obj = make_package_ir()
        ir_obj.blueprint = BlueprintIR(
            parent_class="Character",
            description="Test blueprint",
        )
        result = renderer.render(ir_obj, RenderOptions())

        assert "## Blueprint Details" in result
        assert "Character" in result

    def test_blueprint_description(self, renderer, make_package_ir):
        """蓝图详情显示 Description。"""
        from uasset_read.models.ir import BlueprintIR

        ir_obj = make_package_ir()
        ir_obj.blueprint = BlueprintIR(
            parent_class="Actor",
            description="A test description",
        )
        result = renderer.render(ir_obj, RenderOptions())

        assert "A test description" in result

    def test_blueprint_interfaces(self, renderer, make_package_ir):
        """蓝图详情显示 Interfaces。"""
        from uasset_read.models.ir import BlueprintIR

        ir_obj = make_package_ir()
        ir_obj.blueprint = BlueprintIR(
            parent_class="Actor",
            interfaces=[{"name": "IInteractable"}],
        )
        result = renderer.render(ir_obj, RenderOptions())

        assert "IInteractable" in result

    def test_no_blueprint_no_details(self, renderer, make_package_ir):
        """无蓝图时不输出 Blueprint Details。"""
        ir = make_package_ir()
        result = renderer.render(ir, RenderOptions())

        assert "## Blueprint Details" not in result


class TestMarkdownRendererEventGraph:
    """Event Graph 渲染测试。"""

    def test_event_graph_section(self, renderer, make_package_ir):
        """有事件时生成 Event Graph 章节。"""
        from uasset_read.models.ir import BlueprintIR, BlueprintEventIR

        ir_obj = make_package_ir()
        event = BlueprintEventIR(
            name="ReceiveBeginPlay",
            event_type="custom",
            parameters=[],
        )
        ir_obj.blueprint = BlueprintIR(
            parent_class="Actor",
            events=[event],
        )
        result = renderer.render(ir_obj, RenderOptions())

        assert "## Event Graph" in result
        assert "### ReceiveBeginPlay" in result

    def test_event_graph_cpp_block(self, renderer, make_package_ir):
        """事件生成 C++ 代码块。"""
        from uasset_read.models.ir import BlueprintIR, BlueprintEventIR

        ir_obj = make_package_ir()
        event = BlueprintEventIR(
            name="ReceiveTick",
            event_type="custom",
            parameters=[],
        )
        ir_obj.blueprint = BlueprintIR(
            parent_class="Actor",
            events=[event],
        )
        result = renderer.render(ir_obj, RenderOptions())

        assert "```cpp" in result

    def test_event_with_decompiled_function(self, renderer, make_package_ir):
        """事件匹配反编译函数时使用反编译签名。"""
        from uasset_read.models.ir import (
            BlueprintIR, BlueprintEventIR, DecompiledFunctionIR,
        )

        decompiled = DecompiledFunctionIR(
            name="ReceiveBeginPlay",
            signature="void ATestActor::ReceiveBeginPlay()",
            cpp_code="    Super::ReceiveBeginPlay();\n    // custom logic",
            parameters=[],
            return_type="void",
        )
        event = BlueprintEventIR(
            name="ReceiveBeginPlay",
            event_type="custom",
            parameters=[],
        )
        ir_obj = make_package_ir()
        ir_obj.blueprint = BlueprintIR(
            parent_class="Actor",
            events=[event],
        )
        ir_obj.decompiled_functions = [decompiled]
        result = renderer.render(ir_obj, RenderOptions())

        assert "ATestActor::ReceiveBeginPlay()" in result
        assert "Super::ReceiveBeginPlay()" in result

    def test_event_with_execution_chain(self, renderer, make_package_ir):
        """事件的 execution chain 显示调用链。"""
        from uasset_read.models.ir import (
            BlueprintIR, BlueprintEventIR, ExecutionChainIR,
        )

        event = BlueprintEventIR(
            name="ReceiveBeginPlay",
            event_type="custom",
            parameters=[],
        )
        chain = ExecutionChainIR(
            event="ReceiveBeginPlay",
            chain=["BeginPlay", "SpawnActor", "PlaySound"],
        )
        ir_obj = make_package_ir()
        ir_obj.blueprint = BlueprintIR(
            parent_class="Actor",
            events=[event],
        )
        ir_obj.execution_chains = [chain]
        result = renderer.render(ir_obj, RenderOptions())

        assert "Execution Chain:" in result
        assert "BeginPlay -> SpawnActor -> PlaySound" in result

    def test_execution_chain_standalone(self, renderer, make_package_ir):
        """execution_chain 中未在 events 里列出的事件单独渲染。"""
        from uasset_read.models.ir import ExecutionChainIR

        chain = ExecutionChainIR(
            event="CustomEvent",
            chain=["Step1", "Step2"],
        )
        ir_obj = make_package_ir()
        ir_obj.execution_chains = [chain]
        result = renderer.render(ir_obj, RenderOptions())

        assert "### CustomEvent" in result
        assert "Step1 -> Step2" in result


class TestMarkdownRendererFunctions:
    """函数渲染测试。"""

    def test_decompiled_function_section(self, renderer, make_package_ir):
        """反编译函数生成 Functions 章节。"""
        from uasset_read.models.ir import DecompiledFunctionIR

        func = DecompiledFunctionIR(
            name="DoSomething",
            signature="void ATestActor::DoSomething(float Value)",
            cpp_code="    Health = Value;",
            parameters=[{"name": "Value", "param_type": "float"}],
            return_type="void",
        )
        ir_obj = make_package_ir()
        ir_obj.decompiled_functions = [func]
        result = renderer.render(ir_obj, RenderOptions())

        assert "## Functions" in result
        assert "### DoSomething" in result
        assert "void ATestActor::DoSomething(float Value)" in result

    def test_function_parameter_table(self, renderer, make_package_ir):
        """函数参数在表格中显示。"""
        from uasset_read.models.ir import DecompiledFunctionIR

        func = DecompiledFunctionIR(
            name="CalcDamage",
            signature="",
            cpp_code="",
            parameters=[
                {"name": "Base", "param_type": "float"},
                {"name": "Multiplier", "param_type": "float", "default_value": "1.0"},
            ],
            return_type="float",
        )
        ir_obj = make_package_ir()
        ir_obj.decompiled_functions = [func]
        result = renderer.render(ir_obj, RenderOptions())

        assert "| Parameter | Type | Default |" in result
        assert "Base" in result
        assert "Multiplier" in result
        assert "1.0" in result

    def test_function_without_signature_generates_one(self, renderer, make_package_ir):
        """无签名时自动从参数生成签名。"""
        from uasset_read.models.ir import DecompiledFunctionIR

        func = DecompiledFunctionIR(
            name="GenSig",
            signature="",
            cpp_code="",
            parameters=[{"name": "X", "param_type": "int"}],
            return_type="void",
        )
        ir_obj = make_package_ir()
        ir_obj.decompiled_functions = [func]
        result = renderer.render(ir_obj, RenderOptions())

        assert "**Signature:** `void GenSig(int X)`" in result

    def test_function_heuristic_warning(self, renderer, make_package_ir):
        """bytecode_confidence=heuristic 时显示警告。"""
        from uasset_read.models.ir import DecompiledFunctionIR

        func = DecompiledFunctionIR(
            name="HeuristicFunc",
            signature="void HeuristicFunc()",
            cpp_code="    // code",
            parameters=[],
            return_type="void",
            bytecode_confidence="heuristic",
        )
        ir_obj = make_package_ir()
        ir_obj.decompiled_functions = [func]
        result = renderer.render(ir_obj, RenderOptions())

        assert "[!WARNING]" in result
        assert "启发式恢复" in result

    def test_no_functions_no_section(self, renderer, make_package_ir):
        """无函数时不输出 Functions 章节。"""
        ir = make_package_ir()
        result = renderer.render(ir, RenderOptions())

        assert "## Functions" not in result


class TestMarkdownRendererAssetRegistry:
    """Asset Registry 渲染测试。"""

    def test_asset_registry_section(self, renderer, make_package_ir):
        """有 asset_registry_data 时输出章节。"""
        ir_obj = make_package_ir()
        ir_obj.asset_registry_data = {
            "objects": [
                {
                    "object_path": "/Game/Characters/BP_Hero",
                    "object_class_name": "BlueprintGeneratedClass",
                    "tags": {"Source": "Editor"},
                },
            ],
        }
        result = renderer.render(ir_obj, RenderOptions())

        assert "## Asset Registry Data" in result
        assert "/Game/Characters/BP_Hero" in result
        assert "BlueprintGeneratedClass" in result
        assert "Source" in result

    def test_no_asset_registry_no_section(self, renderer, make_package_ir):
        """无 asset_registry_data 时不输出。"""
        ir = make_package_ir()
        result = renderer.render(ir, RenderOptions())

        assert "## Asset Registry Data" not in result

    def test_empty_asset_registry_no_section(self, renderer, make_package_ir):
        """asset_registry_data 无 objects 时不输出。"""
        ir_obj = make_package_ir()
        ir_obj.asset_registry_data = {"objects": []}
        result = renderer.render(ir_obj, RenderOptions())

        assert "## Asset Registry Data" not in result


class TestMarkdownRendererDiagnostics:
    """诊断信息渲染测试。"""

    def test_diagnostics_section(self, renderer, make_package_ir):
        """有 diagnostics 时输出诊断表。"""
        class FakeDiag:
            def to_dict(self):
                return {
                    "kind": "offset_mismatch",
                    "module": "export[0]",
                    "object_name": "BP_Test",
                    "field": "SerialSize",
                    "error": "expected 1024, got 2048",
                }

        ir_obj = make_package_ir()
        ir_obj.diagnostics = [FakeDiag()]
        result = renderer.render(ir_obj, RenderOptions())

        assert "## 诊断信息" in result
        assert "| 类型 | 模块 | 对象名 | 字段 | 错误信息 |" in result
        assert "offset_mismatch" in result

    def test_no_diagnostics_no_section(self, renderer, make_package_ir):
        """无 diagnostics 时不输出。"""
        ir = make_package_ir()
        result = renderer.render(ir, RenderOptions())

        assert "## 诊断信息" not in result


class TestMarkdownRendererEdgeCases:
    """边界情况测试。"""

    def test_special_characters_escaped(self, renderer, make_package_ir, make_export_ir):
        """Markdown 表格中的 | 字符被转义。"""
        export = make_export_ir(object_name="BP|Test_C")
        ir = make_package_ir(exports=[export])
        result = renderer.render(ir, RenderOptions())

        # | 应被转义为 \|
        assert "BP\\|Test_C" in result

    def test_empty_graph_name(self, renderer, make_package_ir, make_export_ir, make_graph_ir):
        """空图名正常渲染。"""
        graph = make_graph_ir(name="")
        export = make_export_ir(graphs=[graph])
        ir = make_package_ir(exports=[export])
        result = renderer.render(ir, RenderOptions())

        assert "## Graph: " in result

    def test_empty_node_comment_and_class(self, renderer, make_package_ir, make_export_ir,
                                          make_graph_ir, make_node_ir):
        """node_comment 和 node_class 均为空时不崩溃。"""
        node = make_node_ir(node_comment=None, node_class="")
        graph = make_graph_ir(nodes=[node])
        export = make_export_ir(graphs=[graph])
        ir = make_package_ir(exports=[export])
        result = renderer.render(ir, RenderOptions())

        assert isinstance(result, str)

    def test_long_property_value_truncated(self, renderer, make_package_ir, make_export_ir, make_graph_ir):
        """长属性值被截断到 50 字符。"""
        from uasset_read.models.ir import PropertyIR

        long_val = "A" * 100
        prop = PropertyIR(name="LongProp", type="StrProperty", value=long_val,
                          array_index=0, guid=None)
        graph = make_graph_ir(nodes=[])
        export = make_export_ir(properties=[prop], graphs=[graph])
        ir = make_package_ir(exports=[export])
        result = renderer.render(ir, RenderOptions())

        # 值应被截断为 50 字符
        assert "A" * 50 in result
        assert "A" * 51 not in result
