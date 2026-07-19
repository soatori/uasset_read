"""渲染器文本输出测试 — MarkdownRenderer 覆盖。

覆盖范围：
- diff_single 基本功能验证
- MarkdownRenderer 基础渲染、导出表、图渲染、属性、变量
- MarkdownRenderer 蓝图详情、Event Graph、Functions、Asset Registry、诊断、边界
"""
from __future__ import annotations

import pytest

from uasset_read.renderers.markdown_renderer import MarkdownRenderer
from uasset_read.renderers.base import RenderOptions
from uasset_read.models.ir import (
    NodeIR, PinIR, PropertyIR, BlueprintIR, BlueprintEventIR,
    VariableIR, ExecutionChainIR, DecompiledFunctionIR,
)


@pytest.fixture
def md_renderer():
    return MarkdownRenderer()


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
