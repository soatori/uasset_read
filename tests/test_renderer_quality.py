"""renderer 模块缺陷测试。"""
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
    AnimBlueprintIR,
    AnimSequenceIR,
    AnimMontageIR,
    BakedStateMachineIR,
    BakedStateIR,
    BakedTransitionIR,
    AnimNotifyIR,
)
from uasset_read.renderers import RENDERER_REGISTRY, get_renderer, list_formats
from uasset_read.renderers.base import IRenderer, RenderOptions, is_blueprint_export


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


# ---------------------------------------------------------------------------
# 基础导入和注册
# ---------------------------------------------------------------------------

class TestRendererQuality:
    """renderer 模块质量验证。"""

    def test_renderer_imports(self):
        """renderer 模块可正常导入。"""
        from uasset_read.renderers import json_renderer
        assert json_renderer is not None

    def test_renderer_registry(self):
        """渲染器注册表应包含所有内置渲染器。"""
        from uasset_read.renderers import RENDERER_REGISTRY
        assert len(RENDERER_REGISTRY) > 0

    def test_registry_contains_json_and_markdown(self):
        """注册表应包含 json 和 markdown 格式。"""
        formats = list_formats()
        assert "json" in formats
        assert "markdown" in formats

    def test_get_renderer_returns_instance(self):
        """get_renderer 应返回 IRenderer 实例。"""
        for name in list_formats():
            renderer = get_renderer(name)
            assert isinstance(renderer, IRenderer)
            assert renderer.format_name == name

    def test_get_renderer_unknown_format_raises(self):
        """未知格式应抛出 ValueError。"""
        with pytest.raises(ValueError, match="Unknown render format"):
            get_renderer("nonexistent_format")


# ---------------------------------------------------------------------------
# is_blueprint_export 测试
# ---------------------------------------------------------------------------

class TestIsBlueprintExport:
    """is_blueprint_export 函数测试。"""

    def test_name_ends_with_c(self):
        """类名以 _C 结尾应识别为蓝图 export。"""
        e = _make_export(object_name="BP_Test_C")
        assert is_blueprint_export(e) is True

    def test_has_graphs(self):
        """有 graphs 数据应识别为蓝图 export。"""
        graph = GraphIR(
            graph_guid="aaa", graph_name="G", graph_class="EdGraph",
            nodes=[], execution_chains=[],
        )
        e = _make_export(object_name="Texture2D", graphs=[graph])
        assert is_blueprint_export(e) is True

    def test_not_blueprint(self):
        """非蓝图 export 应返回 False。"""
        e = _make_export(object_name="Texture2D", graphs=[])
        assert is_blueprint_export(e) is False


# ---------------------------------------------------------------------------
# JSON 渲染器基础测试
# ---------------------------------------------------------------------------

class TestJSONRendererBasic:
    """JSON 渲染器基础功能测试。"""

    def test_render_produces_valid_json(self):
        """渲染应产生有效的 JSON 字符串。"""
        ir = _make_ir()
        renderer = get_renderer("json")
        result = renderer.render(ir, RenderOptions())
        data = json.loads(result)
        assert isinstance(data, dict)

    def test_render_contains_required_keys(self):
        """输出应包含 status、summary、exports 键，不包含 output_version。"""
        ir = _make_ir()
        renderer = get_renderer("json")
        result = renderer.render(ir, RenderOptions())
        data = json.loads(result)
        assert "status" in data
        assert "output_version" not in data
        assert "summary" in data
        assert "exports" in data

    def test_render_export_basic_fields(self):
        """导出应包含 object_name、object_class、serial_size、parent_class。"""
        ir = _make_ir()
        renderer = get_renderer("json")
        result = renderer.render(ir, RenderOptions())
        data = json.loads(result)
        export = data["exports"][0]
        assert export["object_name"] == "BP_Test_C"
        assert export["object_class"] == "BlueprintGeneratedClass"
        assert export["serial_size"] == 1024
        assert export["parent_class"] == "/Engine/Actor"


# ---------------------------------------------------------------------------
# JSON 渲染器 output_level 测试
# ---------------------------------------------------------------------------

class TestJSONRendererOutputLevel:
    """JSON 渲染器 output_level 行为测试。"""

    def test_standard_filters_editor_properties(self):
        """standard 模式应过滤编辑器布局属性。"""
        prop = PropertyIR(
            name="NodePosX", type="IntProperty", value=100,
            array_index=0, guid=None,
        )
        export = _make_export(properties=[prop])
        ir = _make_ir(exports=[export])
        renderer = get_renderer("json")
        result = renderer.render(ir, RenderOptions(output_level="standard"))
        data = json.loads(result)
        props = data["exports"][0].get("properties", [])
        assert not any(p["name"] == "NodePosX" for p in props)

    def test_debug_preserves_editor_properties(self):
        """debug 模式应保留编辑器布局属性。"""
        prop = PropertyIR(
            name="NodePosX", type="IntProperty", value=100,
            array_index=0, guid=None,
        )
        export = _make_export(properties=[prop])
        ir = _make_ir(exports=[export])
        renderer = get_renderer("json")
        result = renderer.render(ir, RenderOptions(output_level="debug"))
        data = json.loads(result)
        props = data["exports"][0].get("properties", [])
        assert any(p["name"] == "NodePosX" for p in props)

    def test_standard_filters_empty_graphs(self):
        """standard 模式应过滤空 graphs。"""
        graph = GraphIR(
            graph_guid="aaa", graph_name="G", graph_class="EdGraph",
            nodes=[], execution_chains=[],
        )
        export = _make_export(graphs=[graph])
        ir = _make_ir(exports=[export])
        renderer = get_renderer("json")
        result = renderer.render(ir, RenderOptions(output_level="standard"))
        data = json.loads(result)
        assert "graphs" not in data["exports"][0]

    def test_debug_preserves_empty_graphs(self):
        """debug 模式应保留空 graphs。"""
        graph = GraphIR(
            graph_guid="aaa", graph_name="G", graph_class="EdGraph",
            nodes=[], execution_chains=[],
        )
        export = _make_export(graphs=[graph])
        ir = _make_ir(exports=[export])
        renderer = get_renderer("json")
        result = renderer.render(ir, RenderOptions(output_level="debug"))
        data = json.loads(result)
        assert "graphs" in data["exports"][0]

    def test_standard_filters_editor_variables(self):
        """standard 模式应过滤编辑器内部变量。"""
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
        """debug 模式应保留所有变量。"""
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
        """standard 模式应过滤空 execution_chains。"""
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
        """standard 模式下空 properties 不应出现在输出中。"""
        export = _make_export(properties=[])
        ir = _make_ir(exports=[export])
        renderer = get_renderer("json")
        result = renderer.render(ir, RenderOptions(output_level="standard"))
        data = json.loads(result)
        assert "properties" not in data["exports"][0]


# ---------------------------------------------------------------------------
# JSON 渲染器蓝图数据测试
# ---------------------------------------------------------------------------

class TestJSONRendererBlueprint:
    """JSON 渲染器蓝图数据序列化测试。"""

    def test_blueprint_to_dict_basic(self):
        """BlueprintIR 应正确序列化。"""
        blueprint = BlueprintIR(
            parent_class="/Engine/Actor",
            description="Test description",
            interfaces=[{"name": "IInterface"}],
            functions=[
                BlueprintFunctionIR(
                    name="TestFunc", return_type="void",
                    parameters=[{"name": "Val", "param_type": "float"}],
                    is_pure=False, is_blueprint_callable=True,
                )
            ],
            events=[
                BlueprintEventIR(
                    name="OnHit", event_type="Event",
                    parameters=[],
                    is_override=True, override_parent_class="AActor",
                )
            ],
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
        """VariableIR 应正确输出布尔 flags。"""
        ir = _make_ir()
        ir.variables = [
            VariableIR(
                name="Health", type="float", default_value="100.0",
                kind="user", guid="aabb",
                is_edit_anywhere=True, is_replicated=True,
            ),
        ]
        renderer = get_renderer("json")
        result = renderer.render(ir, RenderOptions(output_level="debug"))
        data = json.loads(result)
        var = data["variables"][0]
        assert var["is_edit_anywhere"] is True
        assert var["is_replicated"] is True
        # False flags should not appear
        assert "is_transient" not in var

    def test_function_to_dict_implementation_status(self):
        """BlueprintFunctionIR 应输出 implementation_status。"""
        ir = _make_ir()
        ir.blueprint = BlueprintIR(
            parent_class="/Engine/Actor",
            functions=[
                BlueprintFunctionIR(
                    name="Func1", return_type="void",
                    parameters=[], implementation_status="decompiled",
                ),
                BlueprintFunctionIR(
                    name="Func2", return_type="void",
                    parameters=[], implementation_status="missing",
                ),
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
        """parse_status 非 success 时应输出到导出中。"""
        export = _make_export(parse_status="partial", fallback_reason="reason")
        ir = _make_ir(exports=[export])
        renderer = get_renderer("json")
        result = renderer.render(ir, RenderOptions())
        data = json.loads(result)
        assert data["exports"][0]["parse_status"] == "partial"
        assert data["exports"][0]["fallback_reason"] == "reason"

    def test_diagnostics_dedup_standard_mode(self):
        """standard 模式下 diagnostics 应去重。"""
        class MockDiag:
            def __init__(self, field, error):
                self._d = {"field": field, "error": error}
            def to_dict(self):
                return self._d

        ir = _make_ir()
        ir.diagnostics = [
            MockDiag("SerialOffset", "out of range"),
            MockDiag("SerialOffset", "out of range"),  # duplicate
            MockDiag("SerialSize", "negative"),
        ]
        renderer = get_renderer("json")
        result = renderer.render(ir, RenderOptions(output_level="standard"))
        data = json.loads(result)
        assert len(data["diagnostics"]) == 2

    def test_diagnostics_no_dedup_debug_mode(self):
        """debug 模式下 diagnostics 不应去重。"""
        class MockDiag:
            def __init__(self, field, error):
                self._d = {"field": field, "error": error}
            def to_dict(self):
                return self._d

        ir = _make_ir()
        ir.diagnostics = [
            MockDiag("SerialOffset", "out of range"),
            MockDiag("SerialOffset", "out of range"),
        ]
        renderer = get_renderer("json")
        result = renderer.render(ir, RenderOptions(output_level="debug"))
        data = json.loads(result)
        assert len(data["diagnostics"]) == 2


# ---------------------------------------------------------------------------
# JSON 渲染器节点和 Pin 测试
# ---------------------------------------------------------------------------

class TestJSONRendererNodes:
    """JSON 渲染器节点和 Pin 序列化测试。"""

    def test_node_with_macro_expansion(self):
        """有 macro_expansion 的节点应正确输出。"""
        node = NodeIR(
            node_guid="aabbccdd11223344aabbccdd11223344",
            node_class="K2Node_MacroInstance",
            node_comment=None,
            pins=[],
            execution_flow=[],
            macro_expansion={"macro_name": "TestMacro"},
        )
        graph = GraphIR(
            graph_guid="1122334455667788aabbccdd11223344",
            graph_name="EventGraph", graph_class="EdGraph",
            nodes=[node], execution_chains=[],
        )
        export = _make_export(graphs=[graph])
        ir = _make_ir(exports=[export])
        renderer = get_renderer("json")
        result = renderer.render(ir, RenderOptions())
        data = json.loads(result)
        node_data = data["exports"][0]["graphs"][0]["nodes"][0]
        assert "macro_expansion" in node_data
        assert node_data["macro_expansion"]["macro_name"] == "TestMacro"

    def test_node_without_macro_expansion(self):
        """无 macro_expansion 的节点不应输出该字段。"""
        node = NodeIR(
            node_guid="aabbccdd11223344aabbccdd11223344",
            node_class="K2Node_CallFunction",
            node_comment=None,
            pins=[],
            execution_flow=[],
            macro_expansion=None,
        )
        graph = GraphIR(
            graph_guid="1122334455667788aabbccdd11223344",
            graph_name="EventGraph", graph_class="EdGraph",
            nodes=[node], execution_chains=[],
        )
        export = _make_export(graphs=[graph])
        ir = _make_ir(exports=[export])
        renderer = get_renderer("json")
        result = renderer.render(ir, RenderOptions())
        data = json.loads(result)
        node_data = data["exports"][0]["graphs"][0]["nodes"][0]
        assert "macro_expansion" not in node_data

    def test_pin_to_dict_complete(self):
        """Pin 应包含所有字段。"""
        pin = PinIR(
            pin_name="ReturnValue", pin_type="float",
            pin_type_value="float",
            linked_to=["aabbccdd11223344aabbccdd11223344"],
            direction="output", default_value="0.0",
        )
        node = NodeIR(
            node_guid="aabbccdd11223344aabbccdd11223344",
            node_class="K2Node_CallFunction",
            node_comment=None, pins=[pin], execution_flow=[],
        )
        graph = GraphIR(
            graph_guid="1122334455667788aabbccdd11223344",
            graph_name="EventGraph", graph_class="EdGraph",
            nodes=[node], execution_chains=[],
        )
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


# ---------------------------------------------------------------------------
# JSON 渲染器动画数据测试
# ---------------------------------------------------------------------------

class TestJSONRendererAnimations:
    """JSON 渲染器动画数据序列化测试。"""

    def test_anim_blueprint_full(self):
        """AnimBlueprintIR 应完整序列化。"""
        ir = _make_ir()
        ir.anim_blueprint = AnimBlueprintIR(
            target_skeleton="/Game/Skeleton",
            baked_state_machines=[
                BakedStateMachineIR(
                    machine_name="WalkRun", initial_state=0,
                    states=[
                        BakedStateIR(state_name="Idle", state_root_node_index=0),
                        BakedStateIR(state_name="Run", state_root_node_index=1, b_is_a_conduit=True),
                    ],
                    transitions=[
                        BakedTransitionIR(
                            previous_state=0, next_state=1,
                            crossfade_duration=0.2, blend_mode="Linear",
                        )
                    ],
                )
            ],
            anim_notifies=[
                AnimNotifyIR(notify_name="Footstep", trigger_time_offset=0.5, duration=0.0, notify_class="AN_Footstep"),
            ],
            sync_group_names=["Locomotion"],
        )
        renderer = get_renderer("json")
        result = renderer.render(ir, RenderOptions())
        data = json.loads(result)
        ab = data["anim_blueprint"]
        assert ab["target_skeleton"] == "/Game/Skeleton"
        assert len(ab["baked_state_machines"]) == 1
        sm = ab["baked_state_machines"][0]
        assert sm["machine_name"] == "WalkRun"
        assert len(sm["states"]) == 2
        assert sm["states"][1]["b_is_a_conduit"] is True
        assert len(sm["transitions"]) == 1
        assert len(ab["anim_notifies"]) == 1

    def test_anim_sequence_full(self):
        """AnimSequenceIR 应完整序列化。"""
        ir = _make_ir()
        ir.anim_sequence = AnimSequenceIR(
            target_skeleton="/Game/Skeleton",
            additive_anim_type="AAT_None",
            sequence_length=2.5,
            rate_scale=1.0,
            notifies=[
                AnimNotifyIR(notify_name="Notify1", trigger_time_offset=1.0, duration=0.5, notify_class="AN_Test"),
            ],
            float_curve_names=["Curve1", "Curve2"],
            has_compressed_data=True,
        )
        renderer = get_renderer("json")
        result = renderer.render(ir, RenderOptions())
        data = json.loads(result)
        as_data = data["anim_sequence"]
        assert as_data["target_skeleton"] == "/Game/Skeleton"
        assert as_data["sequence_length"] == 2.5
        assert as_data["has_compressed_data"] is True
        assert len(as_data["notifies"]) == 1
        assert len(as_data["float_curve_names"]) == 2

    def test_anim_montage_full(self):
        """AnimMontageIR 应完整序列化。"""
        ir = _make_ir()
        ir.anim_montage = AnimMontageIR(
            blend_mode_in="Linear",
            blend_mode_out="Linear",
            blend_in_option="BlendIn",
            blend_out_option="BlendOut",
            sync_group="DefaultGroup",
            rate_scale=1.5,
            composite_sections=["Section1"],
            slot_anim_tracks=[{"SlotName": "DefaultSlot"}],
            branching_point_markers=[{"MarkerName": "BP1"}],
            notifies=[
                AnimNotifyIR(notify_name="MontageNotify", trigger_time_offset=0.3, duration=0.0),
            ],
            float_curve_names=["MontageCurve1"],
        )
        renderer = get_renderer("json")
        result = renderer.render(ir, RenderOptions())
        data = json.loads(result)
        am = data["anim_montage"]
        assert am["blend_mode_in"] == "Linear"
        assert am["rate_scale"] == 1.5
        assert len(am["composite_sections"]) == 1
        assert len(am["notifies"]) == 1


# ---------------------------------------------------------------------------
# Markdown 渲染器基础测试
# ---------------------------------------------------------------------------

class TestMarkdownRendererBasic:
    """Markdown 渲染器基础功能测试。"""

    def test_render_produces_string(self):
        """渲染应产生非空字符串。"""
        ir = _make_ir()
        renderer = get_renderer("markdown")
        result = renderer.render(ir, RenderOptions())
        assert isinstance(result, str)
        assert len(result) > 0

    def test_render_contains_asset_overview(self):
        """输出应包含 Asset Overview 表。"""
        ir = _make_ir()
        renderer = get_renderer("markdown")
        result = renderer.render(ir, RenderOptions())
        assert "## Asset Overview" in result
        assert "| Field | Value |" in result
        assert "| Package |" in result

    def test_render_with_package_name_slash(self):
        """路径中的包名应正确提取最后一段作为标题。"""
        ir = _make_ir(header=_make_header(package_name="/Game/Blueprints/BP_MyAsset"))
        renderer = get_renderer("markdown")
        result = renderer.render(ir, RenderOptions())
        assert "# BP_MyAsset" in result

    def test_render_with_simple_name(self):
        """不含路径的包名应直接用作标题。"""
        ir = _make_ir(header=_make_header(package_name="BP_Simple"))
        renderer = get_renderer("markdown")
        result = renderer.render(ir, RenderOptions())
        assert "# BP_Simple" in result


# ---------------------------------------------------------------------------
# Markdown 渲染器蓝图数据测试
# ---------------------------------------------------------------------------

class TestMarkdownRendererBlueprint:
    """Markdown 渲染器蓝图数据渲染测试。"""

    def test_blueprint_details_section(self):
        """有 blueprint 时应输出 Blueprint Details 表。"""
        blueprint = BlueprintIR(
            parent_class="/Engine/Actor",
            description="Test description",
        )
        ir = _make_ir()
        ir.blueprint = blueprint
        renderer = get_renderer("markdown")
        result = renderer.render(ir, RenderOptions())
        assert "## Blueprint Details" in result
        assert "| Parent Class | /Engine/Actor |" in result

    def test_component_hierarchy_mermaid(self):
        """有 components 时应输出 Mermaid 组件层次图。"""
        blueprint = BlueprintIR(
            parent_class="/Engine/Actor",
            components=[
                {"name": "Root", "class": "USceneComponent"},
                {"name": "Mesh", "class": "UStaticMeshComponent"},
            ],
        )
        ir = _make_ir()
        ir.blueprint = blueprint
        renderer = get_renderer("markdown")
        result = renderer.render(ir, RenderOptions())
        assert "### Component Hierarchy" in result
        assert "```mermaid" in result
        assert "graph TD" in result
        assert "Root" in result
        assert "Mesh" in result

    def test_component_detail_table(self):
        """有 components 时应输出组件详情表。"""
        blueprint = BlueprintIR(
            parent_class="/Engine/Actor",
            components=[
                {"name": "Root", "class": "USceneComponent", "transforms": {}},
            ],
        )
        ir = _make_ir()
        ir.blueprint = blueprint
        renderer = get_renderer("markdown")
        result = renderer.render(ir, RenderOptions())
        assert "| Component | Class | Transform |" in result
        assert "| Root | USceneComponent |" in result

    def test_interfaces_rendering(self):
        """interfaces 应正确渲染到 Blueprint Details 表。"""
        blueprint = BlueprintIR(
            parent_class="/Engine/Actor",
            interfaces=[{"name": "IInterfaceA"}, {"name": "IInterfaceB"}],
        )
        ir = _make_ir()
        ir.blueprint = blueprint
        renderer = get_renderer("markdown")
        result = renderer.render(ir, RenderOptions())
        assert "IInterfaceA" in result
        assert "IInterfaceB" in result


# ---------------------------------------------------------------------------
# Markdown 渲染器 Event Graph 测试
# ---------------------------------------------------------------------------

class TestMarkdownRendererEventGraph:
    """Markdown 渲染器 Event Graph 渲染测试。"""

    def test_event_with_decompiled_function(self):
        """有反编译函数的事件应输出 C++ 代码块。"""
        ir = _make_ir()
        ir.blueprint = BlueprintIR(
            parent_class="/Engine/Actor",
            events=[
                BlueprintEventIR(
                    name="ReceiveBeginPlay", event_type="Event",
                    parameters=[],
                )
            ],
        )
        ir.decompiled_functions = [
            DecompiledFunctionIR(
                name="ReceiveBeginPlay",
                signature="void AActor::ReceiveBeginPlay()",
                cpp_code="Super::ReceiveBeginPlay();",
                parameters=[], return_type="void",
            )
        ]
        renderer = get_renderer("markdown")
        result = renderer.render(ir, RenderOptions())
        assert "## Event Graph" in result
        assert "### ReceiveBeginPlay" in result
        assert "void AActor::ReceiveBeginPlay()" in result
        assert "Super::ReceiveBeginPlay();" in result

    def test_event_without_decompiled_function(self):
        """无反编译函数的事件应生成 override 签名。"""
        ir = _make_ir()
        ir.blueprint = BlueprintIR(
            parent_class="/Engine/Actor",
            events=[
                BlueprintEventIR(
                    name="ReceiveBeginPlay", event_type="Event",
                    parameters=[
                        {"name": "OtherActor", "param_type": "AActor*", "is_input": True},
                    ],
                )
            ],
        )
        ir.decompiled_functions = []
        renderer = get_renderer("markdown")
        result = renderer.render(ir, RenderOptions())
        assert "void ReceiveBeginPlay(AActor* OtherActor) override" in result

    def test_event_with_execution_chain(self):
        """有 execution_chain 的事件应输出调用链。"""
        ir = _make_ir()
        ir.blueprint = BlueprintIR(
            parent_class="/Engine/Actor",
            events=[
                BlueprintEventIR(
                    name="ReceiveBeginPlay", event_type="Event", parameters=[],
                )
            ],
        )
        ir.execution_chains = [
            ExecutionChainIR(event="ReceiveBeginPlay", chain=["Begin", "Step1", "Step2"]),
        ]
        renderer = get_renderer("markdown")
        result = renderer.render(ir, RenderOptions())
        assert "Begin -> Step1 -> Step2" in result

    def test_chain_event_not_in_events_list(self):
        """execution_chains 中未在 events 列出的事件也应被渲染。"""
        ir = _make_ir()
        ir.blueprint = BlueprintIR(
            parent_class="/Engine/Actor",
            events=[
                BlueprintEventIR(
                    name="ReceiveBeginPlay", event_type="Event", parameters=[],
                )
            ],
        )
        ir.execution_chains = [
            ExecutionChainIR(event="CustomEvent_1", chain=["X", "Y"]),
        ]
        renderer = get_renderer("markdown")
        result = renderer.render(ir, RenderOptions())
        assert "### CustomEvent_1" in result

    def test_event_only_input_params_in_signature(self):
        """生成的 override 签名应只包含 input 参数。"""
        ir = _make_ir()
        ir.blueprint = BlueprintIR(
            parent_class="/Engine/Actor",
            events=[
                BlueprintEventIR(
                    name="OnHit", event_type="Event",
                    parameters=[
                        {"name": "OtherActor", "param_type": "AActor*", "is_input": True},
                        {"name": "Hit", "param_type": "FHitResult", "is_input": False},
                    ],
                )
            ],
        )
        ir.decompiled_functions = []
        renderer = get_renderer("markdown")
        result = renderer.render(ir, RenderOptions())
        assert "AActor* OtherActor" in result
        assert "FHitResult" not in result


# ---------------------------------------------------------------------------
# Markdown 渲染器 Functions 测试
# ---------------------------------------------------------------------------

class TestMarkdownRendererFunctions:
    """Markdown 渲染器 Functions 渲染测试。"""

    def test_decompiled_function_section(self):
        """反编译函数应渲染为独立章节。"""
        ir = _make_ir()
        ir.decompiled_functions = [
            DecompiledFunctionIR(
                name="TestFunc",
                signature="void TestFunc(float Val)",
                cpp_code="return Val > 0;",
                parameters=[{"name": "Val", "param_type": "float"}],
                return_type="bool",
            )
        ]
        renderer = get_renderer("markdown")
        result = renderer.render(ir, RenderOptions())
        assert "## Functions" in result
        assert "### TestFunc" in result
        assert "`void TestFunc(float Val)`" in result

    def test_function_dedup_decompiled_priority(self):
        """decompiled 函数优先于 blueprint 函数（去重）。"""
        ir = _make_ir()
        ir.blueprint = BlueprintIR(
            parent_class="/Engine/Actor",
            functions=[
                BlueprintFunctionIR(
                    name="TestFunc", return_type="void",
                    parameters=[{"name": "Val", "param_type": "float"}],
                )
            ],
        )
        ir.decompiled_functions = [
            DecompiledFunctionIR(
                name="TestFunc",
                signature="void TestFunc(float Val)",
                cpp_code="return Val > 0;",
                parameters=[{"name": "Val", "param_type": "float"}],
                return_type="bool",
            )
        ]
        renderer = get_renderer("markdown")
        result = renderer.render(ir, RenderOptions())
        # TestFunc should appear only once
        assert result.count("### TestFunc") == 1
        # decompiled signature should be used
        assert "`void TestFunc(float Val)`" in result

    def test_function_signature_generation(self):
        """无 signature 的 blueprint 函数应自动生成签名。"""
        ir = _make_ir()
        ir.blueprint = BlueprintIR(
            parent_class="/Engine/Actor",
            functions=[
                BlueprintFunctionIR(
                    name="Calc", return_type="float",
                    parameters=[
                        {"name": "A", "param_type": "int32", "default_value": 5},
                        {"name": "B", "param_type": "float"},
                    ],
                )
            ],
        )
        renderer = get_renderer("markdown")
        result = renderer.render(ir, RenderOptions())
        assert "int32 A = 5" in result
        assert "float B" in result

    def test_function_parameter_table(self):
        """函数参数应渲染为表格。"""
        ir = _make_ir()
        ir.blueprint = BlueprintIR(
            parent_class="/Engine/Actor",
            functions=[
                BlueprintFunctionIR(
                    name="Func", return_type="void",
                    parameters=[
                        {"name": "X", "param_type": "float", "default_value": 1.0},
                    ],
                )
            ],
        )
        renderer = get_renderer("markdown")
        result = renderer.render(ir, RenderOptions())
        assert "| Parameter | Type | Default |" in result
        assert "| X | float | 1.0 |" in result

    def test_function_cpp_code_block(self):
        """有 cpp_code 的函数应渲染 C++ 代码块。"""
        ir = _make_ir()
        ir.decompiled_functions = [
            DecompiledFunctionIR(
                name="Func",
                signature="void Func()",
                cpp_code="int x = 0;\nreturn;",
                parameters=[], return_type="void",
            )
        ]
        renderer = get_renderer("markdown")
        result = renderer.render(ir, RenderOptions())
        assert "int x = 0;" in result
        assert "return;" in result


# ---------------------------------------------------------------------------
# Markdown 渲染器 Variables 测试
# ---------------------------------------------------------------------------

class TestMarkdownRendererVariables:
    """Markdown 渲染器 Variables 渲染测试。"""

    def test_variables_table(self):
        """变量应渲染为表格。"""
        ir = _make_ir()
        ir.variables = [
            VariableIR(name="Health", type="float", default_value="100.0", kind="user"),
            VariableIR(name="MaxSpeed", type="float", default_value=None, kind="user"),
        ]
        renderer = get_renderer("markdown")
        result = renderer.render(ir, RenderOptions())
        assert "## Variables" in result
        assert "| Name | Type | Default Value |" in result
        assert "| Health | float | 100.0 |" in result
        assert "| MaxSpeed | float | - |" in result

    def test_no_variables_section_when_empty(self):
        """无变量时不应输出 Variables 章节。"""
        ir = _make_ir()
        ir.variables = []
        renderer = get_renderer("markdown")
        result = renderer.render(ir, RenderOptions())
        assert "## Variables" not in result


# ---------------------------------------------------------------------------
# Markdown 渲染器动画数据测试
# ---------------------------------------------------------------------------

class TestMarkdownRendererAnimations:
    """Markdown 渲染器动画数据渲染测试。"""

    def test_anim_blueprint_state_machine(self):
        """AnimBlueprint 状态机应渲染为表格。"""
        ir = _make_ir()
        ir.anim_blueprint = AnimBlueprintIR(
            target_skeleton="/Game/Skeleton",
            baked_state_machines=[
                BakedStateMachineIR(
                    machine_name="WalkRun", initial_state=0,
                    states=[
                        BakedStateIR(state_name="Idle", state_root_node_index=0, b_is_a_conduit=False),
                        BakedStateIR(state_name="Run", state_root_node_index=1, b_is_a_conduit=True),
                    ],
                    transitions=[],
                )
            ],
        )
        renderer = get_renderer("markdown")
        result = renderer.render(ir, RenderOptions())
        assert "### State Machine: WalkRun" in result
        assert "| State | Root Node | Conduit |" in result
        assert "| Idle | #0 | No |" in result
        assert "| Run | #1 | Yes |" in result

    def test_anim_sequence_basic(self):
        """AnimSequence 应渲染基本信息。"""
        ir = _make_ir()
        ir.anim_sequence = AnimSequenceIR(
            target_skeleton="/Game/Skeleton",
            sequence_length=2.5,
            rate_scale=1.0,
            has_compressed_data=True,
        )
        renderer = get_renderer("markdown")
        result = renderer.render(ir, RenderOptions())
        assert "## Animation Sequence" in result
        assert "**Target Skeleton**: `/Game/Skeleton`" in result
        assert "**Sequence Length**: 2.50s" in result
        assert "**Has Compressed Data**: True" in result

    def test_anim_sequence_rate_scale_default(self):
        """AnimSequence rate_scale=1.0 不应显示 Rate Scale。"""
        ir = _make_ir()
        ir.anim_sequence = AnimSequenceIR(
            rate_scale=1.0, sequence_length=1.0,
            has_compressed_data=False,
        )
        renderer = get_renderer("markdown")
        result = renderer.render(ir, RenderOptions())
        # Rate Scale should not appear when it's the default
        anim_seq_section = result.split("## Animation Sequence")[1] if "## Animation Sequence" in result else ""
        assert "Rate Scale" not in anim_seq_section

    def test_anim_montage_basic(self):
        """AnimMontage 应渲染基本信息。"""
        ir = _make_ir()
        ir.anim_montage = AnimMontageIR(
            blend_mode_in="Linear",
            sync_group="Default",
            rate_scale=1.5,
        )
        renderer = get_renderer("markdown")
        result = renderer.render(ir, RenderOptions())
        assert "## Animation Montage" in result
        assert "**Blend In Mode**: Linear" in result
        assert "**Sync Group**: Default" in result
        assert "**Rate Scale**: 1.5" in result

    def test_anim_montage_rate_scale_default(self):
        """AnimMontage rate_scale=1.0 不应显示 Rate Scale。"""
        ir = _make_ir()
        ir.anim_montage = AnimMontageIR(rate_scale=1.0)
        renderer = get_renderer("markdown")
        result = renderer.render(ir, RenderOptions())
        montage_section = result.split("## Animation Montage")[1] if "## Animation Montage" in result else ""
        assert "Rate Scale" not in montage_section

    def test_anim_notify_rendering(self):
        """AnimNotify 应正确渲染（包括 notify_class=None 时显示 '-'）。"""
        ir = _make_ir()
        ir.anim_sequence = AnimSequenceIR(
            notifies=[
                AnimNotifyIR(notify_name="Notify1", trigger_time_offset=0.5, duration=0.0, notify_class="AN_Test"),
                AnimNotifyIR(notify_name="Notify2", trigger_time_offset=1.0, duration=0.0, notify_class=None),
            ],
            has_compressed_data=False,
        )
        renderer = get_renderer("markdown")
        result = renderer.render(ir, RenderOptions())
        assert "| Notify1 | AN_Test | 0.5 |" in result
        assert "| Notify2 | - | 1.0 |" in result


# ---------------------------------------------------------------------------
# Markdown 渲染器诊断和资产注册表测试
# ---------------------------------------------------------------------------

class TestMarkdownRendererDiagnostics:
    """Markdown 渲染器诊断信息渲染测试。"""

    def test_diagnostics_table(self):
        """诊断信息应渲染为表格。"""
        class MockDiag:
            def __init__(self, kind, module, object_name, field, error):
                self._d = {"kind": kind, "module": module, "object_name": object_name, "field": field, "error": error}
            def to_dict(self):
                return self._d

        ir = _make_ir()
        ir.diagnostics = [
            MockDiag("offset", "ExportMap", "Test", "SerialOffset", "out of range"),
        ]
        renderer = get_renderer("markdown")
        result = renderer.render(ir, RenderOptions())
        assert "## 诊断信息" in result
        assert "| 类型 | 模块 | 对象名 | 字段 | 错误信息 |" in result
        assert "SerialOffset" in result

    def test_no_diagnostics_when_empty(self):
        """无诊断信息时不应输出章节。"""
        ir = _make_ir()
        ir.diagnostics = []
        renderer = get_renderer("markdown")
        result = renderer.render(ir, RenderOptions())
        assert "## 诊断信息" not in result


# ---------------------------------------------------------------------------
# Markdown 渲染器资产注册表测试
# ---------------------------------------------------------------------------

class TestMarkdownRendererAssetRegistry:
    """Markdown 渲染器资产注册表渲染测试。"""

    def test_asset_registry_with_objects(self):
        """有 objects 时应渲染资产注册表。"""
        ir = _make_ir()
        ir.asset_registry_data = {
            "objects": [
                {
                    "object_path": "/Game/BP_Test.BP_Test",
                    "object_class_name": "BlueprintGeneratedClass",
                    "tags": {"Tag1": "Value1"},
                }
            ]
        }
        renderer = get_renderer("markdown")
        result = renderer.render(ir, RenderOptions())
        assert "## Asset Registry Data" in result
        assert "BP_Test" in result

    def test_asset_registry_empty_objects(self):
        """空 objects 列表不应渲染章节。"""
        ir = _make_ir()
        ir.asset_registry_data = {"objects": []}
        renderer = get_renderer("markdown")
        result = renderer.render(ir, RenderOptions())
        assert "## Asset Registry Data" not in result


# ---------------------------------------------------------------------------
# Markdown 渲染器 Mermaid 图测试
# ---------------------------------------------------------------------------

class TestMarkdownRendererMermaid:
    """Markdown 渲染器 Mermaid 图渲染测试。"""

    def test_mermaid_with_edges(self):
        """有 linked_to 的节点应生成边。"""
        pin = PinIR(
            pin_name="Then", pin_type="exec", pin_type_value=None,
            linked_to=["bbccdd1122334455bbccdd1122334455"],
            direction="output", default_value=None,
        )
        node1 = NodeIR(
            node_guid="aabbccdd11223344aabbccdd11223344",
            node_class="K2Node_Event", node_comment="BeginPlay",
            pins=[pin], execution_flow=[],
        )
        node2 = NodeIR(
            node_guid="bbccdd1122334455bbccdd1122334455",
            node_class="K2Node_CallFunction", node_comment="DoStuff",
            pins=[], execution_flow=[],
        )
        graph = GraphIR(
            graph_guid="1122334455667788aabbccdd11223344",
            graph_name="EventGraph", graph_class="EdGraph",
            nodes=[node1, node2], execution_chains=[],
        )
        export = _make_export(graphs=[graph])
        ir = _make_ir(exports=[export])
        renderer = get_renderer("markdown")
        result = renderer.render(ir, RenderOptions())
        # Check mermaid has edge
        assert "aabbccdd --> bbccdd11" in result

    def test_mermaid_subgraph(self):
        """子图应渲染为 Mermaid subgraph。"""
        node = NodeIR(
            node_guid="bbccdd1122334455bbccdd1122334455",
            node_class="K2Node_CallFunction", node_comment="Inner",
            pins=[], execution_flow=[],
        )
        subgraph = GraphIR(
            graph_guid="sub111111111111111111111111111111",
            graph_name="SubGraph", graph_class="EdGraph",
            nodes=[node], execution_chains=[],
        )
        graph = GraphIR(
            graph_guid="1122334455667788aabbccdd11223344",
            graph_name="EventGraph", graph_class="EdGraph",
            nodes=[], execution_chains=[], subgraphs=[subgraph],
        )
        export = _make_export(graphs=[graph])
        ir = _make_ir(exports=[export])
        renderer = get_renderer("markdown")
        result = renderer.render(ir, RenderOptions())
        assert "subgraph SubGraph" in result
        assert "end" in result


# ---------------------------------------------------------------------------
# Markdown 渲染器 _escape_md_cell 和 _format_transforms 测试
# ---------------------------------------------------------------------------

class TestMarkdownRendererHelpers:
    """Markdown 渲染器辅助函数测试。"""

    def test_escape_md_cell_pipe(self):
        """管道符应被转义。"""
        from uasset_read.renderers.markdown_renderer import _escape_md_cell
        assert _escape_md_cell("a|b") == "a\\|b"

    def test_escape_md_cell_newline(self):
        """换行符应被替换为空格。"""
        from uasset_read.renderers.markdown_renderer import _escape_md_cell
        assert _escape_md_cell("a\nb") == "a b"

    def test_escape_md_cell_non_string(self):
        """非字符串输入应被转换为字符串。"""
        from uasset_read.renderers.markdown_renderer import _escape_md_cell
        assert _escape_md_cell(42) == "42"

    def test_format_transforms_none(self):
        """None 输入应返回 Identity。"""
        from uasset_read.renderers.markdown_renderer import _format_transforms
        assert _format_transforms(None) == "Identity"

    def test_format_transforms_empty(self):
        """空字典应返回 Identity。"""
        from uasset_read.renderers.markdown_renderer import _format_transforms
        assert _format_transforms({}) == "Identity"

    def test_format_transforms_full(self):
        """完整 transform 字典应正确格式化。"""
        from uasset_read.renderers.markdown_renderer import _format_transforms
        transforms = {
            "relative_location": {"x": 100.0, "y": 200.0, "z": 300.0},
            "relative_rotation": {"pitch": 45.0, "yaw": 90.0, "roll": 0.0},
            "relative_scale": {"x": 1.0, "y": 1.0, "z": 1.0},
        }
        result = _format_transforms(transforms)
        assert "Loc(100.0,200.0,300.0)" in result
        assert "Rot(45.0,90.0,0.0)" in result
        assert "Scale(1.0,1.0,1.0)" in result
