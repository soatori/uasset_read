"""Blueprint 变量提取器测试。"""
import pytest
from unittest.mock import MagicMock
from uasset_read.models.properties import StructValue, PropertyValue
from uasset_read.blueprint.variable_extractor import (
    _guid_from_description,
    _extract_pin_type_from_property,
    _extract_functions_from_graphs,
    _extract_functions_from_bpgc_properties,
)


class TestGuidFromDescription:
    """_guid_from_description 各种输入格式处理。"""

    def test_struct_value_guid(self):
        """StructValue(Guid, {A,B,C,D}) 应转换为十六进制字符串。"""
        sv = StructValue(
            struct_type="Guid",
            fields={"A": 0x01020304, "B": 0x05060708, "C": 0x090A0B0C, "D": 0x0D0E0F10}
        )
        result = _guid_from_description(sv)
        # 4个uint32按小端序字节排列
        assert result != "", "StructValue Guid 不应返回空字符串"
        assert "-" in result, "GUID 应包含连字符分隔符"

    def test_struct_value_zero_guid(self):
        """全零 Guid 也应返回有效字符串。"""
        sv = StructValue(struct_type="Guid", fields={"A": 0, "B": 0, "C": 0, "D": 0})
        result = _guid_from_description(sv)
        assert result != "", "全零 Guid 不应返回空字符串"

    def test_dict_binary_or_native_still_works(self):
        """原有 dict + binary_or_native_property 路径应保持兼容。"""
        d = {
            "kind": "binary_or_native_property",
            "raw_data": b'\x00\x01\x02\x03\x04\x05\x06\x07\x08\x09\x0a\x0b\x0c\x0d\x0e\x0f'
        }
        result = _guid_from_description(d)
        assert result == "00010203-0405-0607-0809-0a0b0c0d0e0f"

    def test_bytes_input_still_works(self):
        """原始 bytes 输入应保持兼容。"""
        result = _guid_from_description(b'\xAA\xBB\xCC\xDD' * 4)
        assert result == "aabbccdd-aabb-ccdd-aabb-ccddaabbccdd"

    def test_string_input_passthrough(self):
        """字符串输入应直接返回。"""
        s = "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
        assert _guid_from_description(s) == s

    def test_none_returns_empty(self):
        """None 应返回空字符串。"""
        assert _guid_from_description(None) == ""

    def test_int_returns_empty(self):
        """非预期类型应返回空字符串。"""
        assert _guid_from_description(0) == ""


class TestExtractPinTypeFromProperty:
    """_extract_pin_type_from_property 从 PropertyValue 提取 FEdGraphPinType。"""

    def test_object_property_with_object_class(self):
        """ObjectProperty dict 含 object_class 时应提取为 pin_subcategory。"""
        prop = PropertyValue(
            name="Target Touch UI",
            type="ObjectProperty",
            value={
                "type": "import",
                "object_name": "UI_TouchSimple_C",
                "object_class": "WidgetBlueprintGeneratedClass",
            },
        )
        result = _extract_pin_type_from_property(prop)
        assert result.pin_category == "object"
        assert result.pin_subcategory == "WidgetBlueprintGeneratedClass"

    def test_object_property_with_object_name_fallback(self):
        """ObjectProperty dict 无 object_class 时回退到 object_name。"""
        prop = PropertyValue(
            name="SomeRef",
            type="ObjectProperty",
            value={
                "type": "export",
                "object_name": "MyActor",
            },
        )
        result = _extract_pin_type_from_property(prop)
        assert result.pin_category == "object"
        assert result.pin_subcategory == "MyActor"

    def test_struct_property_with_struct_type(self):
        """StructProperty dict 含 struct_type 时应提取为 pin_subcategory。"""
        prop = PropertyValue(
            name="RelativeLocation",
            type="StructProperty",
            value={
                "kind": "struct_binary_decoded",
                "struct_type": "Vector",
                "fields": {"X": 0.0, "Y": 0.0, "Z": 0.0},
            },
        )
        result = _extract_pin_type_from_property(prop)
        assert result.pin_category == "struct"
        assert result.pin_subcategory == "Vector"

    def test_dict_with_existing_pin_category(self):
        """dict 已含 pin_category/pin_subcategory 时应直接使用。"""
        prop = PropertyValue(
            name="SomePin",
            type="StructProperty",
            value={
                "pin_category": "int",
                "pin_subcategory": "custom_sub",
            },
        )
        result = _extract_pin_type_from_property(prop)
        assert result.pin_category == "int"
        assert result.pin_subcategory == "custom_sub"

    def test_simple_type_mapping(self):
        """非 dict 值应通过 type_mapping 返回标准 pin_category。"""
        prop = PropertyValue(name="Health", type="FloatProperty", value=100.0)
        result = _extract_pin_type_from_property(prop)
        assert result.pin_category == "float"

    def test_bool_property(self):
        """BoolProperty 应返回 pin_category=bool。"""
        prop = PropertyValue(name="bActive", type="BoolProperty", value=True)
        result = _extract_pin_type_from_property(prop)
        assert result.pin_category == "bool"

    def test_unknown_type_fallback(self):
        """未知属性类型应回退到 prop_type 原始名。"""
        prop = PropertyValue(name="Weird", type="CustomProperty", value="x")
        result = _extract_pin_type_from_property(prop)
        assert result.pin_category == "CustomProperty"


def _make_event_node(name="ReceiveBeginPlay", b_override=False):
    """创建 K2Node_Event mock 节点。"""
    node = MagicMock()
    node.class_name = "K2Node_Event"
    node.node_data = {
        "event_reference": MagicMock(member_name=name),
        "b_override_function": b_override,
    }
    node.pins = []
    return node


def _make_function_entry_node(name="MyFunction"):
    """创建 K2Node_FunctionEntry mock 节点。"""
    node = MagicMock()
    node.class_name = "K2Node_FunctionEntry"
    node.node_data = {
        "function_reference": MagicMock(member_name=name),
    }
    node.pins = []
    return node


def _make_graph(nodes):
    """创建包含指定节点的 mock 图。"""
    graph = MagicMock()
    graph.nodes = nodes
    return graph


class TestEventClassification:
    """K2Node_Event 与 K2Node_FunctionEntry 的 is_implemented 区分。"""

    def test_event_node_is_not_implemented(self):
        """K2Node_Event 节点应标记 is_implemented=False。"""
        graph = _make_graph([_make_event_node("ReceiveBeginPlay")])
        funcs = _extract_functions_from_graphs([graph])
        assert len(funcs) == 1
        assert funcs[0].name == "ReceiveBeginPlay"
        assert funcs[0].is_implemented is False

    def test_function_entry_is_implemented(self):
        """K2Node_FunctionEntry 节点应标记 is_implemented=True。"""
        graph = _make_graph([_make_function_entry_node("MyCustomFunc")])
        funcs = _extract_functions_from_graphs([graph])
        assert len(funcs) == 1
        assert funcs[0].name == "MyCustomFunc"
        assert funcs[0].is_implemented is True

    def test_mixed_nodes_classification(self):
        """混合图中事件和函数应正确分类。"""
        graph = _make_graph([
            _make_event_node("ReceiveBeginPlay"),
            _make_function_entry_node("ShouldUseTouchControls"),
        ])
        funcs = _extract_functions_from_graphs([graph])
        by_name = {f.name: f for f in funcs}
        assert by_name["ReceiveBeginPlay"].is_implemented is False
        assert by_name["ShouldUseTouchControls"].is_implemented is True

    def test_override_event_still_not_implemented(self):
        """即使 b_override_function=True，K2Node_Event 仍标记 is_implemented=False。"""
        graph = _make_graph([_make_event_node("ReceiveBeginPlay", b_override=True)])
        funcs = _extract_functions_from_graphs([graph])
        assert funcs[0].is_implemented is False
        assert funcs[0].is_blueprint_event is True

    def test_empty_graphs_returns_empty(self):
        """空图列表应返回空列表。"""
        assert _extract_functions_from_graphs([]) == []
        assert _extract_functions_from_graphs(None) == []


class TestBpgcFunctionClassification:
    """BPGC 属性路径的 is_implemented 区分。"""

    def testUbergraphFunction_not_implemented(self):
        """UbergraphFunction 条目标记 is_implemented=False。"""
        prop = MagicMock()
        prop.name = "UbergraphFunction"
        prop.value = "/Game/Blueprints/BP.BP_C:ReceiveBeginPlay"
        funcs = _extract_functions_from_bpgc_properties([prop])
        assert len(funcs) == 1
        assert funcs[0].name == "ReceiveBeginPlay"
        assert funcs[0].is_implemented is False

    def testFunctionList_is_implemented(self):
        """FunctionList 条目标记 is_implemented=True。"""
        prop = MagicMock()
        prop.name = "FunctionList"
        prop.value = ["/Game/Blueprints/BP.BP_C:MyFunction"]
        funcs = _extract_functions_from_bpgc_properties([prop])
        assert len(funcs) == 1
        assert funcs[0].name == "MyFunction"
        assert funcs[0].is_implemented is True

    def test_mixed_bpgc_properties(self):
        """UbergraphFunction 和 FunctionList 混合时应正确分类。"""
        ubergraph = MagicMock()
        ubergraph.name = "UbergraphFunction"
        ubergraph.value = "/Game/Blueprints/BP.BP_C.ReceiveBeginPlay"
        funclist = MagicMock()
        funclist.name = "FunctionList"
        funclist.value = ["/Game/Blueprints/BP.BP_C.MyFunc"]
        funcs = _extract_functions_from_bpgc_properties([ubergraph, funclist])
        by_name = {f.name: f for f in funcs}
        assert by_name["ReceiveBeginPlay"].is_implemented is False
        assert by_name["MyFunc"].is_implemented is True
