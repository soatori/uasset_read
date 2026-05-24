"""Phase 72-H: StructValue JSON 递归序列化修复 + FString/LinkedTo 相关测试。"""
import json
import pytest

from uasset_read.formatters.json_formatter import serialize_property_value
from uasset_read.models.properties import StructValue, MapValue, SetValue, EnumValue, TextValue, DelegateValue


class TestSerializePropertyValue:
    """测试 serialize_property_value 对嵌套 dataclass 的递归序列化。"""

    def test_simple_struct_value(self):
        """单层 StructValue 序列化。"""
        sv = StructValue(struct_type="Vector", fields={"X": 1.0, "Y": 2.0, "Z": 3.0})
        result = serialize_property_value(sv)
        assert result["struct_type"] == "Vector"
        assert result["fields"]["X"] == 1.0

    def test_nested_struct_value(self):
        """嵌套 2 层 StructValue：fields 内的值仍是 StructValue。"""
        inner = StructValue(struct_type="Vector", fields={"X": 0.0, "Y": 0.0, "Z": 0.0})
        outer = StructValue(struct_type="Transform", fields={"Translation": inner, "Scale": 1.0})
        result = serialize_property_value(outer)
        # 关键验证：inner StructValue 被递归序列化，不是 dataclass 对象
        assert isinstance(result["fields"]["Translation"], dict)
        assert result["fields"]["Translation"]["struct_type"] == "Vector"
        assert result["fields"]["Translation"]["fields"]["X"] == 0.0

    def test_deeply_nested_struct_value(self):
        """嵌套 3 层以上 StructValue。"""
        level3 = StructValue(struct_type="Vector", fields={"X": 1.0, "Y": 2.0, "Z": 3.0})
        level2 = StructValue(struct_type="Transform", fields={"Location": level3})
        level1 = StructValue(struct_type="Component", fields={"RelativeTransform": level2})
        result = serialize_property_value(level1)
        # 验证 3 层嵌套都能序列化
        assert result["fields"]["RelativeTransform"]["fields"]["Location"]["fields"]["X"] == 1.0

    def test_dict_with_dataclass_values(self):
        """普通 dict 中包含 dataclass 值，应递归处理。"""
        sv = StructValue(struct_type="Rotator", fields={"Pitch": 45.0, "Yaw": 0.0, "Roll": 0.0})
        data = {"rotation": sv, "other": "value"}
        result = serialize_property_value(data)
        assert isinstance(result["rotation"], dict)
        assert result["rotation"]["struct_type"] == "Rotator"

    def test_list_with_dataclass_items(self):
        """list 中包含 dataclass 元素，应递归处理。"""
        sv1 = StructValue(struct_type="Vector", fields={"X": 1.0})
        sv2 = StructValue(struct_type="Vector", fields={"X": 2.0})
        data = [sv1, sv2, "plain"]
        result = serialize_property_value(data)
        assert isinstance(result[0], dict)
        assert result[0]["struct_type"] == "Vector"
        assert result[2] == "plain"

    def test_map_value_with_nested_struct(self):
        """MapValue entries 中包含 StructValue。"""
        sv = StructValue(struct_type="Vector", fields={"X": 0.0})
        mv = MapValue(key_type="Name", value_type="Struct", entries=[{"key": "Offset", "value": sv}])
        result = serialize_property_value(mv)
        assert isinstance(result["entries"][0]["value"], dict)
        assert result["entries"][0]["value"]["struct_type"] == "Vector"

    def test_set_value_with_nested_struct(self):
        """SetValue elements 中包含 StructValue。"""
        sv = StructValue(struct_type="Vector", fields={"X": 1.0})
        sv_set = SetValue(element_type="Struct", elements=[sv])
        result = serialize_property_value(sv_set)
        assert isinstance(result["elements"][0], dict)

    def test_enum_value(self):
        """EnumValue 序列化。"""
        ev = EnumValue(enum_type="ECollisionEnabled", value_name="QueryAndPhysics")
        result = serialize_property_value(ev)
        assert result["enum_type"] == "ECollisionEnabled"
        assert result["value"] == "QueryAndPhysics"

    def test_text_value(self):
        """TextValue 序列化。"""
        tv = TextValue(namespace="MyGame", key="DisplayName", source_string="Hello")
        result = serialize_property_value(tv)
        assert result["source_string"] == "Hello"

    def test_delegate_value(self):
        """DelegateValue 序列化。"""
        dv = DelegateValue(object_ref="Self", function_name="OnClicked")
        result = serialize_property_value(dv)
        assert result["function_name"] == "OnClicked"

    def test_json_dumps_no_error(self):
        """完整嵌套结构可被 json.dumps 序列化，不抛 TypeError。"""
        inner = StructValue(struct_type="Vector", fields={"X": 1.0, "Y": 2.0, "Z": 3.0})
        outer = StructValue(struct_type="Transform", fields={"Location": inner})
        result = serialize_property_value(outer)
        # 这行不应抛 TypeError: Object of type StructValue is not JSON serializable
        json_str = json.dumps(result)
        assert "Vector" in json_str

    def test_dataclass_fallback_recursive(self):
        """未知 dataclass 通过 asdict + 递归正确序列化。"""
        from dataclasses import dataclass

        @dataclass
        class CustomData:
            name: str
            nested: StructValue

        custom = CustomData(name="test", nested=StructValue(struct_type="Test", fields={"a": 1}))
        result = serialize_property_value(custom)
        assert result["name"] == "test"
        assert isinstance(result["nested"], dict)
        assert result["nested"]["struct_type"] == "Test"

    def test_max_depth_truncation(self):
        """超过 max_depth 返回截断标记。"""
        result = serialize_property_value({"a": {"b": {"c": 1}}}, depth=0, max_depth=1)
        # depth=0 → dict → recurse depth=1
        # depth=1 → dict → recurse depth=2 > max_depth=1 → truncated
        assert result["a"]["b"] == "[deep nesting truncated]"

    def test_primitive_types_passthrough(self):
        """原始类型直接返回。"""
        assert serialize_property_value(None) is None
        assert serialize_property_value("hello") == "hello"
        assert serialize_property_value(42) == 42
        assert serialize_property_value(3.14) == 3.14
        assert serialize_property_value(True) is True
