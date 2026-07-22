"""渲染器测试 — 合并自 test_renderers_core.py、test_renderers_text.py、test_report_quality.py。

覆盖：核心渲染、文本渲染。
"""
from __future__ import annotations

import json
from unittest.mock import MagicMock

import pytest

from uasset_read.models.ir import (
    PackageIR,
    PackageHeaderIR,
    ExportIR,
    PropertyIR,
    BlueprintIR,
    LinkerSummaryIR,
    PinIR,
    NodeIR,
    GraphIR,
)
from uasset_read.renderers import get_renderer, list_formats
from uasset_read.renderers.base import IRenderer, RenderOptions


# ============================================================================
# 辅助工厂
# ============================================================================

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


# ============================================================================
# 1. 渲染器注册表基础
# ============================================================================

class TestRendererRegistry:
    def test_registry_contains_json_and_markdown(self):
        """注册表应包含 json 和 markdown。"""
        formats = list_formats()
        assert "json" in formats
        assert "markdown" in formats

    def test_is_blueprint_export_handles_none_object_name(self):
        """#433: object_name 为 None 时不应抛出 AttributeError"""
        from uasset_read.renderers.base import is_blueprint_export

        export = MagicMock()
        export.object_name = None
        export.graphs = []
        assert not is_blueprint_export(export)


# ============================================================================
# 2. JSON 渲染器基础输出
# ============================================================================

class TestJSONRendererBasic:
    def test_render_produces_valid_json(self):
        """渲染结果应为有效 JSON，包含 status、exports。"""
        ir = _make_ir()
        renderer = get_renderer("json")
        data = json.loads(renderer.render(ir, RenderOptions()))
        assert isinstance(data, dict)
        assert "status" in data
        assert "exports" in data


# ============================================================================
# 3. Markdown 渲染器基础输出
# ============================================================================

class TestMarkdownRendererBasic:
    def test_render_produces_string(self):
        """渲染结果应为非空字符串，带路径包名只显示最后一段。"""
        renderer = get_renderer("markdown")
        ir = _make_ir()
        result = renderer.render(ir, RenderOptions())
        assert isinstance(result, str) and len(result) > 0
        # 带路径包名
        ir2 = _make_ir(header=_make_header(package_name="/Game/Blueprints/BP_MyAsset"))
        assert "# BP_MyAsset" in renderer.render(ir2, RenderOptions())


# ============================================================================
# Pin 优化测试
# ============================================================================

def _make_pin(**kwargs) -> "PinIR":
    """构建测试用 PinIR 对象。"""
    from uasset_read.models.ir import PinIR
    defaults = dict(
        pin_name="TestPin",
        pin_type="FEdGraphPinType(pin_category='bool', ...)",
        linked_to=[],
        direction="input",
        default_value="",
        pin_category="bool",
        pin_subcategory="",
        container_type="None",
        is_reference=False,
        is_const=False,
        is_weak_pointer=False,
        is_uobject_wrapper=False,
    )
    defaults.update(kwargs)
    return PinIR(**defaults)


class TestPinOptimization:
    def test_standard_mode_omits_redundant_fields(self):
        """standard 模式下 pin_type、False 布尔值、空字符串被省略。"""
        from uasset_read.renderers.json_renderer import JSONRenderer
        renderer = JSONRenderer()
        pin = _make_pin()
        result = renderer._pin_to_dict(pin, output_level="standard")
        assert "pin_type" not in result
        assert "is_reference" not in result
        assert "is_const" not in result
        assert "is_weak_pointer" not in result
        assert "is_uobject_wrapper" not in result
        assert "default_value" not in result
        assert "pin_subcategory" not in result

        # debug 模式下所有字段保持不变
        result_debug = renderer._pin_to_dict(pin, output_level="debug")
        assert "pin_type" in result_debug
        assert result_debug["is_reference"] is False
        assert result_debug["is_const"] is False
        assert result_debug["default_value"] == ""
        assert result_debug["pin_subcategory"] == ""

        # standard 模式下非默认值不被省略
        pin_non_default = _make_pin(
            is_reference=True,
            is_const=True,
            default_value="true",
            pin_subcategory="native",
        )
        result_non_default = renderer._pin_to_dict(pin_non_default, output_level="standard")
        assert result_non_default["is_reference"] is True
        assert result_non_default["is_const"] is True
        assert result_non_default["default_value"] == "true"
        assert result_non_default["pin_subcategory"] == "native"


# ============================================================================
# Diagnostics 折叠测试
# ============================================================================

class TestDiagnosticsFolding:
    def test_folding_combines_same_pattern(self):
        """相同 (kind, field) 的 diagnostics 被折叠为一条。"""
        from uasset_read.renderers.json_renderer import JSONRenderer
        renderer = JSONRenderer()
        diags = [
            {"kind": "read_name_recovery", "field": "name_map[42]", "error": "adjusted 128 bytes", "current_pos": 100},
            {"kind": "read_name_recovery", "field": "name_map[42]", "error": "adjusted 256 bytes", "current_pos": 200},
            {"kind": "read_name_recovery", "field": "name_map[42]", "error": "adjusted 384 bytes", "current_pos": 300},
        ]
        result = renderer._fold_diagnostics(diags)
        assert len(result) == 1
        assert result[0]["count"] == 3
        assert result[0]["pos_range"]["min"] == 100
        assert result[0]["pos_range"]["max"] == 300
        assert result[0]["error_pattern"] == "adjusted {n} bytes"

        # 不同 (kind, field) 的 diagnostics 不被合并
        diags_different = [
            {"kind": "read_name_recovery", "field": "name_map[42]", "error": "adjusted 128 bytes", "current_pos": 100},
            {"kind": "read_name_recovery", "field": "name_map[43]", "error": "adjusted 256 bytes", "current_pos": 200},
        ]
        result_different = renderer._fold_diagnostics(diags_different)
        assert len(result_different) == 2

    def test_single_item_not_folded(self):
        """单条 diagnostics 不折叠，保持原格式。"""
        from uasset_read.renderers.json_renderer import JSONRenderer
        renderer = JSONRenderer()
        diags = [
            {"kind": "read_name_recovery", "field": "name_map[42]", "error": "adjusted 128 bytes", "current_pos": 100},
        ]
        result = renderer._fold_diagnostics(diags)
        assert len(result) == 1
        assert result[0]["error"] == "adjusted 128 bytes"
        assert "count" not in result[0]

        # 空列表返回空列表
        result_empty = renderer._fold_diagnostics([])
        assert result_empty == []

    def test_error_pattern_extraction(self):
        """error 模式提取正确替换数字为 {n}。"""
        from uasset_read.renderers.json_renderer import JSONRenderer
        renderer = JSONRenderer()
        pattern = renderer._extract_error_pattern("adjusted 128 bytes pos 1234567")
        assert pattern == "adjusted {n} bytes pos {n}"

        # 从 diagnostic 字典中正确提取位置
        pos = renderer._extract_position({"current_pos": 1234567})
        assert pos == 1234567
        assert renderer._extract_position({"current_pos": 0}) == 0
        assert renderer._extract_position({}) is None


# ============================================================================
# 端到端集成测试
# ============================================================================

class TestOutputLevelIntegration:
    def test_standard_vs_debug_pin_output(self):
        """standard 模式 Pin 输出比 debug 模式更简洁。"""
        import json
        from uasset_read.renderers.json_renderer import JSONRenderer
        from uasset_read.renderers.base import RenderOptions

        pin = PinIR(
            pin_name="ReturnValue",
            pin_type="FEdGraphPinType(pin_category='object', ...)",
            linked_to=[],
            direction="EGPD_Output",
            default_value="",
            pin_category="object",
            pin_subcategory="",
            container_type="None",
            is_reference=False,
            is_const=False,
            is_weak_pointer=False,
            is_uobject_wrapper=False,
        )
        node = NodeIR(
            node_guid="abc123",
            node_class="K2Node_CallFunction",
            node_comment="",
            pins=[pin],
            execution_flow=[],
        )
        graph = GraphIR(
            graph_guid="def456",
            graph_name="EventGraph",
            graph_class="EdGraph",
            nodes=[node],
            execution_chains=[],
            subgraphs=[],
            graph_type="Ubergraph",
        )
        export = _make_export(graphs=[graph])
        ir = _make_ir(exports=[export])

        renderer = JSONRenderer()

        # standard 模式
        standard_opts = RenderOptions(output_level="standard")
        standard_data = json.loads(renderer.render(ir, standard_opts))
        standard_pin = standard_data["exports"][0]["graphs"][0]["nodes"][0]["pins"][0]
        assert "pin_type" not in standard_pin
        assert "is_reference" not in standard_pin  # False 值省略
        assert "is_const" not in standard_pin
        assert "is_weak_pointer" not in standard_pin
        assert "is_uobject_wrapper" not in standard_pin
        assert "default_value" not in standard_pin  # 空字符串省略
        assert "pin_subcategory" not in standard_pin  # 空字符串省略
        # 保留字段
        assert standard_pin["pin_name"] == "ReturnValue"
        assert standard_pin["pin_category"] == "object"
        assert "container_type" not in standard_pin  # "None" 在 standard 模式下省略

        # debug 模式
        debug_opts = RenderOptions(output_level="debug")
        debug_data = json.loads(renderer.render(ir, debug_opts))
        debug_pin = debug_data["exports"][0]["graphs"][0]["nodes"][0]["pins"][0]
        assert "pin_type" in debug_pin
        assert debug_pin["is_reference"] is False
        assert debug_pin["is_const"] is False
        assert debug_pin["default_value"] == ""
        assert debug_pin["pin_subcategory"] == ""


# ============================================================================
# parent_class null 省略测试
# ============================================================================

class TestNullFieldOmission:
    def test_standard_omits_parent_class_when_none(self):
        """Export null 字段省略：parent_class None/有值/debug。"""
        from uasset_read.renderers.json_renderer import JSONRenderer
        renderer = JSONRenderer()
        export_none = _make_export(parent_class=None)
        result = renderer._export_to_dict(export_none, RenderOptions(output_level="standard"))
        assert "parent_class" not in result
        export_set = _make_export(parent_class="/Engine/Actor")
        result2 = renderer._export_to_dict(export_set, RenderOptions(output_level="standard"))
        assert result2["parent_class"] == "/Engine/Actor"
        result3 = renderer._export_to_dict(export_none, RenderOptions(output_level="debug"), is_debug=True)
        assert "parent_class" in result3 and result3["parent_class"] is None

    def test_property_standard_omits_null_guid(self):
        """Property null 字段省略：guid/array_index/debug。"""
        from uasset_read.renderers.json_renderer import JSONRenderer
        renderer = JSONRenderer()
        prop_none = PropertyIR(name="P", type="BoolProperty", value=True, array_index=0, guid=None)
        assert "guid" not in renderer._property_to_dict(prop_none, is_debug=False)
        prop_guid = PropertyIR(name="P", type="BoolProperty", value=True, array_index=0, guid="abc123")
        assert renderer._property_to_dict(prop_guid, is_debug=False)["guid"] == "abc123"
        prop_default = PropertyIR(name="P", type="BoolProperty", value=True, array_index=-1, guid=None)
        assert "array_index" not in renderer._property_to_dict(prop_default, is_debug=False)
        prop_custom = PropertyIR(name="P", type="ArrayProperty", value=[], array_index=3, guid=None)
        assert renderer._property_to_dict(prop_custom, is_debug=False)["array_index"] == 3
        result_debug = renderer._property_to_dict(prop_none, is_debug=True)
        assert "guid" in result_debug and result_debug["array_index"] == 0


# ============================================================================
# Pin container_type 省略测试
# ============================================================================

class TestPinContainerTypeOmission:
    def test_standard_omits_container_type_none(self):
        """standard 模式下 container_type='None' 被省略。"""
        from uasset_read.renderers.json_renderer import JSONRenderer
        renderer = JSONRenderer()
        pin = _make_pin(container_type="None")
        result = renderer._pin_to_dict(pin, output_level="standard")
        assert "container_type" not in result

    def test_debug_preserves_container_type_none(self):
        """debug 模式下 container_type='None' 保留。"""
        from uasset_read.renderers.json_renderer import JSONRenderer
        renderer = JSONRenderer()
        pin = _make_pin(container_type="None")
        result = renderer._pin_to_dict(pin, output_level="debug")
        assert result["container_type"] == "None"

    def test_standard_preserves_non_default_container_type(self):
        """standard 模式下非默认 container_type 被保留。"""
        from uasset_read.renderers.json_renderer import JSONRenderer
        renderer = JSONRenderer()
        for ct in ("Array", "Set", "Map"):
            pin = _make_pin(container_type=ct)
            result = renderer._pin_to_dict(pin, output_level="standard")
            assert result["container_type"] == ct


# ============================================================================
# Node 字段省略测试
# ============================================================================

class TestNodeFieldOmission:
    def test_standard_omits_empty_execution_flow(self):
        """standard 模式下空 execution_flow 被省略。"""
        from uasset_read.renderers.json_renderer import JSONRenderer
        renderer = JSONRenderer()
        node = NodeIR(
            node_guid="abc", node_class="K2Node_Event",
            node_comment=None, pins=[], execution_flow=[],
        )
        result = renderer._node_to_dict(node, output_level="standard")
        assert "execution_flow" not in result

    def test_debug_preserves_empty_execution_flow(self):
        """debug 模式下空 execution_flow 保留。"""
        from uasset_read.renderers.json_renderer import JSONRenderer
        renderer = JSONRenderer()
        node = NodeIR(
            node_guid="abc", node_class="K2Node_Event",
            node_comment=None, pins=[], execution_flow=[],
        )
        result = renderer._node_to_dict(node, output_level="debug")
        assert "execution_flow" in result
        assert result["execution_flow"] == []

    def test_standard_omits_null_node_comment(self):
        """standard 模式下 null node_comment 被省略。"""
        from uasset_read.renderers.json_renderer import JSONRenderer
        renderer = JSONRenderer()
        node = NodeIR(
            node_guid="abc", node_class="K2Node_Event",
            node_comment=None, pins=[], execution_flow=[],
        )
        result = renderer._node_to_dict(node, output_level="standard")
        assert "node_comment" not in result

    def test_debug_preserves_null_node_comment(self):
        """debug 模式下 null node_comment 保留。"""
        from uasset_read.renderers.json_renderer import JSONRenderer
        renderer = JSONRenderer()
        node = NodeIR(
            node_guid="abc", node_class="K2Node_Event",
            node_comment=None, pins=[], execution_flow=[],
        )
        result = renderer._node_to_dict(node, output_level="debug")
        assert "node_comment" in result
        assert result["node_comment"] is None

    def test_standard_preserves_non_null_node_comment(self):
        """standard 模式下非空 node_comment 保留。"""
        from uasset_read.renderers.json_renderer import JSONRenderer
        renderer = JSONRenderer()
        node = NodeIR(
            node_guid="abc", node_class="K2Node_Event",
            node_comment="test comment", pins=[], execution_flow=[],
        )
        result = renderer._node_to_dict(node, output_level="standard")
        assert result["node_comment"] == "test comment"

    def test_standard_omits_empty_trigger_events(self):
        """standard 模式下空 trigger_events 被省略。"""
        from uasset_read.renderers.json_renderer import JSONRenderer
        renderer = JSONRenderer()
        node = NodeIR(
            node_guid="abc", node_class="K2Node_Event",
            node_comment=None, pins=[], execution_flow=[],
            trigger_events=[],
        )
        result = renderer._node_to_dict(node, output_level="standard")
        assert "trigger_events" not in result

    def test_standard_omits_null_event_type(self):
        """standard 模式下 null event_type 被省略。"""
        from uasset_read.renderers.json_renderer import JSONRenderer
        renderer = JSONRenderer()
        node = NodeIR(
            node_guid="abc", node_class="K2Node_Event",
            node_comment=None, pins=[], execution_flow=[],
            event_type=None,
        )
        result = renderer._node_to_dict(node, output_level="standard")
        assert "event_type" not in result

    def test_standard_omits_null_input_action_path(self):
        """standard 模式下 null input_action_path 被省略。"""
        from uasset_read.renderers.json_renderer import JSONRenderer
        renderer = JSONRenderer()
        node = NodeIR(
            node_guid="abc", node_class="K2Node_Event",
            node_comment=None, pins=[], execution_flow=[],
            input_action_path=None,
        )
        result = renderer._node_to_dict(node, output_level="standard")
        assert "input_action_path" not in result

    def test_debug_preserves_enhanced_input_fields(self):
        """debug 模式下 Enhanced Input 字段全部保留。"""
        from uasset_read.renderers.json_renderer import JSONRenderer
        renderer = JSONRenderer()
        node = NodeIR(
            node_guid="abc", node_class="K2Node_Event",
            node_comment=None, pins=[], execution_flow=[],
            trigger_events=[{"event": "Triggered"}],
            event_type="Triggered",
            input_action_path="/Game/IA_Jump",
        )
        result = renderer._node_to_dict(node, output_level="debug")
        assert result["trigger_events"] == [{"event": "Triggered"}]
        assert result["event_type"] == "Triggered"
        assert result["input_action_path"] == "/Game/IA_Jump"


# ============================================================================
# StructValue 元数据省略测试
# ============================================================================

class TestStructMetadataOmission:
    def test_standard_omits_default_parse_status(self):
        """standard 模式下 parse_status='success' 被省略。"""
        from uasset_read.renderers.json_renderer import JSONRenderer
        from uasset_read.models.properties import StructValue
        renderer = JSONRenderer()
        sv = StructValue(struct_type="Vector", fields={"X": 1.0})
        prop = PropertyIR(name="Location", type="StructProperty", value=sv, array_index=0, guid=None)
        result = renderer._property_to_dict(prop, is_debug=False)
        assert "parse_status" not in result["value"]

    def test_standard_omits_default_property_type(self):
        """standard 模式下 property_type='StructProperty' 被省略。"""
        from uasset_read.renderers.json_renderer import JSONRenderer
        from uasset_read.models.properties import StructValue
        renderer = JSONRenderer()
        sv = StructValue(struct_type="Vector", fields={"X": 1.0})
        prop = PropertyIR(name="Location", type="StructProperty", value=sv, array_index=0, guid=None)
        result = renderer._property_to_dict(prop, is_debug=False)
        assert "property_type" not in result["value"]

    def test_debug_preserves_struct_metadata(self):
        """debug 模式下 StructValue 保持原始 dataclass，不做转换。"""
        from uasset_read.renderers.json_renderer import JSONRenderer
        from uasset_read.models.properties import StructValue
        renderer = JSONRenderer()
        sv = StructValue(struct_type="Vector", fields={"X": 1.0})
        prop = PropertyIR(name="Location", type="StructProperty", value=sv, array_index=0, guid=None)
        result = renderer._property_to_dict(prop, is_debug=True)
        # debug 模式下 value 保持原始 StructValue dataclass（未被 dataclasses.asdict 转换）
        assert isinstance(result["value"], StructValue)
        assert result["value"].parse_status == "success"
        assert result["value"].property_type == "StructProperty"

    def test_standard_preserves_non_default_struct_metadata(self):
        """standard 模式下非默认 StructValue 元数据被保留。"""
        from uasset_read.renderers.json_renderer import JSONRenderer
        from uasset_read.models.properties import StructValue
        renderer = JSONRenderer()
        sv = StructValue(
            struct_type="Vector", fields={"X": 1.0},
            parse_status="partial", property_type="NotStructProperty",
        )
        prop = PropertyIR(name="Location", type="StructProperty", value=sv, array_index=0, guid=None)
        result = renderer._property_to_dict(prop, is_debug=False)
        assert result["value"]["parse_status"] == "partial"
        assert result["value"]["property_type"] == "NotStructProperty"


# ============================================================================
# ObjectProperty full_name 省略测试
# ============================================================================

class TestObjectPropertyFullNameOmission:
    def test_standard_omits_full_name(self):
        """standard 模式下 ObjectProperty 的 full_name 被省略。"""
        from uasset_read.renderers.json_renderer import JSONRenderer
        renderer = JSONRenderer()
        obj_value = {
            "object_name": "BP_Player",
            "object_class": "BlueprintGeneratedClass",
            "full_name": "/Game/Blueprints/BP_Player.BP_Player_C",
        }
        prop = PropertyIR(name="Target", type="ObjectProperty", value=obj_value, array_index=0, guid=None)
        result = renderer._property_to_dict(prop, is_debug=False)
        assert "full_name" not in result["value"]
        assert "object_name" in result["value"]

    def test_debug_preserves_full_name(self):
        """debug 模式下 ObjectProperty 的 full_name 保留。"""
        from uasset_read.renderers.json_renderer import JSONRenderer
        renderer = JSONRenderer()
        obj_value = {
            "object_name": "BP_Player",
            "object_class": "BlueprintGeneratedClass",
            "full_name": "/Game/Blueprints/BP_Player.BP_Player_C",
        }
        prop = PropertyIR(name="Target", type="ObjectProperty", value=obj_value, array_index=0, guid=None)
        result = renderer._property_to_dict(prop, is_debug=True)
        assert result["value"]["full_name"] == "/Game/Blueprints/BP_Player.BP_Player_C"

    def test_non_object_property_unaffected(self):
        """非 ObjectProperty 类型不受 full_name 省略影响。"""
        from uasset_read.renderers.json_renderer import JSONRenderer
        renderer = JSONRenderer()
        other_value = {
            "some_key": "some_value",
            "full_name": "should remain",
        }
        prop = PropertyIR(name="Data", type="StructProperty", value=other_value, array_index=0, guid=None)
        result = renderer._property_to_dict(prop, is_debug=False)
        assert result["value"]["full_name"] == "should remain"
