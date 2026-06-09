"""Tests for blueprint_ue_text renderer golden fixtures."""
import pytest
from pathlib import Path

from uasset_read.renderers.blueprint_ue_renderer import (
    BlueprintUERenderer,
    _format_ue_value,
)
from uasset_read.renderers.base import RenderOptions
from uasset_read.models.ir import (
    PackageIR,
    PackageHeaderIR,
    ExportIR,
    ExportRawIR,
    GraphIR,
    NodeIR,
    PinIR,
    PropertyIR,
    LinkerSummaryIR,
)
from uasset_read.models.properties import (
    StructValue,
    TextValue,
    EnumValue,
    MapValue,
    SetValue,
    DelegateValue,
    SoftObjectPathValue,
)


FIXTURES_DIR = Path(__file__).parent / "fixtures" / "ue_editor_blueprint_text"


def load_golden(filename: str) -> str:
    """加载 golden fixture 文件。"""
    return (FIXTURES_DIR / filename).read_text(encoding="utf-8")


def _make_header(**overrides) -> PackageHeaderIR:
    """构造默认 PackageHeaderIR。"""
    defaults = dict(
        package_name="TestBlueprint",
        package_class="Blueprint",
        package_flags=0,
        total_export_count=0,
        total_import_count=0,
        ue_version="5.3.0",
    )
    defaults.update(overrides)
    return PackageHeaderIR(**defaults)


def _make_ir(exports=None, **header_kw) -> PackageIR:
    """构造最小 PackageIR。"""
    return PackageIR(
        header=_make_header(**header_kw),
        name_map=[],
        imports=[],
        exports=exports or [],
        linker=LinkerSummaryIR(has_linker=False, import_paths=[], export_paths=[]),
    )


def _make_pin(name, pin_type, linked_to=None, default_value=None):
    """构造 PinIR。"""
    return PinIR(
        pin_name=name,
        pin_type=pin_type,
        pin_type_value="",
        linked_to=linked_to or [],
        direction="EGPD_Output",
        default_value=default_value,
    )


def _make_node(node_class, guid, comment=None, pins=None):
    """构造 NodeIR。"""
    return NodeIR(
        node_guid=guid,
        node_class=node_class,
        node_comment=comment,
        pins=pins or [],
        execution_flow=[],
    )


def _make_export(object_class, object_name, graphs=None, properties=None, parent_class=None):
    """构造 ExportIR。"""
    return ExportIR(
        index=0,
        object_name=object_name,
        object_class=object_class,
        serial_size=0,
        outer_index_resolved=None,
        super_index_resolved=None,
        parent_class=parent_class,
        properties=properties or [],
        graphs=graphs or [],
        bulk_data=None,
    )


# ── Golden fixture 结构验证 ──────────────────────────────────────────


def test_event_node_golden_structure():
    """验证 event_node.txt golden fixture 结构。"""
    golden = load_golden("event_node.txt")
    assert 'Class="/Script/BlueprintGraph.K2Node_Event"' in golden
    assert "NodeGuid=ABCD1234567890ABCDEF1234567890AB" in golden
    assert 'NodeComment="Event BeginPlay"' in golden
    assert 'MemberName="ReceiveBeginPlay"' in golden
    assert "bOverrideFunction=True" in golden


def test_function_call_golden_structure():
    """验证 function_call.txt golden fixture 结构。"""
    golden = load_golden("function_call.txt")
    assert 'Class="/Script/BlueprintGraph.K2Node_CallFunction"' in golden
    assert 'MemberName="K2_SetActorLocation"' in golden
    assert "Pin: execute (Exec)" in golden
    assert "Pin: self (Object)" in golden
    assert "LinkedTo=" in golden


def test_branch_golden_structure():
    """验证 branch.txt golden fixture 结构。"""
    golden = load_golden("branch.txt")
    assert 'Class="/Script/BlueprintGraph.K2Node_IfThenElse"' in golden
    assert "Pin: Condition (Bool)" in golden
    assert "Pin: True (Exec)" in golden
    assert "Pin: False (Exec)" in golden


def test_sequence_golden_structure():
    """验证 sequence.txt golden fixture 结构。"""
    golden = load_golden("sequence.txt")
    assert 'Class="/Script/BlueprintGraph.K2Node_Sequence"' in golden
    assert "Pin: then_0 (Exec)" in golden
    assert "Pin: then_1 (Exec)" in golden
    assert "Pin: then_2 (Exec)" in golden


def test_for_loop_golden_structure():
    """验证 for_loop.txt golden fixture 结构。"""
    golden = load_golden("for_loop.txt")
    assert 'Class="/Script/BlueprintGraph.K2Node_ForLoop"' in golden
    assert "Pin: FirstIndex (Int)" in golden
    assert "Pin: LastIndex (Int)" in golden
    assert "Pin: Index (Int)" in golden
    assert "Pin: LoopBody (Exec)" in golden
    assert "Pin: Completed (Exec)" in golden


# ── 渲染器输出验证 ───────────────────────────────────────────────────


def test_event_node_rendering():
    """测试 Event 节点渲染输出包含关键结构字段。"""
    node = _make_node(
        node_class="K2Node_Event",
        guid="abcd1234567890abcdef1234567890ab",
        comment="Event BeginPlay",
        pins=[
            _make_pin("then", "Exec", linked_to=["deadbeef12345678"]),
        ],
    )
    graph = GraphIR(
        graph_guid="",
        graph_name="EventGraph",
        graph_class="EdGraph",
        nodes=[node],
        execution_chains=[],
    )
    export = _make_export(
        object_class="BlueprintGeneratedClass",
        object_name="TestBlueprint_C",
        graphs=[graph],
    )
    ir = _make_ir(exports=[export])

    renderer = BlueprintUERenderer()
    output = renderer.render(ir, RenderOptions())

    assert 'Begin Object Name="K2Node_Event"' in output
    assert "NodeGuid=ABCD1234567890ABCDEF1234567890AB" in output
    assert 'NodeComment="Event BeginPlay"' in output
    assert "Pin: then (Exec)" in output


def test_no_python_repr_in_output():
    """测试输出不包含 Python repr 格式。"""
    # 构建含 StructValue / TextValue / EnumValue 属性的 export
    struct_prop = PropertyIR(
        name="TestStruct",
        type="StructProperty",
        value=StructValue(struct_type="Vector", fields={"X": 1.0, "Y": 2.0, "Z": 3.0}),
        array_index=0,
        guid=None,
    )
    text_prop = PropertyIR(
        name="DisplayName",
        type="TextProperty",
        value=TextValue(namespace="NS", key="KEY", source_string="Hello"),
        array_index=0,
        guid=None,
    )
    enum_prop = PropertyIR(
        name="CollisionType",
        type="EnumProperty",
        value=EnumValue(enum_type="ECollisionChannel", value_name="ECC_WorldStatic"),
        array_index=0,
        guid=None,
    )
    export = _make_export(
        object_class="BlueprintGeneratedClass",
        object_name="Test_C",
        properties=[struct_prop, text_prop, enum_prop],
    )
    ir = _make_ir(exports=[export])

    renderer = BlueprintUERenderer()
    output = renderer.render(ir, RenderOptions())

    # 核心断言：不包含 Python repr
    assert "StructValue(" not in output
    assert "TextValue(" not in output
    assert "EnumValue(" not in output
    assert "Property(" not in output
    assert "<" not in output  # 不应有 <object at 0x...>


def test_struct_value_formatting():
    """测试 StructValue 格式化为 UE 风格。"""
    sv = StructValue(struct_type="Vector", fields={"X": 1.0, "Y": 2.0, "Z": 3.0})
    result = _format_ue_value(sv)
    assert "StructValue" not in result
    assert "X=1.0" in result
    assert "Y=2.0" in result
    assert "Z=3.0" in result


def test_text_value_formatting():
    """测试 TextValue 格式化为 UE 风格。"""
    tv = TextValue(namespace="NS", key="KEY", source_string="Hello World")
    result = _format_ue_value(tv)
    assert "TextValue" not in result
    assert "Hello World" in result


def test_enum_value_formatting():
    """测试 EnumValue 格式化为 UE 风格。"""
    ev = EnumValue(enum_type="ECollisionChannel", value_name="ECC_WorldStatic")
    result = _format_ue_value(ev)
    assert "EnumValue" not in result
    assert "ECollisionChannel" in result
    assert "ECC_WorldStatic" in result


def test_basic_value_formatting():
    """测试基础类型格式化。"""
    assert _format_ue_value(None) == "None"
    assert _format_ue_value(True) == "True"
    assert _format_ue_value(False) == "False"
    assert _format_ue_value(42) == "42"
    assert _format_ue_value(3.14) == "3.14"
    assert _format_ue_value("hello") == "hello"


def test_soft_object_path_formatting():
    """测试 SoftObjectPathValue 格式化。"""
    sv = SoftObjectPathValue(
        raw_kind="SoftObjectPath",
        asset_path="/Game/Blueprints/BP_Test",
        sub_path="",
    )
    result = _format_ue_value(sv)
    assert "SoftObjectPathValue" not in result
    assert "/Game/Blueprints/BP_Test" in result


def test_list_formatting():
    """测试列表格式化为 UE 风格。"""
    result = _format_ue_value([1, 2, 3])
    assert result == "(1,2,3)"


def test_nested_struct_formatting():
    """测试嵌套 StructValue 格式化。"""
    inner = StructValue(struct_type="Vector", fields={"X": 0.0, "Y": 0.0, "Z": 0.0})
    outer = StructValue(struct_type="Transform", fields={"Translation": inner})
    result = _format_ue_value(outer)
    assert "StructValue" not in result
    assert "Translation=" in result
