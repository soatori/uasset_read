"""models 核心数据模型单元测试。

覆盖范围：
- models/properties: PropertyTypeName、PropertyTag、PropertyValue、
  StructValue、MapValue、SetValue、EnumValue、TextValue、DelegateValue、
  SoftObjectPathValue
- models/ir: PackageHeaderIR、PinIR、NodeIR、GraphIR、PropertyIR、
  ExportRawIR、ImportIR、ExportIR、ExportDependencyIR、BlueprintFunctionIR、
  BlueprintEventIR、BlueprintIR、DecompiledFunctionIR、ExecutionChainIR、
  LinkerSummaryIR、VariableIR、SourceSiteContextIR、GatherableTextDataIR、
  PackageIR
- models/core: FEdGraphPinType、UEdGraphPin、UEdGraphNode、UEdGraph、
  FMemberReference（序列化模型，无 from_archive）
- models/node_types: 各 K2Node 子类存在性（序列化模型，无 from_archive）
"""
from __future__ import annotations

import pytest

from uasset_read.models.properties import (
    AdvancedPropertyValue,
    DelegateValue,
    EnumValue,
    MapValue,
    PropertyTag,
    PropertyTypeName,
    PropertyValue,
    SetValue,
    SoftObjectPathValue,
    StructValue,
    TextValue,
)
from uasset_read.models.ir import (
    AnimBlueprintIR,
    AnimMontageIR,
    AnimSequenceIR,
    BlueprintEventIR,
    BlueprintFunctionIR,
    BlueprintIR,
    DecompiledFunctionIR,
    ExecutionChainIR,
    ExportDependencyIR,
    ExportIR,
    ExportRawIR,
    GatherableTextDataIR,
    GraphIR,
    ImportIR,
    LinkerSummaryIR,
    NodeIR,
    PackageHeaderIR,
    PackageIR,
    PinIR,
    PropertyIR,
    SourceSiteContextIR,
    VariableIR,
)
from uasset_read.models.core import (
    FEdGraphPinType,
    FMemberReference,
    UEdGraph,
    UEdGraphNode,
    UEdGraphPin,
)
from uasset_read.models.node_types import (
    EdGraphNodeComment,
    K2NodeAddDelegate,
    K2NodeAssignDelegate,
    K2NodeCallArrayFunction,
    K2NodeCallDelegate,
    K2NodeCallFunction,
    K2NodeCallParentFunction,
    K2NodeCreateWidget,
    K2NodeEnhancedInputAction,
    K2NodeEvent,
    K2NodeFunctionEntry,
    K2NodeFunctionResult,
    K2NodeGetDataTableRow,
    K2NodeKnot,
    K2NodeLoadAsset,
    K2NodeMacroInstance,
    K2NodeMessage,
    K2NodeSpawnActorFromClass,
)


# ============================================================================
# models/properties — PropertyTypeName
# ============================================================================


class TestPropertyTypeName:
    """PropertyTypeName 应正确递归创建和查询。"""

    def test_simple_type(self):
        pt = PropertyTypeName(name="IntProperty")
        assert pt.name == "IntProperty"
        assert pt.inner_count == 0
        assert pt.children == []

    def test_child_access(self):
        child = PropertyTypeName(name="IntProperty")
        parent = PropertyTypeName(name="ArrayProperty", children=[child])
        assert parent.inner_count == 1
        assert parent.child(0) is child
        assert parent.child(1) is None
        assert parent.child(-1) is None

    def test_to_parts_simple(self):
        pt = PropertyTypeName(name="IntProperty")
        assert pt.to_parts() == [("IntProperty", 0)]

    def test_to_parts_nested(self):
        inner = PropertyTypeName(name="IntProperty")
        outer = PropertyTypeName(name="ArrayProperty", children=[inner])
        parts = outer.to_parts()
        assert parts == [("ArrayProperty", 1), ("IntProperty", 0)]


# ============================================================================
# models/properties — PropertyTag
# ============================================================================


class TestPropertyTag:
    """PropertyTag 应正确创建。"""

    def test_basic_tag(self):
        tag = PropertyTag(name="Health", type="FloatProperty", size=4)
        assert tag.name == "Health"
        assert tag.type == "FloatProperty"
        assert tag.size == 4
        assert tag.array_index == 0
        assert tag.flags == 0

    def test_tag_with_optional_fields(self):
        tag = PropertyTag(
            name="Name",
            type="StrProperty",
            size=10,
            struct_type="Name",
            inner_type="CharProperty",
            key_type="IntProperty",
            value_type="FloatProperty",
        )
        assert tag.struct_type == "Name"
        assert tag.inner_type == "CharProperty"
        assert tag.key_type == "IntProperty"
        assert tag.value_type == "FloatProperty"


# ============================================================================
# models/properties — PropertyValue
# ============================================================================


class TestPropertyValue:
    """PropertyValue 应正确创建。"""

    def test_basic_value(self):
        pv = PropertyValue(name="Health", type="FloatProperty", value=100.0)
        assert pv.name == "Health"
        assert pv.type == "FloatProperty"
        assert pv.value == 100.0
        assert pv.array_index == 0


# ============================================================================
# models/properties — 高级属性值容器
# ============================================================================


class TestAdvancedPropertyValues:
    """各种高级属性值容器应正确创建。"""

    def test_struct_value(self):
        sv = StructValue(struct_type="Vector", fields={"X": 1.0})
        assert sv.struct_type == "Vector"
        assert sv.fields["X"] == 1.0
        assert sv.parse_status == "parsed"
        assert sv.property_type == "StructProperty"
        assert isinstance(sv, AdvancedPropertyValue)

    def test_map_value(self):
        mv = MapValue(key_type="IntProperty", value_type="FloatProperty")
        assert mv.key_type == "IntProperty"
        assert mv.value_type == "FloatProperty"
        assert mv.entries == []
        assert mv.property_type == "MapProperty"
        assert isinstance(mv, AdvancedPropertyValue)

    def test_set_value(self):
        sv = SetValue(element_type="IntProperty")
        assert sv.element_type == "IntProperty"
        assert sv.elements == []
        assert sv.property_type == "SetProperty"

    def test_enum_value(self):
        ev = EnumValue(enum_type="Color", value_name="Red")
        assert ev.enum_type == "Color"
        assert ev.value_name == "Red"
        assert ev.property_type == "EnumProperty"

    def test_text_value(self):
        tv = TextValue(namespace="NS", key="k", source_string="hello")
        assert tv.namespace == "NS"
        assert tv.key == "k"
        assert tv.source_string == "hello"
        assert tv.property_type == "TextProperty"

    def test_delegate_value(self):
        dv = DelegateValue(object_ref=0, function_name="OnHit")
        assert dv.object_ref == 0
        assert dv.function_name == "OnHit"
        assert dv.property_type == "DelegateProperty"


# ============================================================================
# models/properties — SoftObjectPathValue
# ============================================================================


class TestSoftObjectPathValue:
    """SoftObjectPathValue 应正确创建。"""

    def test_basic(self):
        v = SoftObjectPathValue(raw_kind="SoftObjectPath", asset_path="/Game/Mesh")
        assert v.raw_kind == "SoftObjectPath"
        assert v.asset_path == "/Game/Mesh"
        assert v.error is None


# ============================================================================
# models/ir — PackageHeaderIR
# ============================================================================


class TestPackageHeaderIR:
    """PackageHeaderIR 应正确创建。"""

    def test_minimal_header(self):
        h = PackageHeaderIR(
            package_name="Test",
            package_class="BlueprintGeneratedClass",
            package_flags=0,
            total_export_count=1,
            total_import_count=0,
            ue_version="5.4",
        )
        assert h.package_name == "Test"
        assert h.total_export_count == 1
        assert h.saved_hash == b""


# ============================================================================
# models/ir — PinIR
# ============================================================================


class TestPinIR:
    """PinIR 应正确创建。"""

    def test_basic_pin(self):
        pin = PinIR(
            pin_name="exec",
            pin_type="exec",
            pin_type_value=None,
            linked_to=[],
            direction="output",
            default_value=None,
        )
        assert pin.pin_name == "exec"
        assert pin.linked_to == []


# ============================================================================
# models/ir — NodeIR
# ============================================================================


class TestNodeIR:
    """NodeIR 应正确创建。"""

    def test_basic_node(self):
        node = NodeIR(
            node_guid="abc123",
            node_class="K2Node_Event",
            node_comment=None,
            pins=[],
            execution_flow=[],
        )
        assert node.node_guid == "abc123"
        assert node.pins == []


# ============================================================================
# models/ir — GraphIR
# ============================================================================


class TestGraphIR:
    """GraphIR 应正确创建。"""

    def test_basic_graph(self):
        g = GraphIR(
            graph_guid="def456",
            graph_name="EventGraph",
            graph_class="EdGraph",
            nodes=[],
            execution_chains=[],
        )
        assert g.graph_name == "EventGraph"
        assert g.subgraphs == []


# ============================================================================
# models/ir — PropertyIR
# ============================================================================


class TestPropertyIR:
    """PropertyIR 应正确创建。"""

    def test_basic_property(self):
        p = PropertyIR(name="Health", type="FloatProperty", value=100.0, array_index=0, guid=None)
        assert p.name == "Health"
        assert p.guid is None


# ============================================================================
# models/ir — ExportRawIR
# ============================================================================


class TestExportRawIR:
    """ExportRawIR 应正确创建。"""

    def test_defaults(self):
        r = ExportRawIR()
        assert r.class_index == 0
        assert r.b_forced_export is False
        assert r.guid == ""


# ============================================================================
# models/ir — ImportIR
# ============================================================================


class TestImportIR:
    """ImportIR 应正确创建。"""

    def test_basic_import(self):
        imp = ImportIR(
            index=0,
            class_package="/Script/Engine",
            class_name="Object",
            object_name="TestObject",
        )
        assert imp.class_name == "Object"
        assert imp.outer_index == 0


# ============================================================================
# models/ir — ExportIR
# ============================================================================


class TestExportIR:
    """ExportIR 应正确创建。"""

    def test_minimal_export(self):
        exp = ExportIR(
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
        assert exp.parse_status == "success"
        assert exp.properties == []
        assert exp.graphs == []


# ============================================================================
# models/ir — ExportDependencyIR
# ============================================================================


class TestExportDependencyIR:
    """ExportDependencyIR 应正确创建。"""

    def test_basic_dependency(self):
        d = ExportDependencyIR(
            export_index=0,
            serialization_before_serialization=[],
            create_before_serialization=[],
            serialization_before_create=[],
            create_before_create=[],
        )
        assert d.export_index == 0


# ============================================================================
# models/ir — BlueprintFunctionIR
# ============================================================================


class TestBlueprintFunctionIR:
    """BlueprintFunctionIR 应正确创建。"""

    def test_basic_function(self):
        f = BlueprintFunctionIR(
            name="GetHealth",
            return_type="float",
            parameters=[],
        )
        assert f.is_implemented is True
        assert f.is_pure is False
        assert f.function_flags == 0


# ============================================================================
# models/ir — BlueprintEventIR
# ============================================================================


class TestBlueprintEventIR:
    """BlueprintEventIR 应正确创建。"""

    def test_basic_event(self):
        e = BlueprintEventIR(
            name="ReceiveBeginPlay",
            event_type="CustomEvent",
            parameters=[],
        )
        assert e.name == "ReceiveBeginPlay"


# ============================================================================
# models/ir — BlueprintIR
# ============================================================================


class TestBlueprintIR:
    """BlueprintIR 应正确创建。"""

    def test_basic_blueprint(self):
        bp = BlueprintIR(
            parent_class="Actor",
            description="",
            interfaces=[],
            functions=[],
            events=[],
            components=[],
        )
        assert bp.parent_class == "Actor"
        assert bp.functions == []


# ============================================================================
# models/ir — ExecutionChainIR
# ============================================================================


class TestExecutionChainIR:
    """ExecutionChainIR 应正确创建。"""

    def test_basic_chain(self):
        ec = ExecutionChainIR(event="ReceiveBeginPlay", chain=["node1", "node2"])
        assert ec.event == "ReceiveBeginPlay"
        assert len(ec.chain) == 2


# ============================================================================
# models/ir — LinkerSummaryIR
# ============================================================================


class TestLinkerSummaryIR:
    """LinkerSummaryIR 应正确创建。"""

    def test_basic_linker(self):
        ls = LinkerSummaryIR(has_linker=True, import_paths=[], export_paths=[])
        assert ls.has_linker is True


# ============================================================================
# models/ir — VariableIR
# ============================================================================


class TestVariableIR:
    """VariableIR 应正确创建。"""

    def test_basic_variable(self):
        v = VariableIR(name="Health", type="float", default_value=100.0)
        assert v.name == "Health"


# ============================================================================
# models/ir — SourceSiteContextIR / GatherableTextDataIR
# ============================================================================


class TestSourceSiteContextIR:
    """SourceSiteContextIR 应正确创建。"""

    def test_basic(self):
        ctx = SourceSiteContextIR(
            key_name="key",
            site_description="desc",
            is_editor_only=False,
            is_optional=False,
        )
        assert ctx.key_name == "key"
        assert ctx.is_editor_only is False
        assert ctx.is_optional is False


class TestGatherableTextDataIR:
    """GatherableTextDataIR 应正确创建。"""

    def test_basic(self):
        gtd = GatherableTextDataIR(
            namespace_name="NS",
            source_string="hello",
            source_site_contexts=[],
        )
        assert gtd.namespace_name == "NS"
        assert gtd.source_site_contexts == []


# ============================================================================
# models/ir — PackageIR
# ============================================================================


class TestPackageIR:
    """PackageIR 应正确创建。"""

    def test_minimal_package_ir(self):
        header = PackageHeaderIR(
            package_name="Test",
            package_class="BlueprintGeneratedClass",
            package_flags=0,
            total_export_count=0,
            total_import_count=0,
            ue_version="5.4",
        )
        pkg = PackageIR(
            header=header,
            name_map=[],
            imports=[],
            exports=[],
            linker=None,
            blueprint=None,
        )
        assert pkg.header.package_name == "Test"
        assert pkg.exports == []
        assert pkg.status == "success"


# ============================================================================
# models/core — FEdGraphPinType
# ============================================================================


class TestFEdGraphPinType:
    """FEdGraphPinType 应正确创建。"""

    def test_basic_pin_type(self):
        pt = FEdGraphPinType(
            pin_category="bool",
            pin_subcategory="None",
            pin_subcategory_object=None,
            pin_subcategory_object_name="",
            pin_subcategory_object_ref=None,
            container_type="None",
        )
        assert pt.pin_category == "bool"
        assert pt.is_map_key is False
        assert pt.is_reference is False


# ============================================================================
# models/core — UEdGraphPin
# ============================================================================


class TestUEdGraphPin:
    """UEdGraphPin 应正确创建。"""

    def test_basic_pin(self):
        pin = UEdGraphPin(
            pin_id="abc123",
            pin_name="exec",
            pin_friendly_name="exec",
            pin_tooltip="",
            direction="output",
            pin_type=FEdGraphPinType(pin_category="exec", pin_subcategory="None"),
            default_value=None,
        )
        assert pin.pin_id == "abc123"
        assert pin.hidden is False
        assert pin.linked_to_raw == []


# ============================================================================
# models/core — UEdGraphNode
# ============================================================================


class TestUEdGraphNode:
    """UEdGraphNode 应正确创建。"""

    def test_basic_node(self):
        node = UEdGraphNode(
            node_guid="node123",
            node_pos_x=0,
            node_pos_y=0,
            node_comment="",
            pins=[],
            class_name="K2Node_Event",
        )
        assert node.node_guid == "node123"
        assert node.pins == []


# ============================================================================
# models/core — UEdGraph
# ============================================================================


class TestUEdGraph:
    """UEdGraph 应正确创建。"""

    def test_basic_graph(self):
        graph = UEdGraph(
            graph_name="EventGraph",
            graph_class="EdGraph",
            schema="EdGraphSchema",
            nodes=[],
            graph_guid="graph123",
        )
        assert graph.graph_name == "EventGraph"
        assert graph.subgraphs == []
        assert graph.b_editable is True


# ============================================================================
# models/core — FMemberReference
# ============================================================================


class TestFMemberReference:
    """FMemberReference 应正确创建。"""

    def test_basic_reference(self):
        ref = FMemberReference(
            member_parent=None,
            member_name="GetHealth",
            member_guid="ref123",
            b_self_context=False,
        )
        assert ref.member_name == "GetHealth"
        assert ref.b_self_context is False


# ============================================================================
# models/node_types — 子类存在性
# ============================================================================


class TestNodeTypesExistence:
    """所有 K2Node 子类应可导入且继承自 UEdGraphNode。"""

    @pytest.mark.parametrize(
        "cls",
        [
            K2NodeCallFunction,
            K2NodeEvent,
            K2NodeKnot,
            EdGraphNodeComment,
            K2NodeEnhancedInputAction,
            K2NodeFunctionEntry,
            K2NodeMessage,
            K2NodeCallDelegate,
            K2NodeCallArrayFunction,
            K2NodeCallParentFunction,
            K2NodeFunctionResult,
            K2NodeCreateWidget,
            K2NodeAddDelegate,
            K2NodeMacroInstance,
            K2NodeAssignDelegate,
            K2NodeGetDataTableRow,
            K2NodeLoadAsset,
            K2NodeSpawnActorFromClass,
        ],
    )
    def test_inherits_ue_d_graph_node(self, cls):
        assert issubclass(cls, UEdGraphNode)


class TestK2NodeCallFunction:
    """K2NodeCallFunction 应正确创建。"""

    def test_basic(self):
        node = K2NodeCallFunction(
            node_guid="n1",
            node_pos_x=0,
            node_pos_y=0,
            node_comment=None,
            pins=[],
            class_name="K2Node_CallFunction",
            function_reference=None,
            b_defaults_to_pure=False,
        )
        assert node.b_defaults_to_pure is False
        assert node.function_reference is None


class TestK2NodeEvent:
    """K2NodeEvent 应正确创建。"""

    def test_basic(self):
        node = K2NodeEvent(
            node_guid="n2",
            node_pos_x=0,
            node_pos_y=0,
            node_comment=None,
            pins=[],
            class_name="K2Node_Event",
            event_reference=None,
            b_override_function=False,
        )
        assert node.b_override_function is False


class TestEdGraphNodeComment:
    """EdGraphNodeComment 应正确创建。"""

    def test_basic(self):
        node = EdGraphNodeComment(
            node_guid="n3",
            node_pos_x=0,
            node_pos_y=0,
            node_comment="This is a comment",
            pins=[],
            class_name="EdGraphNode_Comment",
            comment_color=(1.0, 1.0, 1.0, 1.0),
            node_width=200,
            node_height=100,
            font_size=18,
        )
        assert node.node_comment == "This is a comment"
        assert node.font_size == 18


# ============================================================================
# models/core — from_archive 已移除验证
# ============================================================================


class TestFromArchiveRemoved:
    """from_archive 方法已从序列化模型移至 serializers 层（#255 M-5）。"""

    def test_fed_graph_pin_type_no_from_archive(self):
        """FEdGraphPinType 不应有 from_archive 方法。"""
        assert not hasattr(FEdGraphPinType, "from_archive")

    def test_ue_graph_pin_no_from_archive(self):
        """UEdGraphPin 不应有 from_archive 或 from_archive_with_linker 方法。"""
        assert not hasattr(UEdGraphPin, "from_archive")
        assert not hasattr(UEdGraphPin, "from_archive_with_linker")

    def test_ue_graph_node_no_from_archive(self):
        """UEdGraphNode 不应有 from_archive 或 from_archive_with_linker 方法。"""
        assert not hasattr(UEdGraphNode, "from_archive")
        assert not hasattr(UEdGraphNode, "from_archive_with_linker")

    def test_ue_graph_no_from_archive(self):
        """UEdGraph 不应有 from_archive 或 from_archive_with_linker 方法。"""
        assert not hasattr(UEdGraph, "from_archive")
        assert not hasattr(UEdGraph, "from_archive_with_linker")

    def test_f_member_reference_no_from_archive(self):
        """FMemberReference 不应有 from_archive 方法。"""
        assert not hasattr(FMemberReference, "from_archive")


class TestNodeTypesNoFromArchive:
    """K2Node 子类不应有 from_archive 方法（#255 M-5）。"""

    @pytest.mark.parametrize(
        "cls",
        [
            K2NodeCallFunction,
            K2NodeEvent,
            K2NodeKnot,
            EdGraphNodeComment,
            K2NodeEnhancedInputAction,
            K2NodeFunctionEntry,
            K2NodeMessage,
            K2NodeCallDelegate,
            K2NodeCallArrayFunction,
            K2NodeCallParentFunction,
            K2NodeFunctionResult,
            K2NodeCreateWidget,
            K2NodeAddDelegate,
            K2NodeMacroInstance,
            K2NodeAssignDelegate,
            K2NodeGetDataTableRow,
            K2NodeLoadAsset,
            K2NodeSpawnActorFromClass,
        ],
    )
    def test_no_from_archive(self, cls):
        """每个 K2Node 子类不应有 from_archive 方法。"""
        assert not hasattr(cls, "from_archive")


class TestBlueprintNoFromArchive:
    """蓝图元数据 DTO 不应有 from_archive 方法（#255 M-5）。"""

    def test_function_parameter_no_from_archive(self):
        from uasset_read.models.blueprint import FunctionParameter
        assert not hasattr(FunctionParameter, "from_archive")

    def test_multicast_delegate_no_from_archive(self):
        from uasset_read.models.blueprint import MulticastDelegate
        assert not hasattr(MulticastDelegate, "from_archive")

    def test_blueprint_event_no_from_archive(self):
        from uasset_read.models.blueprint import BlueprintEvent
        assert not hasattr(BlueprintEvent, "from_archive")

    def test_blueprint_function_no_from_archive(self):
        from uasset_read.models.blueprint import BlueprintFunction
        assert not hasattr(BlueprintFunction, "from_archive")

    def test_blueprint_variable_no_from_archive(self):
        from uasset_read.models.blueprint import BlueprintVariable
        assert not hasattr(BlueprintVariable, "from_archive")

    def test_blueprint_metadata_no_from_archive(self):
        from uasset_read.models.blueprint import BlueprintMetadata
        assert not hasattr(BlueprintMetadata, "from_archive")


# ============================================================================
# models 分层文档验证（#255 M-4）
# ============================================================================


class TestLayerSeparation:
    """序列化模型与呈现模型应有清晰的分层文档（#255 M-4）。"""

    def test_core_module_docstring_mentions_serialization_layer(self):
        """core.py 模块文档应说明其为序列化层。"""
        import uasset_read.models.core as core_mod
        doc = core_mod.__doc__
        assert "序列化" in doc
        assert "core.py" in doc or "本模块" in doc

    def test_ir_module_docstring_mentions_presentation_layer(self):
        """ir.py 模块文档应说明其为呈现层。"""
        import uasset_read.models.ir as ir_mod
        doc = ir_mod.__doc__
        assert "呈现" in doc
        assert "ir.py" in doc or "本模块" in doc

    def test_pin_ir_docstring_mentions_ue_d_graph_pin(self):
        """PinIR 文档应说明与 UEdGraphPin 的关系。"""
        assert "UEdGraphPin" in PinIR.__doc__

    def test_node_ir_docstring_mentions_ue_d_graph_node(self):
        """NodeIR 文档应说明与 UEdGraphNode 的关系。"""
        assert "UEdGraphNode" in NodeIR.__doc__

    def test_graph_ir_docstring_mentions_ue_d_graph(self):
        """GraphIR 文档应说明与 UEdGraph 的关系。"""
        assert "UEdGraph" in GraphIR.__doc__
