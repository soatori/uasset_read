"""渲染器核心测试 — 合并自 test_renderer_quality / test_renderer_compat / test_json_renderer。

覆盖范围：
- 渲染器注册表、导入、格式列表
- is_blueprint_export 辅助函数
- JSON 渲染器基础功能、输出级别、蓝图数据、节点/Pin、动画数据
- Markdown 渲染器基础功能、蓝图数据、Event Graph、Functions、Variables、动画数据
- 编辑器变量/节点类/属性过滤一致性
- IR Builder parent_class 逻辑安全
- JSONRenderer 输出、宏展开数据
"""
from __future__ import annotations

import json
from io import StringIO
from pathlib import Path

import pytest

from uasset_read.models.ir import (
    PackageIR,
    PackageHeaderIR,
    ExportIR,
    ExportRawIR,
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
    AnimBlueprintIR,
    AnimSequenceIR,
    AnimMontageIR,
    BakedStateMachineIR,
    BakedStateIR,
    BakedTransitionIR,
    AnimNotifyIR,
)
from uasset_read.renderers import RENDERER_REGISTRY, get_renderer, list_formats, register_renderer
from uasset_read.renderers.base import IRenderer, RenderOptions, is_blueprint_export
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
    defaults = dict(name=name, type="bool", default_value="False", kind="user")
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
    defaults = dict(name=name, type="IntProperty", value=0, array_index=-1, guid=None)
    defaults.update(kwargs)
    return PropertyIR(**defaults)


# ---------------------------------------------------------------------------
# 渲染器注册表和基础导入 (test_renderer_quality)
# ---------------------------------------------------------------------------


class TestRendererQuality:
    def test_renderer_imports(self):
        from uasset_read.renderers import json_renderer
        assert json_renderer is not None

    def test_renderer_registry(self):
        assert len(RENDERER_REGISTRY) > 0

    def test_registry_contains_json_and_markdown(self):
        formats = list_formats()
        assert "json" in formats
        assert "markdown" in formats

    def test_get_renderer_returns_instance(self):
        for name in list_formats():
            renderer = get_renderer(name)
            assert isinstance(renderer, IRenderer)
            assert renderer.format_name == name

    def test_get_renderer_unknown_format_raises(self):
        with pytest.raises(ValueError, match="Unknown render format"):
            get_renderer("nonexistent_format")


class TestIsBlueprintExport:
    def test_name_ends_with_c(self):
        e = _make_export(object_name="BP_Test_C")
        assert is_blueprint_export(e) is True

    def test_has_graphs(self):
        graph = GraphIR(graph_guid="aaa", graph_name="G", graph_class="EdGraph", nodes=[], execution_chains=[])
        e = _make_export(object_name="Texture2D", graphs=[graph])
        assert is_blueprint_export(e) is True

    def test_not_blueprint(self):
        e = _make_export(object_name="Texture2D", graphs=[])
        assert is_blueprint_export(e) is False


class TestJSONRendererBasicQuality:
    def test_render_produces_valid_json(self):
        ir = _make_ir()
        renderer = get_renderer("json")
        result = renderer.render(ir, RenderOptions())
        data = json.loads(result)
        assert isinstance(data, dict)

    def test_render_contains_required_keys(self):
        ir = _make_ir()
        renderer = get_renderer("json")
        result = renderer.render(ir, RenderOptions())
        data = json.loads(result)
        assert "status" in data
        assert "output_version" not in data
        assert "summary" in data
        assert "exports" in data

    def test_render_export_basic_fields(self):
        ir = _make_ir()
        renderer = get_renderer("json")
        result = renderer.render(ir, RenderOptions())
        data = json.loads(result)
        export = data["exports"][0]
        assert export["object_name"] == "BP_Test_C"
        assert export["object_class"] == "BlueprintGeneratedClass"
        assert export["serial_size"] == 1024
        assert export["parent_class"] == "/Engine/Actor"


class TestJSONRendererOutputLevel:
    def test_standard_filters_editor_properties(self):
        prop = PropertyIR(name="NodePosX", type="IntProperty", value=100, array_index=0, guid=None)
        export = _make_export(properties=[prop])
        ir = _make_ir(exports=[export])
        renderer = get_renderer("json")
        result = renderer.render(ir, RenderOptions(output_level="standard"))
        data = json.loads(result)
        props = data["exports"][0].get("properties", [])
        assert not any(p["name"] == "NodePosX" for p in props)

    def test_debug_preserves_editor_properties(self):
        prop = PropertyIR(name="NodePosX", type="IntProperty", value=100, array_index=0, guid=None)
        export = _make_export(properties=[prop])
        ir = _make_ir(exports=[export])
        renderer = get_renderer("json")
        result = renderer.render(ir, RenderOptions(output_level="debug"))
        data = json.loads(result)
        props = data["exports"][0].get("properties", [])
        assert any(p["name"] == "NodePosX" for p in props)

    def test_standard_filters_empty_graphs(self):
        graph = GraphIR(graph_guid="aaa", graph_name="G", graph_class="EdGraph", nodes=[], execution_chains=[])
        export = _make_export(graphs=[graph])
        ir = _make_ir(exports=[export])
        renderer = get_renderer("json")
        result = renderer.render(ir, RenderOptions(output_level="standard"))
        data = json.loads(result)
        assert "graphs" not in data["exports"][0]

    def test_debug_preserves_empty_graphs(self):
        graph = GraphIR(graph_guid="aaa", graph_name="G", graph_class="EdGraph", nodes=[], execution_chains=[])
        export = _make_export(graphs=[graph])
        ir = _make_ir(exports=[export])
        renderer = get_renderer("json")
        result = renderer.render(ir, RenderOptions(output_level="debug"))
        data = json.loads(result)
        assert "graphs" in data["exports"][0]

    def test_standard_filters_editor_variables(self):
        ir = _make_ir()
        ir.variables = [
            VariableIR(name="Health", type="float", default_value="100.0", kind="user"),
            VariableIR(name="UbergraphPages", type="ArrayProperty", default_value=None, kind="metadata"),
        ]
        renderer = get_renderer("json")
        result = renderer.render(ir, RenderOptions(output_level="standard"))
        data = json.loads(result)
        var_names = [v["name"] for v in data.get("variables", [])]
        assert "Health" in var_names
        assert "UbergraphPages" not in var_names

    def test_debug_preserves_editor_variables(self):
        ir = _make_ir()
        ir.variables = [
            VariableIR(name="Health", type="float", default_value="100.0", kind="user"),
            VariableIR(name="UbergraphPages", type="ArrayProperty", default_value=None, kind="metadata"),
        ]
        renderer = get_renderer("json")
        result = renderer.render(ir, RenderOptions(output_level="debug"))
        data = json.loads(result)
        var_names = [v["name"] for v in data.get("variables", [])]
        assert "Health" in var_names
        assert "UbergraphPages" in var_names

    def test_standard_filters_empty_execution_chains(self):
        ir = _make_ir()
        ir.execution_chains = [
            ExecutionChainIR(event="A", chain=["A", "B"]),
            ExecutionChainIR(event="Empty", chain=[]),
        ]
        renderer = get_renderer("json")
        result = renderer.render(ir, RenderOptions(output_level="standard"))
        data = json.loads(result)
        chains = data.get("execution_chains", [])
        assert len(chains) == 1
        assert chains[0]["event"] == "A"

    def test_standard_filters_empty_properties(self):
        export = _make_export(properties=[])
        ir = _make_ir(exports=[export])
        renderer = get_renderer("json")
        result = renderer.render(ir, RenderOptions(output_level="standard"))
        data = json.loads(result)
        assert "properties" not in data["exports"][0]


class TestJSONRendererBlueprint:
    def test_blueprint_to_dict_basic(self):
        blueprint = BlueprintIR(
            parent_class="/Engine/Actor",
            description="Test description",
            interfaces=[{"name": "IInterface"}],
            functions=[BlueprintFunctionIR(name="TestFunc", return_type="void", parameters=[{"name": "Val", "param_type": "float"}], is_pure=False, is_blueprint_callable=True)],
            events=[BlueprintEventIR(name="OnHit", event_type="Event", parameters=[], is_override=True, override_parent_class="AActor")],
            components=[{"name": "Root", "class": "USceneComponent"}],
        )
        ir = _make_ir()
        ir.blueprint = blueprint
        renderer = get_renderer("json")
        result = renderer.render(ir, RenderOptions())
        data = json.loads(result)
        bp = data["blueprint"]
        assert bp["parent_class"] == "/Engine/Actor"
        assert bp["description"] == "Test description"
        assert len(bp["functions"]) == 1
        assert len(bp["events"]) == 1
        assert len(bp["components"]) == 1

    def test_variable_to_dict_all_flags(self):
        ir = _make_ir()
        ir.variables = [VariableIR(name="Health", type="float", default_value="100.0", kind="user", guid="aabb", is_edit_anywhere=True, is_replicated=True)]
        renderer = get_renderer("json")
        result = renderer.render(ir, RenderOptions(output_level="debug"))
        data = json.loads(result)
        var = data["variables"][0]
        assert var["is_edit_anywhere"] is True
        assert var["is_replicated"] is True
        assert "is_transient" not in var

    def test_function_to_dict_implementation_status(self):
        ir = _make_ir()
        ir.blueprint = BlueprintIR(
            parent_class="/Engine/Actor",
            functions=[
                BlueprintFunctionIR(name="Func1", return_type="void", parameters=[], implementation_status="decompiled"),
                BlueprintFunctionIR(name="Func2", return_type="void", parameters=[], implementation_status="missing"),
            ],
        )
        renderer = get_renderer("json")
        result = renderer.render(ir, RenderOptions())
        data = json.loads(result)
        funcs = data["blueprint"]["functions"]
        func_map = {f["name"]: f for f in funcs}
        assert func_map["Func1"]["implementation_status"] == "decompiled"
        assert func_map["Func2"]["implementation_status"] == "missing"

    def test_export_status_partial(self):
        export = _make_export(parse_status="partial", fallback_reason="reason")
        ir = _make_ir(exports=[export])
        renderer = get_renderer("json")
        result = renderer.render(ir, RenderOptions())
        data = json.loads(result)
        assert data["exports"][0]["parse_status"] == "partial"
        assert data["exports"][0]["fallback_reason"] == "reason"

    def test_diagnostics_dedup_standard_mode(self):
        class MockDiag:
            def __init__(self, field, error):
                self._d = {"field": field, "error": error}
            def to_dict(self):
                return self._d
        ir = _make_ir()
        ir.diagnostics = [MockDiag("SerialOffset", "out of range"), MockDiag("SerialOffset", "out of range"), MockDiag("SerialSize", "negative")]
        renderer = get_renderer("json")
        result = renderer.render(ir, RenderOptions(output_level="standard"))
        data = json.loads(result)
        assert len(data["diagnostics"]) == 2

    def test_diagnostics_no_dedup_debug_mode(self):
        class MockDiag:
            def __init__(self, field, error):
                self._d = {"field": field, "error": error}
            def to_dict(self):
                return self._d
        ir = _make_ir()
        ir.diagnostics = [MockDiag("SerialOffset", "out of range"), MockDiag("SerialOffset", "out of range")]
        renderer = get_renderer("json")
        result = renderer.render(ir, RenderOptions(output_level="debug"))
        data = json.loads(result)
        assert len(data["diagnostics"]) == 2


class TestJSONRendererNodes:
    def test_node_with_macro_expansion(self):
        node = NodeIR(node_guid="aabbccdd11223344aabbccdd11223344", node_class="K2Node_MacroInstance", node_comment=None, pins=[], execution_flow=[], macro_expansion={"macro_name": "TestMacro"})
        graph = GraphIR(graph_guid="1122334455667788aabbccdd11223344", graph_name="EventGraph", graph_class="EdGraph", nodes=[node], execution_chains=[])
        export = _make_export(graphs=[graph])
        ir = _make_ir(exports=[export])
        renderer = get_renderer("json")
        result = renderer.render(ir, RenderOptions())
        data = json.loads(result)
        node_data = data["exports"][0]["graphs"][0]["nodes"][0]
        assert "macro_expansion" in node_data
        assert node_data["macro_expansion"]["macro_name"] == "TestMacro"

    def test_node_without_macro_expansion(self):
        node = NodeIR(node_guid="aabbccdd11223344aabbccdd11223344", node_class="K2Node_CallFunction", node_comment=None, pins=[], execution_flow=[], macro_expansion=None)
        graph = GraphIR(graph_guid="1122334455667788aabbccdd11223344", graph_name="EventGraph", graph_class="EdGraph", nodes=[node], execution_chains=[])
        export = _make_export(graphs=[graph])
        ir = _make_ir(exports=[export])
        renderer = get_renderer("json")
        result = renderer.render(ir, RenderOptions())
        data = json.loads(result)
        node_data = data["exports"][0]["graphs"][0]["nodes"][0]
        assert "macro_expansion" not in node_data

    def test_pin_to_dict_complete(self):
        pin = PinIR(pin_name="ReturnValue", pin_type="float", linked_to=["aabbccdd11223344aabbccdd11223344"], direction="output", default_value="0.0", pin_category="float")
        node = NodeIR(node_guid="aabbccdd11223344aabbccdd11223344", node_class="K2Node_CallFunction", node_comment=None, pins=[pin], execution_flow=[])
        graph = GraphIR(graph_guid="1122334455667788aabbccdd11223344", graph_name="EventGraph", graph_class="EdGraph", nodes=[node], execution_chains=[])
        export = _make_export(graphs=[graph])
        ir = _make_ir(exports=[export])
        renderer = get_renderer("json")
        result = renderer.render(ir, RenderOptions())
        data = json.loads(result)
        pin_data = data["exports"][0]["graphs"][0]["nodes"][0]["pins"][0]
        assert pin_data["pin_name"] == "ReturnValue"
        assert pin_data["pin_type"] == "float"
        assert pin_data["direction"] == "output"
        assert pin_data["linked_to"] == ["aabbccdd11223344aabbccdd11223344"]


class TestJSONRendererAnimations:
    def test_anim_blueprint_full(self):
        ir = _make_ir()
        ir.anim_blueprint = AnimBlueprintIR(
            target_skeleton="/Game/Skeleton",
            baked_state_machines=[BakedStateMachineIR(machine_name="WalkRun", initial_state=0, states=[BakedStateIR(state_name="Idle", state_root_node_index=0), BakedStateIR(state_name="Run", state_root_node_index=1, b_is_a_conduit=True)], transitions=[BakedTransitionIR(previous_state=0, next_state=1, crossfade_duration=0.2, blend_mode="Linear")])],
            anim_notifies=[AnimNotifyIR(notify_name="Footstep", trigger_time_offset=0.5, duration=0.0, notify_class="AN_Footstep")],
            sync_group_names=["Locomotion"],
        )
        renderer = get_renderer("json")
        result = renderer.render(ir, RenderOptions())
        data = json.loads(result)
        ab = data["anim_blueprint"]
        assert ab["target_skeleton"] == "/Game/Skeleton"
        assert len(ab["baked_state_machines"]) == 1
        assert ab["baked_state_machines"][0]["machine_name"] == "WalkRun"
        assert len(ab["baked_state_machines"][0]["states"]) == 2

    def test_anim_sequence_full(self):
        ir = _make_ir()
        ir.anim_sequence = AnimSequenceIR(target_skeleton="/Game/Skeleton", additive_anim_type="AAT_None", sequence_length=2.5, rate_scale=1.0, notifies=[AnimNotifyIR(notify_name="Notify1", trigger_time_offset=1.0, duration=0.5, notify_class="AN_Test")], float_curve_names=["Curve1", "Curve2"], has_compressed_data=True)
        renderer = get_renderer("json")
        result = renderer.render(ir, RenderOptions())
        data = json.loads(result)
        as_data = data["anim_sequence"]
        assert as_data["target_skeleton"] == "/Game/Skeleton"
        assert as_data["sequence_length"] == 2.5

    def test_anim_montage_full(self):
        ir = _make_ir()
        ir.anim_montage = AnimMontageIR(blend_mode_in="Linear", blend_mode_out="Linear", blend_in_option="BlendIn", blend_out_option="BlendOut", sync_group="DefaultGroup", rate_scale=1.5, composite_sections=["Section1"], slot_anim_tracks=[{"SlotName": "DefaultSlot"}], branching_point_markers=[{"MarkerName": "BP1"}], notifies=[AnimNotifyIR(notify_name="MontageNotify", trigger_time_offset=0.3, duration=0.0)], float_curve_names=["MontageCurve1"])
        renderer = get_renderer("json")
        result = renderer.render(ir, RenderOptions())
        data = json.loads(result)
        am = data["anim_montage"]
        assert am["blend_mode_in"] == "Linear"
        assert am["rate_scale"] == 1.5


class TestMarkdownRendererBasicQuality:
    def test_render_produces_string(self):
        ir = _make_ir()
        renderer = get_renderer("markdown")
        result = renderer.render(ir, RenderOptions())
        assert isinstance(result, str)
        assert len(result) > 0

    def test_render_contains_asset_overview(self):
        ir = _make_ir()
        renderer = get_renderer("markdown")
        result = renderer.render(ir, RenderOptions())
        assert "## Asset Overview" in result
        assert "| Field | Value |" in result
        assert "| Package |" in result

    def test_render_with_package_name_slash(self):
        ir = _make_ir(header=_make_header(package_name="/Game/Blueprints/BP_MyAsset"))
        renderer = get_renderer("markdown")
        result = renderer.render(ir, RenderOptions())
        assert "# BP_MyAsset" in result

    def test_render_with_simple_name(self):
        ir = _make_ir(header=_make_header(package_name="BP_Simple"))
        renderer = get_renderer("markdown")
        result = renderer.render(ir, RenderOptions())
        assert "# BP_Simple" in result


class TestMarkdownRendererBlueprintQuality:
    def test_blueprint_details_section(self):
        blueprint = BlueprintIR(parent_class="/Engine/Actor", description="Test description")
        ir = _make_ir()
        ir.blueprint = blueprint
        renderer = get_renderer("markdown")
        result = renderer.render(ir, RenderOptions())
        assert "## Blueprint Details" in result
        assert "| Parent Class | /Engine/Actor |" in result

    def test_component_hierarchy_mermaid(self):
        blueprint = BlueprintIR(parent_class="/Engine/Actor", components=[{"name": "Root", "class": "USceneComponent"}, {"name": "Mesh", "class": "UStaticMeshComponent"}])
        ir = _make_ir()
        ir.blueprint = blueprint
        renderer = get_renderer("markdown")
        result = renderer.render(ir, RenderOptions())
        assert "### Component Hierarchy" in result
        assert "```mermaid" in result
        assert "graph TD" in result

    def test_interfaces_rendering(self):
        blueprint = BlueprintIR(parent_class="/Engine/Actor", interfaces=[{"name": "IInterfaceA"}, {"name": "IInterfaceB"}])
        ir = _make_ir()
        ir.blueprint = blueprint
        renderer = get_renderer("markdown")
        result = renderer.render(ir, RenderOptions())
        assert "IInterfaceA" in result
        assert "IInterfaceB" in result


class TestMarkdownRendererEventGraphQuality:
    def test_event_with_decompiled_function(self):
        ir = _make_ir()
        ir.blueprint = BlueprintIR(parent_class="/Engine/Actor", events=[BlueprintEventIR(name="ReceiveBeginPlay", event_type="Event", parameters=[])])
        ir.decompiled_functions = [DecompiledFunctionIR(name="ReceiveBeginPlay", signature="void AActor::ReceiveBeginPlay()", cpp_code="Super::ReceiveBeginPlay();", parameters=[], return_type="void")]
        renderer = get_renderer("markdown")
        result = renderer.render(ir, RenderOptions())
        assert "## Event Graph" in result
        assert "### ReceiveBeginPlay" in result
        assert "void AActor::ReceiveBeginPlay()" in result

    def test_event_without_decompiled_function(self):
        ir = _make_ir()
        ir.blueprint = BlueprintIR(parent_class="/Engine/Actor", events=[BlueprintEventIR(name="ReceiveBeginPlay", event_type="Event", parameters=[{"name": "OtherActor", "param_type": "AActor*", "is_input": True}])])
        ir.decompiled_functions = []
        renderer = get_renderer("markdown")
        result = renderer.render(ir, RenderOptions())
        assert "void ReceiveBeginPlay(AActor* OtherActor) override" in result

    def test_event_with_execution_chain(self):
        ir = _make_ir()
        ir.blueprint = BlueprintIR(parent_class="/Engine/Actor", events=[BlueprintEventIR(name="ReceiveBeginPlay", event_type="Event", parameters=[])])
        ir.execution_chains = [ExecutionChainIR(event="ReceiveBeginPlay", chain=["Begin", "Step1", "Step2"])]
        renderer = get_renderer("markdown")
        result = renderer.render(ir, RenderOptions())
        assert "Begin -> Step1 -> Step2" in result


class TestMarkdownRendererFunctionsQuality:
    def test_decompiled_function_section(self):
        ir = _make_ir()
        ir.decompiled_functions = [DecompiledFunctionIR(name="TestFunc", signature="void TestFunc(float Val)", cpp_code="return Val > 0;", parameters=[{"name": "Val", "param_type": "float"}], return_type="bool")]
        renderer = get_renderer("markdown")
        result = renderer.render(ir, RenderOptions())
        assert "## Functions" in result
        assert "### TestFunc" in result
        assert "`void TestFunc(float Val)`" in result

    def test_function_dedup_decompiled_priority(self):
        ir = _make_ir()
        ir.blueprint = BlueprintIR(parent_class="/Engine/Actor", functions=[BlueprintFunctionIR(name="TestFunc", return_type="void", parameters=[{"name": "Val", "param_type": "float"}])])
        ir.decompiled_functions = [DecompiledFunctionIR(name="TestFunc", signature="void TestFunc(float Val)", cpp_code="return Val > 0;", parameters=[{"name": "Val", "param_type": "float"}], return_type="bool")]
        renderer = get_renderer("markdown")
        result = renderer.render(ir, RenderOptions())
        assert result.count("### TestFunc") == 1

    def test_function_parameter_table(self):
        ir = _make_ir()
        ir.blueprint = BlueprintIR(parent_class="/Engine/Actor", functions=[BlueprintFunctionIR(name="Func", return_type="void", parameters=[{"name": "X", "param_type": "float", "default_value": 1.0}])])
        renderer = get_renderer("markdown")
        result = renderer.render(ir, RenderOptions())
        assert "| Parameter | Type | Default |" in result
        assert "| X | float | 1.0 |" in result


class TestMarkdownRendererVariablesQuality:
    def test_variables_table(self):
        ir = _make_ir()
        ir.variables = [VariableIR(name="Health", type="float", default_value="100.0", kind="user"), VariableIR(name="MaxSpeed", type="float", default_value=None, kind="user")]
        renderer = get_renderer("markdown")
        result = renderer.render(ir, RenderOptions())
        assert "## Variables" in result
        assert "| Health | float | 100.0 |" in result
        assert "| MaxSpeed | float | - |" in result

    def test_no_variables_section_when_empty(self):
        ir = _make_ir()
        ir.variables = []
        renderer = get_renderer("markdown")
        result = renderer.render(ir, RenderOptions())
        assert "## Variables" not in result


class TestMarkdownRendererAnimationsQuality:
    def test_anim_blueprint_state_machine(self):
        ir = _make_ir()
        ir.anim_blueprint = AnimBlueprintIR(target_skeleton="/Game/Skeleton", baked_state_machines=[BakedStateMachineIR(machine_name="WalkRun", initial_state=0, states=[BakedStateIR(state_name="Idle", state_root_node_index=0, b_is_a_conduit=False), BakedStateIR(state_name="Run", state_root_node_index=1, b_is_a_conduit=True)], transitions=[])])
        renderer = get_renderer("markdown")
        result = renderer.render(ir, RenderOptions())
        assert "### State Machine: WalkRun" in result
        assert "| Idle | #0 | No |" in result
        assert "| Run | #1 | Yes |" in result

    def test_anim_sequence_basic(self):
        ir = _make_ir()
        ir.anim_sequence = AnimSequenceIR(target_skeleton="/Game/Skeleton", sequence_length=2.5, rate_scale=1.0, has_compressed_data=True)
        renderer = get_renderer("markdown")
        result = renderer.render(ir, RenderOptions())
        assert "## Animation Sequence" in result
        assert "**Sequence Length**: 2.50s" in result

    def test_anim_montage_basic(self):
        ir = _make_ir()
        ir.anim_montage = AnimMontageIR(blend_mode_in="Linear", sync_group="Default", rate_scale=1.5)
        renderer = get_renderer("markdown")
        result = renderer.render(ir, RenderOptions())
        assert "## Animation Montage" in result
        assert "**Blend In Mode**: Linear" in result


class TestMarkdownRendererDiagnosticsQuality:
    def test_diagnostics_table(self):
        class MockDiag:
            def __init__(self, kind, module, object_name, field, error):
                self._d = {"kind": kind, "module": module, "object_name": object_name, "field": field, "error": error}
            def to_dict(self):
                return self._d
        ir = _make_ir()
        ir.diagnostics = [MockDiag("offset", "ExportMap", "Test", "SerialOffset", "out of range")]
        renderer = get_renderer("markdown")
        result = renderer.render(ir, RenderOptions())
        assert "## 诊断信息" in result
        assert "SerialOffset" in result

    def test_no_diagnostics_when_empty(self):
        ir = _make_ir()
        ir.diagnostics = []
        renderer = get_renderer("markdown")
        result = renderer.render(ir, RenderOptions())
        assert "## 诊断信息" not in result


class TestMarkdownRendererMermaid:
    def test_mermaid_with_edges(self):
        pin = PinIR(pin_name="Then", pin_type="exec", linked_to=["bbccdd1122334455bbccdd1122334455"], direction="output", default_value=None)
        node1 = NodeIR(node_guid="aabbccdd11223344aabbccdd11223344", node_class="K2Node_Event", node_comment="BeginPlay", pins=[pin], execution_flow=[])
        target_pin = PinIR(pin_name="exec", pin_type="exec", linked_to=[], direction="input", default_value=None, pin_guid="bbccdd1122334455bbccdd1122334455")
        node2 = NodeIR(node_guid="bbccdd1122334455bbccdd1122334455", node_class="K2Node_CallFunction", node_comment="DoStuff", pins=[target_pin], execution_flow=[])
        graph = GraphIR(graph_guid="1122334455667788aabbccdd11223344", graph_name="EventGraph", graph_class="EdGraph", nodes=[node1, node2], execution_chains=[])
        export = _make_export(graphs=[graph])
        ir = _make_ir(exports=[export])
        renderer = get_renderer("markdown")
        result = renderer.render(ir, RenderOptions())
        assert "aabbccdd --> bbccdd11" in result

    def test_mermaid_subgraph(self):
        node = NodeIR(node_guid="bbccdd1122334455bbccdd1122334455", node_class="K2Node_CallFunction", node_comment="Inner", pins=[], execution_flow=[])
        subgraph = GraphIR(graph_guid="sub111111111111111111111111111111", graph_name="SubGraph", graph_class="EdGraph", nodes=[node], execution_chains=[])
        graph = GraphIR(graph_guid="1122334455667788aabbccdd11223344", graph_name="EventGraph", graph_class="EdGraph", nodes=[], execution_chains=[], subgraphs=[subgraph])
        export = _make_export(graphs=[graph])
        ir = _make_ir(exports=[export])
        renderer = get_renderer("markdown")
        result = renderer.render(ir, RenderOptions())
        assert "subgraph SubGraph" in result


class TestMarkdownRendererHelpers:
    def test_escape_md_cell_pipe(self):
        from uasset_read.renderers.markdown_renderer import _escape_md_cell
        assert _escape_md_cell("a|b") == "a\\|b"

    def test_escape_md_cell_newline(self):
        from uasset_read.renderers.markdown_renderer import _escape_md_cell
        assert _escape_md_cell("a\nb") == "a b"

    def test_escape_md_cell_non_string(self):
        from uasset_read.renderers.markdown_renderer import _escape_md_cell
        assert _escape_md_cell(42) == "42"

    def test_format_transforms_none(self):
        from uasset_read.renderers.markdown_renderer import _format_transforms
        assert _format_transforms(None) == "Identity"

    def test_format_transforms_empty(self):
        from uasset_read.renderers.markdown_renderer import _format_transforms
        assert _format_transforms({}) == "Identity"

    def test_format_transforms_full(self):
        from uasset_read.renderers.markdown_renderer import _format_transforms
        transforms = {
            "relative_location": {"x": 100.0, "y": 200.0, "z": 300.0},
            "relative_rotation": {"pitch": 45.0, "yaw": 90.0, "roll": 0.0},
            "relative_scale": {"x": 1.0, "y": 1.0, "z": 1.0},
        }
        result = _format_transforms(transforms)
        assert "Loc(100.0,200.0,300.0)" in result


# ---------------------------------------------------------------------------
# 编辑器过滤一致性 (test_renderer_quality)
# ---------------------------------------------------------------------------


class TestEditorVariableFilterConsistency:
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
        ir = self._make_ir_with_variables([editor_var, "MyHealth"])
        renderer = get_renderer("json")
        result = renderer.render(ir, RenderOptions())
        data = json.loads(result)
        var_names = [v["name"] for v in data.get("variables", [])]
        assert editor_var not in var_names
        assert "MyHealth" in var_names

    @pytest.mark.parametrize("editor_var", sorted(EDITOR_VAR_NAMES))
    def test_markdown_filters_editor_variable(self, editor_var: str):
        ir = self._make_ir_with_variables([editor_var, "MyHealth"])
        renderer = get_renderer("markdown")
        result = renderer.render(ir, RenderOptions())
        assert editor_var not in result
        assert "MyHealth" in result


class TestEditorNodeClassFilterConsistency:
    def test_json_filters_editor_node_class_export(self):
        normal_export = _make_export(index=0, object_name="BP_Test_C", object_class="BlueprintGeneratedClass")
        knot_export = _make_export(index=1, object_name="Knot_0", object_class="K2Node_Knot")
        ir = _make_ir(exports=[normal_export, knot_export])
        renderer = get_renderer("json")
        result = renderer.render(ir, RenderOptions())
        data = json.loads(result)
        export_classes = [e["object_class"] for e in data["exports"]]
        assert "K2Node_Knot" not in export_classes
        assert "BlueprintGeneratedClass" in export_classes

    def test_markdown_filters_editor_node_class_export(self):
        normal_export = _make_export(index=0, object_name="BP_Test_C", object_class="BlueprintGeneratedClass")
        knot_export = _make_export(index=1, object_name="Knot_0", object_class="K2Node_Knot")
        ir = _make_ir(exports=[normal_export, knot_export])
        renderer = get_renderer("markdown")
        result = renderer.render(ir, RenderOptions())
        assert "K2Node_Knot" not in result


class TestEditorPropertyFilterConsistency:
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
        props = [_make_property(editor_prop), _make_property("Health")]
        export = _make_export(properties=props)
        ir = _make_ir(exports=[export])
        renderer = get_renderer("json")
        result = renderer.render(ir, RenderOptions())
        data = json.loads(result)
        prop_names = [p["name"] for p in data["exports"][0].get("properties", [])]
        assert editor_prop not in prop_names
        assert "Health" in prop_names


class TestIRBuilderParentClass:
    def test_blueprint_export_gets_parent_class(self):
        from uasset_read.ir_builder import _build_export_ir
        bp = BlueprintIR(parent_class="/Engine/Actor", functions=[], events=[], components=[])
        export = _make_export(object_name="BP_Test_C", object_class="BlueprintGeneratedClass")

        class MockResult:
            blueprint = bp
            import_map = []
            export_map = []
            linker = None
        result = MockResult()
        export_ir = _build_export_ir(0, export, result)
        assert export_ir.parent_class == "/Engine/Actor"

    def test_non_blueprint_export_no_parent_class(self):
        from uasset_read.ir_builder import _build_export_ir
        bp = BlueprintIR(parent_class="/Engine/Actor", functions=[], events=[], components=[])
        export = _make_export(object_name="SM_Chair", object_class="StaticMesh")

        class MockResult:
            blueprint = bp
            import_map = []
            export_map = []
            linker = None
        result = MockResult()
        export_ir = _build_export_ir(0, export, result)
        assert export_ir.parent_class is None

    def test_no_blueprint_no_parent_class(self):
        from uasset_read.ir_builder import _build_export_ir
        export = _make_export(object_name="BP_Test_C", object_class="BlueprintGeneratedClass")

        class MockResult:
            blueprint = None
            import_map = []
            export_map = []
            linker = None
        result = MockResult()
        export_ir = _build_export_ir(0, export, result)
        assert export_ir.parent_class is None


# ---------------------------------------------------------------------------
# 兼容性测试 (test_renderer_compat)
# ---------------------------------------------------------------------------


class TestRenderOptionsCompat:
    def test_defaults(self):
        opts = RenderOptions()
        assert opts.verbose is False
        assert opts.indent == 2
        assert opts.include_schema is False

    def test_custom(self):
        opts = RenderOptions(verbose=True, indent=4, include_function_graphs=True)
        assert opts.verbose is True
        assert opts.indent == 4


class TestRendererRegistryCompat:
    def test_get_renderer_json(self):
        from uasset_read.renderers.json_renderer import JSONRenderer  # noqa: F401
        r = get_renderer("json")
        assert r.format_name == "json"

    def test_get_renderer_unknown(self):
        with pytest.raises(ValueError, match="Unknown render format"):
            get_renderer("nonexistent")

    def test_list_formats(self):
        from uasset_read.renderers.json_renderer import JSONRenderer  # noqa: F401
        fmts = list_formats()
        assert "json" in fmts

    def test_duplicate_registration_raises(self):
        class _TestRenderer(IRenderer):
            def render(self, ir, options): return ""
            @property
            def format_name(self): return "_test_dup"
        register_renderer("_test_dup", _TestRenderer)
        with pytest.raises(ValueError, match="already registered"):
            register_renderer("_test_dup", _TestRenderer)
        RENDERER_REGISTRY.pop("_test_dup", None)


class TestJSONRendererCompat:
    def test_encoder_rejects_dynamically_generated_to_dict(self):
        from uasset_read.renderers.json_renderer import _JSONEncoder
        mock = MagicMock()
        with pytest.raises(TypeError):
            _JSONEncoder().default(mock)
        mock.to_dict.assert_not_called()

    def test_json_excludes_redundant_fields(self):
        ir = PackageIR(
            header=PackageHeaderIR(package_name="/Game/Test", package_class="", package_flags=0, total_export_count=0, total_import_count=0, ue_version="5.x"),
            name_map=["test"], imports=[], exports=[], linker=None,
        )
        ir.status = "success"
        renderer = JSONRenderer()
        result = renderer.render(ir, RenderOptions())
        data = json.loads(result)
        assert "name_map" not in data
        assert "imports" not in data
        assert "linker" not in data

    def test_render_minimal_ir(self):
        header = PackageHeaderIR(package_name="/Game/Test", package_class="Test_C", package_flags=0, total_export_count=0, total_import_count=0, ue_version="5.x")
        ir = PackageIR(header=header, name_map=["Test"], imports=[], exports=[], linker=None)
        renderer = get_renderer("json")
        output = renderer.render(ir, RenderOptions())
        data = json.loads(output)
        assert data["status"]["status"] == "success"
        assert data["summary"]["package_name"] == "/Game/Test"
        assert "blueprint" not in data


class TestMarkdownRendererCompat:
    def test_render_minimal_ir(self):
        header = PackageHeaderIR(package_name="/Game/Test", package_class="Test_C", package_flags=0, total_export_count=0, total_import_count=0, ue_version="5.x")
        ir = PackageIR(header=header, name_map=["Test"], imports=[], exports=[], linker=None)
        renderer = get_renderer("markdown")
        output = renderer.render(ir, RenderOptions())
        assert "# Test" in output
        assert "| Class |" in output

    def test_render_with_mermaid(self):
        pin = PinIR(pin_name="Exec", pin_type="exec", linked_to=["target1234"], direction=1, default_value=None)
        node = NodeIR(node_guid="abcd1234567890abcdef1234567890ab", node_class="K2Node_Event", node_comment="BeginPlay", pins=[pin], execution_flow=[])
        graph = GraphIR(graph_guid="guid0001", graph_name="EventGraph", graph_class="EdGraph", nodes=[node], execution_chains=[])
        export = ExportIR(index=0, object_name="Default__TestBP_C", object_class="BlueprintGeneratedClass", serial_size=1024, outer_index_resolved=None, super_index_resolved=None, parent_class=None, properties=[], graphs=[graph], bulk_data=None)
        header = PackageHeaderIR(package_name="/Game/TestBP", package_class="TestBP_C", package_flags=0, total_export_count=1, total_import_count=0, ue_version="5.3")
        ir = PackageIR(header=header, name_map=["TestBP"], imports=[], exports=[export], linker=None)
        renderer = get_renderer("markdown")
        output = renderer.render(ir, RenderOptions())
        assert "EventGraph" in output
        assert "```mermaid" in output


class TestRendererListFormatsCompat:
    def test_all_formats_registered(self):
        fmts = list_formats()
        assert "json" in fmts
        assert "markdown" in fmts
        assert "text" in fmts
        assert len(fmts) == 3


class TestJSONOnlyBlueprintExportsCompat:
    def test_json_only_blueprint_exports(self):
        bp_export = ExportIR(index=0, object_name="BP_Test_C", object_class="", serial_size=100, outer_index_resolved=None, super_index_resolved=None, parent_class="/Script/Engine.Actor", properties=[], graphs=[GraphIR(graph_guid="abc", graph_name="EventGraph", graph_class="EdGraph", nodes=[], execution_chains=[])], bulk_data=None)
        non_bp_export = ExportIR(index=1, object_name="BodySetup", object_class="", serial_size=200, outer_index_resolved=None, super_index_resolved=None, parent_class=None, properties=[], graphs=[], bulk_data=None)
        ir = PackageIR(header=PackageHeaderIR(package_name="/Game/Test", package_class="", package_flags=0, total_export_count=2, total_import_count=0, ue_version="5.x"), name_map=[], imports=[], exports=[bp_export, non_bp_export], linker=None)
        ir.status = "success"
        renderer = JSONRenderer()
        result = renderer.render(ir, RenderOptions())
        data = json.loads(result)
        assert len(data["exports"]) == 2


class TestMarkdownOnlyBlueprintExportsCompat:
    def test_markdown_only_blueprint_exports(self):
        bp_export = ExportIR(index=0, object_name="BP_Test_C", object_class="", serial_size=100, outer_index_resolved=None, super_index_resolved=None, parent_class="/Script/Engine.Actor", properties=[], graphs=[GraphIR(graph_guid="abc", graph_name="EventGraph", graph_class="EdGraph", nodes=[], execution_chains=[])], bulk_data=None)
        non_bp_export = ExportIR(index=1, object_name="BodySetup", object_class="", serial_size=200, outer_index_resolved=None, super_index_resolved=None, parent_class=None, properties=[], graphs=[], bulk_data=None)
        ir = PackageIR(header=PackageHeaderIR(package_name="/Game/Test", package_class="", package_flags=0, total_export_count=2, total_import_count=0, ue_version="5.x"), name_map=[], imports=[], exports=[bp_export, non_bp_export], linker=None)
        ir.status = "success"
        renderer = MarkdownRenderer()
        result = renderer.render(ir, RenderOptions())
        assert "BP_Test_C" in result
        assert "BodySetup" not in result


class TestJSONExportExcludesRawFieldsCompat:
    def test_json_export_excludes_raw_fields(self):
        export = ExportIR(index=0, object_name="TestExport_C", object_class="", serial_size=100, outer_index_resolved="/Game/Test", super_index_resolved="/Script/Engine.Actor", parent_class="/Script/Engine.Actor", properties=[], graphs=[], bulk_data=None, ue_export_raw=ExportRawIR(), diagnostics={"test": "data"})
        ir = PackageIR(header=PackageHeaderIR(package_name="/Game/Test", package_class="", package_flags=0, total_export_count=1, total_import_count=0, ue_version="5.x"), name_map=[], imports=[], exports=[export], linker=None)
        ir.status = "success"
        renderer = JSONRenderer()
        result = renderer.render(ir, RenderOptions(output_level="debug"))
        data = json.loads(result)
        export_data = data["exports"][0]
        assert "ue_export_raw" not in export_data
        assert "diagnostics" not in export_data
        assert "outer_index_resolved" not in export_data


class TestMarkdownExcludesLinkerSectionCompat:
    def test_markdown_excludes_linker_section(self):
        ir = PackageIR(header=PackageHeaderIR(package_name="/Game/Test", package_class="", package_flags=0, total_export_count=0, total_import_count=0, ue_version="5.x"), name_map=[], imports=[], exports=[], linker=LinkerSummaryIR(has_linker=True, import_paths=["/Script/Engine"], export_paths=["/Game/Test"]))
        ir.status = "success"
        renderer = MarkdownRenderer()
        result = renderer.render(ir, RenderOptions())
        assert "## Linker" not in result


class TestOnlyJsonAndMarkdownFormatsCompat:
    def test_only_json_and_markdown_formats(self):
        formats = list_formats()
        assert "json" in formats
        assert "markdown" in formats
        assert "text" in formats
        assert "text_summary" not in formats
        assert "blueprint_text" not in formats


# ---------------------------------------------------------------------------
# JSON 渲染器输出测试 (test_json_renderer)
# ---------------------------------------------------------------------------


from uasset_read.core import parse_single
from tests.conftest import asset_path, ASSET_TEXTURE_BRICK, ASSET_MATERIAL_ROCK, ASSET_MESH_CHAIR


class TestJSONRendererExportsFromJsonRenderer:
    def test_json_renderer_includes_non_blueprint_exports(self, sample_root: Path):
        texture_path = asset_path(sample_root, ASSET_TEXTURE_BRICK)
        output = json.loads(parse_single(str(texture_path)))
        assert len(output.get("exports", [])) > 0

    def test_json_renderer_object_class_populated(self, sample_root: Path):
        texture_path = asset_path(sample_root, ASSET_TEXTURE_BRICK)
        output = json.loads(parse_single(str(texture_path)))
        for exp in output["exports"]:
            assert "object_class" in exp
            assert isinstance(exp["object_class"], str)

    def test_json_renderer_package_name_correct(self, sample_root: Path):
        texture_path = asset_path(sample_root, ASSET_TEXTURE_BRICK)
        output = json.loads(parse_single(str(texture_path)))
        pkg = output["summary"]["package_name"]
        assert pkg is not None
        assert pkg != "None"

    def test_json_renderer_material_exports(self, sample_root: Path):
        material_path = asset_path(sample_root, ASSET_MATERIAL_ROCK)
        output = json.loads(parse_single(str(material_path)))
        exports = output["exports"]
        assert len(exports) > 0
        has_material = any(e.get("object_class") == "Material" for e in exports)
        assert has_material

    def test_json_renderer_staticmesh_exports(self, sample_root: Path):
        mesh_path = asset_path(sample_root, ASSET_MESH_CHAIR)
        output = json.loads(parse_single(str(mesh_path)))
        for exp in output["exports"]:
            assert "object_class" in exp

    def test_json_renderer_opaque_export_has_partial_status(self, sample_root: Path):
        texture_path = asset_path(sample_root, ASSET_TEXTURE_BRICK)
        output = json.loads(parse_single(str(texture_path)))
        exports_with_status = [e for e in output["exports"] if e.get("parse_status")]
        if exports_with_status:
            main_export = exports_with_status[-1]
            assert main_export.get("parse_status") in ("partial_metadata", "success", "partial")


class TestJsonMacroExpansionOutput:
    def _make_minimal_ir(self, nodes):
        graph = GraphIR(graph_guid="guid0001", graph_name="EventGraph", graph_class="EdGraph", nodes=nodes, execution_chains=[])
        export = ExportIR(index=0, object_name="Default__TestBP_C", object_class="BlueprintGeneratedClass", serial_size=256, outer_index_resolved=None, super_index_resolved=None, parent_class="Actor", properties=[], graphs=[graph], bulk_data=None)
        header = PackageHeaderIR(package_name="/Game/TestBP", package_class="TestBP_C", package_flags=0, total_export_count=1, total_import_count=0, ue_version="5.3")
        return PackageIR(header=header, name_map=["TestBP"], imports=[], exports=[export], linker=None)

    def test_node_to_dict_includes_macro_expansion(self):
        macro_data = {"macro_name": "ForLoop", "macro_guid": "", "is_standard": True, "pin_mapping": {"Entry": {"instance_direction": "EGPD_Input"}}}
        node = NodeIR(node_guid="abcd1234567890abcdef1234567890ab", node_class="K2Node_MacroInstance", node_comment=None, pins=[], execution_flow=[], macro_expansion=macro_data)
        renderer = JSONRenderer()
        result = renderer._node_to_dict(node)
        assert "macro_expansion" in result
        assert result["macro_expansion"]["macro_name"] == "ForLoop"

    def test_node_to_dict_excludes_empty_macro_expansion(self):
        node = NodeIR(node_guid="abcd1234567890abcdef1234567890ab", node_class="K2Node_CallFunction", node_comment=None, pins=[], execution_flow=[], macro_expansion=None)
        renderer = JSONRenderer()
        result = renderer._node_to_dict(node)
        assert "macro_expansion" not in result

    def test_full_json_output_includes_macro_expansion(self):
        macro_data = {"macro_name": "ForLoop", "macro_guid": "", "is_standard": True, "pin_mapping": {"Entry": {"instance_direction": "EGPD_Input"}, "LastIndex": {"instance_direction": "EGPD_Input"}, "Completed": {"instance_direction": "EGPD_Output"}}}
        event_node = NodeIR(node_guid="event_guid_1234567890abcdef12345678", node_class="K2Node_Event", node_comment="BeginPlay", pins=[], execution_flow=[], macro_expansion=None)
        macro_node = NodeIR(node_guid="macro_guid_1234567890abcdef12345678", node_class="K2Node_MacroInstance", node_comment=None, pins=[], execution_flow=[], macro_expansion=macro_data)
        call_node = NodeIR(node_guid="call_guid_1234567890abcdef12345678", node_class="K2Node_CallFunction", node_comment=None, pins=[], execution_flow=[], macro_expansion=None)
        ir = self._make_minimal_ir([event_node, macro_node, call_node])
        renderer = JSONRenderer()
        output = renderer.render(ir, RenderOptions())
        data = json.loads(output)
        graph_nodes = data["exports"][0]["graphs"][0]["nodes"]
        macro_result = next(n for n in graph_nodes if n["node_class"] == "K2Node_MacroInstance")
        assert "macro_expansion" in macro_result
        assert macro_result["macro_expansion"]["macro_name"] == "ForLoop"
        event_result = next(n for n in graph_nodes if n["node_class"] == "K2Node_Event")
        assert "macro_expansion" not in event_result


from unittest.mock import MagicMock
