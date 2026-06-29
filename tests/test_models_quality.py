"""models/mappings 模块缺陷测试。"""
from __future__ import annotations

import pytest
from dataclasses import fields as dc_fields

from uasset_read.models import ir
from uasset_read.models.ir import (
    PackageIR, PackageHeaderIR, PinIR, NodeIR, GraphIR,
    PropertyIR, ExportIR, ExportRawIR, ImportIR, LinkerSummaryIR,
    ExportDependencyIR, BlueprintFunctionIR, BlueprintEventIR,
    BlueprintIR, DecompiledFunctionIR, ExecutionChainIR,
    VariableIR, SourceSiteContextIR, GatherableTextDataIR,
    AnimBlueprintIR, AnimSequenceIR, AnimMontageIR,
    BakedStateMachineIR, BakedStateIR, BakedTransitionIR,
    BakedExitTransitionIR, AnimNotifyIR,
)
from uasset_read.models.core import (
    FEdGraphPinType, UEdGraphPin, UEdGraphNode, UEdGraph, FMemberReference,
)
from uasset_read.models.node_types import (
    K2NodeCallFunction, K2NodeEvent, K2NodeKnot,
    EdGraphNodeComment, K2NodeEnhancedInputAction, K2NodeFunctionEntry,
)
from uasset_read.models.result import ParseResult, StatusInfo
from uasset_read.models.blueprint import (
    BlueprintMetadata, BlueprintVariable, BlueprintFunction,
    BlueprintEvent, BlueprintInterface, FunctionParameter, MulticastDelegate,
)
from uasset_read.models.properties import (
    PropertyTag, PropertyTypeName, PropertyValue, SoftObjectPathValue,
    AdvancedPropertyValue, StructValue, MapValue, SetValue,
    EnumValue, TextValue, DelegateValue,
)
from uasset_read.models.transforms import (
    VectorValue, RotatorValue, ScaleValue, format_transform_value,
)
from uasset_read.models.fallback import (
    PropertyFallback, StructFallback, GenericUObject,
    ExportParseStatus, FallbackReason,
)
from uasset_read.models.diagnostics import OffsetRangeDiagnostic
from uasset_read.mappings import (
    TypeMappings, StructMapping, PropertyInfo, PropertyType,
    UsmapParser, JmapParser, TypeMappingsProvider,
)


class TestModelsImports:
    """models 模块可正常导入。"""

    def test_models_imports(self):
        """models 模块可正常导入。"""
        from uasset_read.models import ir
        assert ir is not None

    def test_models_package_imports_all(self):
        """models 包的 __all__ 导出应包含所有核心模型。"""
        from uasset_read.models import __all__ as all_exports
        expected = [
            "PackageIR", "PinIR", "NodeIR", "GraphIR", "ExportIR",
            "ParseResult", "StatusInfo",
            "BlueprintMetadata", "BlueprintVariable", "BlueprintFunction",
            "PropertyTag", "PropertyTypeName", "PropertyValue",
            "VectorValue", "RotatorValue", "ScaleValue",
            "PropertyFallback", "StructFallback", "GenericUObject",
            "OffsetRangeDiagnostic",
        ]
        for name in expected:
            assert name in all_exports, f"__all__ 缺少 {name}"


class TestIRDataclass:
    """IR 数据结构应可实例化。"""

    def test_package_header_ir_instantiation(self):
        """PackageHeaderIR 应可正确实例化。"""
        h = PackageHeaderIR(
            package_name="TestPkg",
            package_class="/Script/CoreUObject.Package",
            package_flags=0,
            total_export_count=2,
            total_import_count=1,
            ue_version="5.4",
        )
        assert h.package_name == "TestPkg"
        assert h.total_export_count == 2
        assert h.saved_hash == b""

    def test_pin_ir_instantiation(self):
        """PinIR 应可正确实例化。"""
        pin = PinIR(
            pin_name="OutputPin",
            pin_type="bool",
            pin_type_value=None,
            linked_to=["abcdef1234567890abcdef1234567890"],
            direction="output",
            default_value="true",
        )
        assert pin.pin_name == "OutputPin"
        assert len(pin.linked_to) == 1

    def test_node_ir_instantiation(self):
        """NodeIR 应可正确实例化。"""
        node = NodeIR(
            node_guid="abc123",
            node_class="K2Node_CallFunction",
            node_comment=None,
            pins=[],
            execution_flow=[],
        )
        assert node.node_class == "K2Node_CallFunction"
        assert node.macro_expansion is None

    def test_graph_ir_instantiation(self):
        """GraphIR 应可正确实例化，subgraphs 默认空列表。"""
        g = GraphIR(
            graph_guid="g1",
            graph_name="EventGraph",
            graph_class="UEdGraph",
            nodes=[],
            execution_chains=[],
        )
        assert g.subgraphs == []
        assert g.graph_type is None

    def test_export_ir_instantiation(self):
        """ExportIR 应可正确实例化。"""
        e = ExportIR(
            index=0,
            object_name="TestExport",
            object_class="BlueprintGeneratedClass",
            serial_size=1024,
            outer_index_resolved=None,
            super_index_resolved=None,
            parent_class=None,
            properties=[],
            graphs=[],
            bulk_data=None,
        )
        assert e.parse_status == "success"
        assert e.anim_blueprint is None
        assert e.ue_export_raw is None

    def test_export_dependency_ir(self):
        """ExportDependencyIR 应可正确实例化。"""
        d = ExportDependencyIR(
            export_index=0,
            serialization_before_serialization=[],
            create_before_serialization=[],
            serialization_before_create=[],
            create_before_create=[],
        )
        assert d.export_index == 0

    def test_package_ir_instantiation(self):
        """PackageIR 应可正确实例化，所有列表字段默认为空。"""
        pkg = PackageIR(
            header=PackageHeaderIR(
                package_name="Pkg",
                package_class="/Script/CoreUObject.Package",
                package_flags=0,
                total_export_count=0,
                total_import_count=0,
                ue_version="5.4",
            ),
            name_map=[],
            imports=[],
            exports=[],
            linker=None,
        )
        assert pkg.blueprint is None
        assert pkg.decompiled_functions == []
        assert pkg.execution_chains == []
        assert pkg.variables == []
        assert pkg.status == "success"

    def test_anim_blueprint_ir(self):
        """AnimBlueprintIR 应可正确实例化。"""
        abp = AnimBlueprintIR()
        assert abp.baked_state_machines == []
        assert abp.anim_notifies == []

    def test_anim_sequence_ir(self):
        """AnimSequenceIR 应可正确实例化。"""
        seq = AnimSequenceIR(sequence_length=120.5, rate_scale=1.0)
        assert seq.sequence_length == 120.5
        assert seq.notifies == []

    def test_anim_montage_ir(self):
        """AnimMontageIR 应可正确实例化。"""
        m = AnimMontageIR(rate_scale=1.5)
        assert m.rate_scale == 1.5
        assert m.composite_sections == []

    def test_baked_state_machine_ir(self):
        """BakedStateMachineIR 应可正确实例化。"""
        sm = BakedStateMachineIR(machine_name="IdleRun", initial_state=0)
        assert sm.states == []
        assert sm.transitions == []

    def test_source_site_context_ir(self):
        """SourceSiteContextIR 应可正确实例化。"""
        ctx = SourceSiteContextIR(
            key_name="test_key",
            site_description="source.cpp:42",
            is_editor_only=True,
            is_optional=False,
        )
        assert ctx.key_name == "test_key"

    def test_gatherable_text_data_ir(self):
        """GatherableTextDataIR 应可正确实例化。"""
        gtd = GatherableTextDataIR(
            namespace_name="NSLOCTEXT",
            source_string="Hello",
            source_site_contexts=[],
        )
        assert gtd.source_string == "Hello"


class TestCoreModels:
    """核心数据模型测试。"""

    def test_fed_graph_pin_type_defaults(self):
        """FEdGraphPinType 默认值应正确。"""
        t = FEdGraphPinType()
        assert t.pin_category == ""
        assert t.is_reference is False
        assert t.is_weak_pointer is False

    def test_ue_graph_pin_instantiation(self):
        """UEdGraphPin 应可正确实例化。"""
        pin = UEdGraphPin(
            pin_id="abc123",
            pin_name="TestPin",
        )
        assert pin.pin_id == "abc123"
        assert pin.linked_to_raw == []
        assert pin.hidden is False

    def test_ue_graph_node_instantiation(self):
        """UEdGraphNode 应可正确实例化。"""
        node = UEdGraphNode(node_guid="guid123")
        assert node.pins == []
        assert node.node_pos_x == 0

    def test_ue_graph_instantiation(self):
        """UEdGraph 应可正确实例化。"""
        g = UEdGraph(
            graph_name="EventGraph",
            graph_class="UEdGraph",
        )
        assert g.nodes == []
        assert g.subgraphs == []
        assert g.b_editable is True

    def test_f_member_reference_defaults(self):
        """FMemberReference 默认值应正确。"""
        ref = FMemberReference()
        assert ref.member_parent is None
        assert ref.member_name == ""
        assert ref.b_self_context is False


class TestNodeTypes:
    """节点类型子类测试。"""

    def test_k2node_call_function(self):
        """K2NodeCallFunction 应继承 UEdGraphNode 字段。"""
        n = K2NodeCallFunction(node_guid="g1")
        assert n.function_reference is None
        assert n.b_defaults_to_pure is False
        assert isinstance(n, UEdGraphNode)

    def test_k2node_event(self):
        """K2NodeEvent 应继承 UEdGraphNode 字段。"""
        n = K2NodeEvent(node_guid="g2")
        assert n.event_reference is None
        assert n.b_override_function is False

    def test_k2node_knot(self):
        """K2NodeKnot 应继承 UEdGraphNode 字段。"""
        n = K2NodeKnot(node_guid="g3")
        assert isinstance(n, UEdGraphNode)

    def test_ed_graph_node_comment(self):
        """EdGraphNodeComment 应有注释颜色和尺寸字段。"""
        n = EdGraphNodeComment(node_guid="g4")
        assert n.comment_color == (0.05, 0.05, 0.05, 1.0)
        assert n.font_size == 14

    def test_k2node_enhanced_input_action(self):
        """K2NodeEnhancedInputAction 应有 trigger_events 字段。"""
        n = K2NodeEnhancedInputAction(node_guid="g5")
        assert n.trigger_events == {}
        assert n.input_action_path == ""


class TestResultModels:
    """ParseResult / StatusInfo 测试。"""

    def test_parse_result_status_empty(self):
        """空 ParseResult 的 status 应为 failed。"""
        pr = ParseResult()
        assert pr.status == "failed"

    def test_parse_result_status_success(self):
        """无错误的 ParseResult 应为 success。"""
        pr = ParseResult(
            name_map=["test"],
            export_map=[],
            is_success=True,
        )
        assert pr.status == "success"

    def test_parse_result_status_partial_with_errors(self):
        """有 errors 的 ParseResult 应为 partial。"""
        pr = ParseResult(
            name_map=["test"],
            errors=["error1"],
        )
        assert pr.status == "partial"

    def test_parse_result_status_partial_lightweight(self):
        """lightweight_tolerant_parse metadata 应返回 partial。"""
        pr = ParseResult(
            name_map=["test"],
            metadata={"lightweight_tolerant_parse": True},
        )
        assert pr.status == "partial"

    def test_status_info(self):
        """StatusInfo 应可正确实例化。"""
        si = StatusInfo(status="success")
        assert si.message is None
        assert si.code is None


class TestBlueprintModels:
    """蓝图元数据模型测试。"""

    def test_blueprint_metadata_instantiation(self):
        """BlueprintMetadata 应可正确实例化。"""
        bm = BlueprintMetadata(is_blueprint=True)
        assert bm.parent_class is None
        assert bm.variables == []
        assert bm.functions == []
        assert bm.events == []
        assert bm.interfaces == []

    def test_blueprint_variable_instantiation(self):
        """BlueprintVariable 应可正确实例化。"""
        bv = BlueprintVariable(var_name="Health")
        assert bv.var_type is None
        assert bv.property_flags == 0
        assert bv.is_transient is False

    def test_blueprint_function_instantiation(self):
        """BlueprintFunction 应可正确实例化。"""
        bf = BlueprintFunction(name="TakeDamage")
        assert bf.return_type == ""
        assert bf.parameters == []
        assert bf.is_implemented is True

    def test_blueprint_event_instantiation(self):
        """BlueprintEvent 应可正确实例化。"""
        be = BlueprintEvent(name="ReceiveBeginPlay")
        assert be.event_type == ""
        assert be.is_override is False
        assert be.parameters == []

    def test_function_parameter_instantiation(self):
        """FunctionParameter 应可正确实例化。"""
        fp = FunctionParameter(name="DamageAmount")
        assert fp.is_input is True
        assert fp.is_output is False

    def test_multicast_delegate_instantiation(self):
        """MulticastDelegate 应可正确实例化。"""
        md = MulticastDelegate(delegate_name="OnHealthChanged")
        assert md.is_callable_in_blueprint is False


class TestPropertyModels:
    """属性数据模型测试。"""

    def test_property_type_name_children(self):
        """PropertyTypeName 应正确管理子节点。"""
        root = PropertyTypeName(name="Array")
        child = PropertyTypeName(name="Struct")
        root.children.append(child)
        assert root.inner_count == 1
        assert root.child(0).name == "Struct"
        assert root.child(1) is None
        assert root.child(-1) is None

    def test_property_type_name_to_parts(self):
        """PropertyTypeName.to_parts() 应递归返回完整路径。"""
        root = PropertyTypeName(name="Map")
        key = PropertyTypeName(name="Name")
        val = PropertyTypeName(name="Vector")
        root.children = [key, val]
        parts = root.to_parts()
        assert parts == [("Map", 2), ("Name", 0), ("Vector", 0)]

    def test_property_tag_defaults(self):
        """PropertyTag 默认值应正确。"""
        tag = PropertyTag(name="TestProp", type="IntProperty", size=4)
        assert tag.array_index == 0
        assert tag.serialize_type == "Property"
        assert tag.type_name is None
        assert tag.tag_data is None

    def test_property_value_instantiation(self):
        """PropertyValue 应可正确实例化。"""
        pv = PropertyValue(name="Health", type="FloatProperty", value=100.0)
        assert pv.array_index == 0

    def test_soft_object_path_value_defaults(self):
        """SoftObjectPathValue 默认值应正确。"""
        sp = SoftObjectPathValue(raw_kind="SoftObject")
        assert sp.asset_path == ""
        assert sp.guid is None
        assert sp.index is None
        assert sp.error is None

    def test_struct_value(self):
        """StructValue 应可正确实例化。"""
        sv = StructValue(
            struct_type="Vector",
            fields={"X": 0.0, "Y": 0.0, "Z": 0.0},
        )
        assert sv.property_type == "StructProperty"
        assert sv.parse_status == "parsed"

    def test_map_value(self):
        """MapValue 应可正确实例化。"""
        mv = MapValue(key_type="Name", value_type="FloatProperty")
        assert mv.property_type == "MapProperty"
        assert mv.entries == []

    def test_set_value(self):
        """SetValue 应可正确实例化。"""
        sv = SetValue(element_type="Name")
        assert sv.property_type == "SetProperty"
        assert sv.elements == []

    def test_enum_value(self):
        """EnumValue 应可正确实例化。"""
        ev = EnumValue(enum_type="ETestEnum", value_name="Value1")
        assert ev.property_type == "EnumProperty"

    def test_text_value(self):
        """TextValue 应可正确实例化。"""
        tv = TextValue(namespace="NS", key="K", source_string="Hello")
        assert tv.property_type == "TextProperty"

    def test_delegate_value(self):
        """DelegateValue 应可正确实例化。"""
        dv = DelegateValue(object_ref=1, function_name="OnClicked")
        assert dv.property_type == "DelegateProperty"

    def test_advanced_property_value_hierarchy(self):
        """AdvancedPropertyValue 子类应正确继承。"""
        sv = StructValue(struct_type="Test")
        assert isinstance(sv, AdvancedPropertyValue)
        mv = MapValue(key_type="K", value_type="V")
        assert isinstance(mv, AdvancedPropertyValue)


class TestTransformModels:
    """变换数据模型测试。"""

    def test_vector_value(self):
        """VectorValue 应可正确实例化。"""
        v = VectorValue(x=1.0, y=2.0, z=3.0)
        assert v.property_type == "StructProperty"

    def test_rotator_value(self):
        """RotatorValue 应可正确实例化。"""
        r = RotatorValue(roll=0.0, pitch=45.0, yaw=90.0)
        assert r.unit == "degrees"

    def test_scale_value(self):
        """ScaleValue 应可正确实例化。"""
        s = ScaleValue(x=1.0, y=1.0, z=1.0)
        assert s.property_type == "StructProperty"

    def test_format_transform_value_location_integer(self):
        """format_transform_value location 整数值应返回 int。"""
        result = format_transform_value(5.0, "location")
        assert result == 5
        assert isinstance(result, int)

    def test_format_transform_value_location_float(self):
        """format_transform_value location 浮点值应返回 3 位小数。"""
        result = format_transform_value(5.5555, "location")
        assert result == 5.556  # round(5.5555, 3) = 5.556 (Python banker's rounding)

    def test_format_transform_value_rotation(self):
        """format_transform_value rotation 应返回 3 位小数。"""
        result = format_transform_value(90.12345, "rotation")
        assert result == 90.123

    def test_format_transform_value_scale(self):
        """format_transform_value scale 应返回 4 位小数。"""
        result = format_transform_value(1.12345, "scale")
        assert result == 1.1235

    def test_format_transform_value_unknown_type(self):
        """format_transform_value 未知类型应原样返回。"""
        result = format_transform_value(42.0, "unknown")
        assert result == 42.0

    def test_format_transform_value_zero(self):
        """format_transform_value 零值 location 应返回 int(0)。"""
        result = format_transform_value(0.0, "location")
        assert result == 0
        assert isinstance(result, int)


class TestFallbackModels:
    """Fallback 模型测试。"""

    def test_property_fallback_instantiation(self):
        """PropertyFallback 应可正确实例化。"""
        pf = PropertyFallback(name="Test", type="Unknown", size=0)
        assert pf.reason == FallbackReason.UNSUPPORTED_TYPE
        assert pf.kind == "unknown_property"

    def test_property_fallback_to_dict(self):
        """PropertyFallback.to_dict() 应返回完整字典。"""
        pf = PropertyFallback(
            name="Test",
            type="Unknown",
            size=10,
            raw_bytes=b"\x00" * 300,
            error_message="test error",
        )
        d = pf.to_dict()
        assert d["kind"] == "unknown_property"
        assert d["name"] == "Test"
        assert d["type"] == "Unknown"
        assert d["size"] == 10
        assert d["raw_data_truncated"] is True
        assert d["raw_data_full_size"] == 300
        assert d["error_message"] == "test error"

    def test_property_fallback_to_dict_no_raw(self):
        """PropertyFallback.to_dict() 无 raw_bytes 时不应包含 raw_data。"""
        pf = PropertyFallback(name="T", type="U", size=0)
        d = pf.to_dict()
        assert "raw_data" not in d

    def test_struct_fallback_instantiation(self):
        """StructFallback 应可正确实例化。"""
        sf = StructFallback(struct_type="UnknownStruct", size=0)
        assert sf.reason == FallbackReason.UNSUPPORTED_STRUCT
        assert sf.kind == "struct_fallback"

    def test_struct_fallback_to_dict(self):
        """StructFallback.to_dict() 应返回完整字典。"""
        sf = StructFallback(
            struct_type="TestStruct",
            size=64,
            fields={"X": 1.0},
            raw_bytes=b"\xff" * 300,
        )
        d = sf.to_dict()
        assert d["kind"] == "struct_fallback"
        assert d["struct_type"] == "TestStruct"
        assert d["size"] == 64
        assert d["fields"] == {"X": 1.0}
        assert d["raw_data_truncated"] is True

    def test_generic_uobject_instantiation(self):
        """GenericUObject 应可正确实例化。"""
        go = GenericUObject(name="Test", class_name="UObject")
        assert go.parse_status == ExportParseStatus.FALLBACK
        assert go.kind == "generic_uobject"

    def test_generic_uobject_to_dict(self):
        """GenericUObject.to_dict() 应返回完整字典。"""
        go = GenericUObject(
            name="Test",
            class_name="UStaticMesh",
            requires_mappings=True,
            missing_mapping="FStaticMesh",
        )
        d = go.to_dict()
        assert d["kind"] == "generic_uobject"
        assert d["name"] == "Test"
        assert d["requires_mappings"] is True
        assert d["missing_mapping"] == "FStaticMesh"

    def test_export_parse_status_values(self):
        """ExportParseStatus 枚举值应正确。"""
        assert ExportParseStatus.SUCCESS.value == "success"
        assert ExportParseStatus.PARTIAL.value == "partial"
        assert ExportParseStatus.FALLBACK.value == "fallback"
        assert ExportParseStatus.SKIPPED.value == "skipped"
        assert ExportParseStatus.FAILED.value == "failed"

    def test_fallback_reason_values(self):
        """FallbackReason 枚举值应正确。"""
        assert FallbackReason.UNSUPPORTED_TYPE.value == "unsupported_type"
        assert FallbackReason.UNSUPPORTED_STRUCT.value == "unsupported_struct"
        assert FallbackReason.PARSE_ERROR.value == "parse_error"
        assert FallbackReason.MISSING_MAPPING.value == "missing_mapping"


class TestDiagnosticsModels:
    """诊断模型测试。"""

    def test_offset_range_diagnostic_instantiation(self):
        """OffsetRangeDiagnostic 应可正确实例化。"""
        d = OffsetRangeDiagnostic()
        assert d.kind == "offset_range_diagnostic"
        assert d.fallback_used is False

    def test_offset_range_diagnostic_to_dict_minimal(self):
        """OffsetRangeDiagnostic.to_dict() 最小字段集应正确。"""
        d = OffsetRangeDiagnostic()
        result = d.to_dict()
        assert result["kind"] == "offset_range_diagnostic"
        assert result["current_pos"] == 0
        assert result["target_offset"] == 0
        assert result["read_size"] == 0
        assert result["file_size"] == 0

    def test_offset_range_diagnostic_to_dict_full(self):
        """OffsetRangeDiagnostic.to_dict() 完整字段应正确序列化。"""
        d = OffsetRangeDiagnostic(
            asset_path="/Game/Test",
            asset_type="Blueprint",
            module="linker",
            object_name="TestObj",
            export_index=3,
            field="serial_offset",
            current_pos=100,
            target_offset=200,
            read_size=50,
            file_size=1000,
            range_start=150,
            range_end=250,
            source="test",
            error="test error",
            fallback_used=True,
            fallback_result="partial",
        )
        result = d.to_dict()
        assert result["asset_path"] == "/Game/Test"
        assert result["asset_type"] == "Blueprint"
        assert result["module"] == "linker"
        assert result["object_name"] == "TestObj"
        assert result["export_index"] == 3
        assert result["range_start"] == 150
        assert result["range_end"] == 250
        assert result["fallback_used"] is True
        assert result["fallback_result"] == "partial"

    def test_offset_range_diagnostic_to_dict_omits_none(self):
        """OffsetRangeDiagnostic.to_dict() 应省略 None 可选整数字段。"""
        d = OffsetRangeDiagnostic()
        result = d.to_dict()
        assert "export_index" not in result
        assert "import_index" not in result
        assert "range_start" not in result
        assert "range_end" not in result

    def test_offset_range_diagnostic_to_dict_omits_empty_strings(self):
        """OffsetRangeDiagnostic.to_dict() 应省略空字符串字段。"""
        d = OffsetRangeDiagnostic()
        result = d.to_dict()
        assert "asset_path" not in result
        assert "module" not in result
        assert "error" not in result


class TestTypeMappings:
    """TypeMappings 容器测试。"""

    def test_type_mappings_defaults(self):
        """TypeMappings 默认值应正确。"""
        tm = TypeMappings()
        assert tm.types == {}
        assert tm.enums == {}

    def test_struct_mapping_property_by_name(self):
        """StructMapping.property_by_name 应按名称查找属性。"""
        sm = StructMapping(
            name="TestStruct",
            properties={
                0: PropertyInfo(index=0, name="Health", mapping_type=PropertyType("FloatProperty")),
                1: PropertyInfo(index=1, name="MaxHealth", mapping_type=PropertyType("FloatProperty")),
            },
        )
        found = sm.property_by_name("Health")
        assert found is not None
        assert found.name == "Health"

    def test_struct_mapping_property_by_name_case_insensitive(self):
        """StructMapping.property_by_name 应不区分大小写。"""
        sm = StructMapping(
            name="TestStruct",
            properties={
                0: PropertyInfo(index=0, name="Health", mapping_type=PropertyType("FloatProperty")),
            },
        )
        found = sm.property_by_name("health")
        assert found is not None
        assert found.name == "Health"

    def test_struct_mapping_property_by_name_not_found(self):
        """StructMapping.property_by_name 找不到时应返回 None。"""
        sm = StructMapping(name="TestStruct")
        assert sm.property_by_name("Nonexistent") is None

    def test_type_mappings_get_struct(self):
        """TypeMappings.get_struct 应按名称查找结构体。"""
        tm = TypeMappings()
        sm = StructMapping(name="MyStruct")
        tm.types["MyStruct"] = sm
        assert tm.get_struct("MyStruct") is sm

    def test_type_mappings_get_struct_with_dot_prefix(self):
        """TypeMappings.get_struct 应支持点号分隔的名称。"""
        tm = TypeMappings()
        sm = StructMapping(name="MyStruct")
        tm.types["MyStruct"] = sm
        assert tm.get_struct("/Script/Game.MyStruct") is sm

    def test_type_mappings_get_struct_none(self):
        """TypeMappings.get_struct(None) 应返回 None。"""
        tm = TypeMappings()
        assert tm.get_struct(None) is None

    def test_type_mappings_get_struct_not_found(self):
        """TypeMappings.get_struct 找不到时应返回 None。"""
        tm = TypeMappings()
        assert tm.get_struct("Nonexistent") is None

    def test_type_mappings_get_struct_fallback(self):
        """TypeMappings.get_struct 应在 short name 查找失败后尝试全名。"""
        tm = TypeMappings()
        sm = StructMapping(name="MyStruct")
        tm.types["/Script.Game.MyStruct"] = sm
        # short name 查找失败，应尝试全名
        result = tm.get_struct("/Script.Game.MyStruct")
        assert result is sm

    def test_type_mappings_property_by_name(self):
        """TypeMappings.property_by_name 应按结构体和属性名查找。"""
        tm = TypeMappings()
        sm = StructMapping(
            name="MyStruct",
            properties={
                0: PropertyInfo(index=0, name="Value", mapping_type=PropertyType("IntProperty")),
            },
        )
        tm.types["MyStruct"] = sm
        found = tm.property_by_name("MyStruct", "Value")
        assert found is not None
        assert found.name == "Value"

    def test_type_mappings_property_by_name_with_super(self):
        """TypeMappings.property_by_name 应沿 super 链查找。"""
        tm = TypeMappings()
        base = StructMapping(
            name="BaseStruct",
            properties={
                0: PropertyInfo(index=0, name="BaseProp", mapping_type=PropertyType("IntProperty")),
            },
        )
        child = StructMapping(
            name="ChildStruct",
            super_type="BaseStruct",
            properties={
                0: PropertyInfo(index=0, name="ChildProp", mapping_type=PropertyType("IntProperty")),
            },
        )
        tm.types["BaseStruct"] = base
        tm.types["ChildStruct"] = child
        found = tm.property_by_name("ChildStruct", "BaseProp")
        assert found is not None
        assert found.name == "BaseProp"

    def test_type_mappings_property_by_name_circular_super(self):
        """TypeMappings.property_by_name 应处理循环 super 引用。"""
        tm = TypeMappings()
        a = StructMapping(name="A", super_type="B", properties={
            0: PropertyInfo(index=0, name="PropA", mapping_type=PropertyType("IntProperty")),
        })
        b = StructMapping(name="B", super_type="A", properties={})
        tm.types["A"] = a
        tm.types["B"] = b
        # 不应死循环
        found = tm.property_by_name("A", "PropA")
        assert found is not None


class TestPropertyType:
    """PropertyType 数据模型测试。"""

    def test_property_type_simple(self):
        """PropertyType 简单类型应正确。"""
        pt = PropertyType(type="IntProperty")
        assert pt.type == "IntProperty"
        assert pt.struct_type is None
        assert pt.inner_type is None
        assert pt.value_type is None

    def test_property_type_struct(self):
        """PropertyType 结构体类型应正确。"""
        pt = PropertyType(type="StructProperty", struct_type="Vector")
        assert pt.struct_type == "Vector"

    def test_property_type_array(self):
        """PropertyType 数组类型应正确。"""
        inner = PropertyType(type="IntProperty")
        pt = PropertyType(type="ArrayProperty", inner_type=inner)
        assert pt.inner_type is not None
        assert pt.inner_type.type == "IntProperty"

    def test_property_type_map(self):
        """PropertyType Map 类型应正确。"""
        key = PropertyType(type="NameProperty")
        val = PropertyType(type="FloatProperty")
        pt = PropertyType(type="MapProperty", inner_type=key, value_type=val)
        assert pt.inner_type.type == "NameProperty"
        assert pt.value_type.type == "FloatProperty"

    def test_property_type_enum(self):
        """PropertyType 枚举类型应正确。"""
        pt = PropertyType(type="EnumProperty", inner_type=PropertyType("ByteProperty"), enum_name="ETest")
        assert pt.enum_name == "ETest"


class TestUsmapParser:
    """UsmapParser 解析测试。"""

    def test_property_type_names_coverage(self):
        """_PROPERTY_TYPE_NAMES 应覆盖所有已知类型。"""
        from uasset_read.mappings import _PROPERTY_TYPE_NAMES
        # 基本类型
        assert 0 in _PROPERTY_TYPE_NAMES  # ByteProperty
        assert 1 in _PROPERTY_TYPE_NAMES  # BoolProperty
        assert 9 in _PROPERTY_TYPE_NAMES  # StructProperty
        assert 24 in _PROPERTY_TYPE_NAMES  # MapProperty
        # 特殊标记
        assert 0xFD in _PROPERTY_TYPE_NAMES
        assert 0xFE in _PROPERTY_TYPE_NAMES
        assert 0xFF in _PROPERTY_TYPE_NAMES

    def test_usmap_parser_rejects_bad_magic(self):
        """UsmapParser 应拒绝无效的 magic number。"""
        from uasset_read.exceptions import ParseError
        bad_data = b"\x00\x00" + b"\x00" * 100
        with pytest.raises(ParseError, match="magic 无效"):
            UsmapParser(bad_data)

    def test_usmap_parser_rejects_bad_version(self):
        """UsmapParser 应拒绝过高的版本号。"""
        from uasset_read.exceptions import ParseError
        # magic + version=5 (> 4)
        data = b"\xC4\x30" + bytes([5]) + b"\x00" * 100
        with pytest.raises(ParseError, match="版本无效"):
            UsmapParser(data)

    def test_usmap_parser_rejects_unsupported_compression(self):
        """UsmapParser 应拒绝不支持的压缩方式。"""
        from uasset_read.exceptions import ParseError
        # 构建一个看起来有效但压缩方式无效的数据
        import struct
        data = bytearray()
        data += struct.pack("<H", 0x30C4)  # magic
        data += struct.pack("<B", 4)  # version
        data += struct.pack("<B", 0)  # has_editor_data = false
        data += struct.pack("<B", 99)  # 压缩方式 99（不支持）
        data += struct.pack("<I", 10)  # comp_size
        data += struct.pack("<I", 10)  # decomp_size
        data += b"\x00" * 10  # payload
        with pytest.raises(ParseError, match="不支持的 Usmap 压缩方式"):
            UsmapParser(bytes(data))


class TestJmapParser:
    """JmapParser 解析测试。"""

    def test_jmap_parser_empty(self):
        """JmapParser 应处理空 JSON。"""
        data = b'{"objects": {}}'
        jp = JmapParser(data)
        assert jp.mappings.types == {}
        assert jp.mappings.enums == {}

    def test_jmap_parser_enum(self):
        """JmapParser 应正确解析枚举类型。"""
        import json
        data = json.dumps({
            "objects": {
                "/Script/Game.ETestEnum": {
                    "type": "Enum",
                    "names": [["Value0", 0], ["Value1", 1]],
                }
            }
        }).encode("utf-8")
        jp = JmapParser(data)
        assert "ETestEnum" in jp.mappings.enums
        assert jp.mappings.enums["ETestEnum"][0] == "Value0"
        assert jp.mappings.enums["ETestEnum"][1] == "Value1"

    def test_jmap_parser_class(self):
        """JmapParser 应正确解析类结构体。"""
        import json
        data = json.dumps({
            "objects": {
                "/Script.Game.MyClass": {
                    "type": "Class",
                    "super_struct": "/Script/CoreUObject.Object",
                    "properties": [
                        {"name": "Health", "type": "FloatProperty", "array_dim": 1},
                    ],
                }
            }
        }).encode("utf-8")
        jp = JmapParser(data)
        assert "MyClass" in jp.mappings.types
        sm = jp.mappings.types["MyClass"]
        assert sm.super_type == "Object"
        assert len(sm.properties) == 1

    def test_jmap_parser_struct(self):
        """JmapParser 应正确解析 ScriptStruct。"""
        import json
        data = json.dumps({
            "objects": {
                "/Script/Game.FMyStruct": {
                    "type": "ScriptStruct",
                    "properties": [
                        {"name": "X", "type": "FloatProperty"},
                        {"name": "Y", "type": "FloatProperty"},
                    ],
                }
            }
        }).encode("utf-8")
        jp = JmapParser(data)
        assert "FMyStruct" in jp.mappings.types

    def test_jmap_parser_non_dict_objects_ignored(self):
        """JmapParser 应忽略非 dict 的 objects 值。"""
        import json
        data = json.dumps({
            "objects": {
                "BadEntry": "not a dict",
                "AlsoBad": 123,
            }
        }).encode("utf-8")
        jp = JmapParser(data)
        assert jp.mappings.types == {}

    def test_jmap_parser_non_dict_properties_ignored(self):
        """JmapParser 应忽略非 dict 的 properties 元素。"""
        import json
        data = json.dumps({
            "objects": {
                "/Script.Game.MyClass": {
                    "type": "Class",
                    "properties": [
                        "not_a_dict",
                        42,
                        {"name": "Valid", "type": "IntProperty"},
                    ],
                }
            }
        }).encode("utf-8")
        jp = JmapParser(data)
        sm = jp.mappings.types["MyClass"]
        assert len(sm.properties) == 1

    def test_jmap_parser_super_struct_dot_prefix(self):
        """JmapParser 应剥离 super_struct 的点号前缀。"""
        import json
        data = json.dumps({
            "objects": {
                "/Script/CoreUObject.Object": {
                    "type": "Class",
                    "super_struct": "",
                    "properties": [],
                },
                "/Script.Game.Child": {
                    "type": "Class",
                    "super_struct": "/Script/CoreUObject.Object",
                    "properties": [],
                }
            }
        }).encode("utf-8")
        jp = JmapParser(data)
        assert jp.mappings.types["Child"].super_type == "Object"


class TestTypeMappingsProvider:
    """TypeMappingsProvider 测试。"""

    def test_type_mappings_provider_unsupported_extension(self):
        """TypeMappingsProvider 应拒绝不支持的文件扩展名。"""
        from uasset_read.exceptions import ParseError
        with pytest.raises(ParseError, match="不支持的映射文件类型"):
            TypeMappingsProvider.from_file("test.xyz")

    def test_type_mappings_provider_from_type_mappings(self):
        """TypeMappingsProvider 应可从 TypeMappings 实例创建。"""
        tm = TypeMappings()
        provider = TypeMappingsProvider(tm)
        assert provider.mappings is tm


class TestExportParseStatusEnum:
    """ExportParseStatus 枚举完整性。"""

    def test_all_statuses_have_string_values(self):
        """所有 ExportParseStatus 值应为字符串。"""
        for status in ExportParseStatus:
            assert isinstance(status.value, str)

    def test_status_string_equality(self):
        """ExportParseStatus 应支持与字符串比较。"""
        assert ExportParseStatus.SUCCESS == "success"
        assert ExportParseStatus.PARTIAL == "partial"
        assert ExportParseStatus.FAILED == "failed"


# =============================================================================
# 缺陷检测测试（Defect Detection Tests）
# =============================================================================


class TestTransformDefects:
    """缺陷 #1: format_transform_value NaN/inf 崩溃。"""

    def test_format_transform_value_nan_location(self):
        """format_transform_value location 遇 NaN 不应崩溃。"""
        import math
        result = format_transform_value(float("nan"), "location")
        assert math.isnan(result)

    def test_format_transform_value_inf_location(self):
        """format_transform_value location 遇 inf 不应崩溃。"""
        import math
        result = format_transform_value(float("inf"), "location")
        assert result == float("inf")

    def test_format_transform_value_neg_inf_location(self):
        """format_transform_value location 遇 -inf 不应崩溃。"""
        import math
        result = format_transform_value(float("-inf"), "location")
        assert result == float("-inf")

    def test_format_transform_value_nan_rotation(self):
        """format_transform_value rotation 遇 NaN 不应崩溃。"""
        import math
        result = format_transform_value(float("nan"), "rotation")
        assert math.isnan(result)

    def test_format_transform_value_inf_scale(self):
        """format_transform_value scale 遇 inf 不应崩溃。"""
        result = format_transform_value(float("inf"), "scale")
        assert result == float("inf")


class TestExportRawIRDefaultsDefect:
    """缺陷 #3: b_not_always_loaded_for_editor_game 默认值反转。"""

    def test_export_raw_ir_default_flag_value(self):
        """ExportRawIR.b_not_always_loaded_for_editor_game 默认应为 False。"""
        raw = ExportRawIR()
        assert raw.b_not_always_loaded_for_editor_game is False

    def test_export_ir_default_flag_value(self):
        """ExportIR.b_not_always_loaded_for_editor_game 默认应为 False。"""
        e = ExportIR(
            index=0,
            object_name="Test",
            object_class="UObject",
            serial_size=0,
            outer_index_resolved=None,
            super_index_resolved=None,
            parent_class=None,
            properties=[],
            graphs=[],
            bulk_data=None,
        )
        assert e.b_not_always_loaded_for_editor_game is False


class TestModelsExportsDefect:
    """缺陷 #4: models/__init__.py 缺少 IR 数据类导出。"""

    def test_import_ir(self):
        """ImportIR 应可通过 models 包导入。"""
        from uasset_read.models import ImportIR
        assert ImportIR is not None

    def test_import_export_dependency_ir(self):
        """ExportDependencyIR 应可通过 models 包导入。"""
        from uasset_read.models import ExportDependencyIR
        assert ExportDependencyIR is not None

    def test_import_blueprint_function_ir(self):
        """BlueprintFunctionIR 应可通过 models 包导入。"""
        from uasset_read.models import BlueprintFunctionIR
        assert BlueprintFunctionIR is not None

    def test_import_blueprint_event_ir(self):
        """BlueprintEventIR 应可通过 models 包导入。"""
        from uasset_read.models import BlueprintEventIR
        assert BlueprintEventIR is not None

    def test_import_blueprint_ir(self):
        """BlueprintIR 应可通过 models 包导入。"""
        from uasset_read.models import BlueprintIR
        assert BlueprintIR is not None

    def test_import_decompiled_function_ir(self):
        """DecompiledFunctionIR 应可通过 models 包导入。"""
        from uasset_read.models import DecompiledFunctionIR
        assert DecompiledFunctionIR is not None

    def test_import_execution_chain_ir(self):
        """ExecutionChainIR 应可通过 models 包导入。"""
        from uasset_read.models import ExecutionChainIR
        assert ExecutionChainIR is not None

    def test_import_variable_ir(self):
        """VariableIR 应可通过 models 包导入。"""
        from uasset_read.models import VariableIR
        assert VariableIR is not None

    def test_import_source_site_context_ir(self):
        """SourceSiteContextIR 应可通过 models 包导入。"""
        from uasset_read.models import SourceSiteContextIR
        assert SourceSiteContextIR is not None

    def test_import_gatherable_text_data_ir(self):
        """GatherableTextDataIR 应可通过 models 包导入。"""
        from uasset_read.models import GatherableTextDataIR
        assert GatherableTextDataIR is not None

    def test_import_anim_notify_ir(self):
        """AnimNotifyIR 应可通过 models 包导入。"""
        from uasset_read.models import AnimNotifyIR
        assert AnimNotifyIR is not None

    def test_import_anim_blueprint_ir(self):
        """AnimBlueprintIR 应可通过 models 包导入。"""
        from uasset_read.models import AnimBlueprintIR
        assert AnimBlueprintIR is not None

    def test_import_anim_sequence_ir(self):
        """AnimSequenceIR 应可通过 models 包导入。"""
        from uasset_read.models import AnimSequenceIR
        assert AnimSequenceIR is not None

    def test_import_anim_montage_ir(self):
        """AnimMontageIR 应可通过 models 包导入。"""
        from uasset_read.models import AnimMontageIR
        assert AnimMontageIR is not None

    def test_import_baked_exit_transition_ir(self):
        """BakedExitTransitionIR 应可通过 models 包导入。"""
        from uasset_read.models import BakedExitTransitionIR
        assert BakedExitTransitionIR is not None

    def test_import_baked_state_ir(self):
        """BakedStateIR 应可通过 models 包导入。"""
        from uasset_read.models import BakedStateIR
        assert BakedStateIR is not None

    def test_import_baked_transition_ir(self):
        """BakedTransitionIR 应可通过 models 包导入。"""
        from uasset_read.models import BakedTransitionIR
        assert BakedTransitionIR is not None

    def test_import_baked_state_machine_ir(self):
        """BakedStateMachineIR 应可通过 models 包导入。"""
        from uasset_read.models import BakedStateMachineIR
        assert BakedStateMachineIR is not None


class TestFileHandleLeakDefect:
    """缺陷 #2: UsmapParser/JmapParser 文件句柄泄漏。"""

    def test_usmap_parser_bytes_input(self):
        """UsmapParser 接受 bytes 时不打开文件。"""
        from uasset_read.exceptions import ParseError
        with pytest.raises(ParseError):
            UsmapParser(b"not_a_usmap")

    def test_jmap_parser_bytes_input(self):
        """JmapParser 接受 bytes 时不打开文件。"""
        import json
        data = json.dumps({"objects": {}}).encode("utf-8")
        jp = JmapParser(data)
        assert jp.mappings is not None
