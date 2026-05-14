"""
tests/test_phase35d_model_class_fixes.py - 模型类修复测试（Phase 35d-03）

测试 CR-13：StructValue/MapValue/SetValue 等子类缺少默认 property_type。

测试内容：
- 各子类不传 property_type 时自动使用正确的默认值
- 向后兼容：传 property_type 时行为不变
"""
import pytest
from dataclasses import dataclass

from uasset_read.models.properties import (
    AdvancedPropertyValue,
    StructValue,
    MapValue,
    SetValue,
    EnumValue,
    TextValue,
    DelegateValue,
)


class TestDefaultPropertyType:
    """CR-13: Value 子类自动获取默认 property_type 值。"""

    def test_struct_value_default_property_type(self):
        """StructValue 不传 property_type 时，默认应为 'StructProperty'。"""
        s = StructValue(struct_type="Vector", fields={"X": 1.0, "Y": 2.0, "Z": 3.0})
        assert s.property_type == "StructProperty"
        assert s.struct_type == "Vector"
        assert s.fields == {"X": 1.0, "Y": 2.0, "Z": 3.0}

    def test_map_value_default_property_type(self):
        """MapValue 不传 property_type 时，默认应为 'MapProperty'。"""
        m = MapValue(key_type="Name", value_type="IntProperty", entries=[])
        assert m.property_type == "MapProperty"
        assert m.key_type == "Name"
        assert m.value_type == "IntProperty"

    def test_set_value_default_property_type(self):
        """SetValue 不传 property_type 时，默认应为 'SetProperty'。"""
        s = SetValue(element_type="Name", elements=[])
        assert s.property_type == "SetProperty"
        assert s.element_type == "Name"

    def test_enum_value_default_property_type(self):
        """EnumValue 不传 property_type 时，默认应为 'EnumProperty'。"""
        e = EnumValue(enum_type="SomeEnum", value_name="SomeEnum::Value")
        assert e.property_type == "EnumProperty"
        assert e.enum_type == "SomeEnum"
        assert e.value_name == "SomeEnum::Value"

    def test_text_value_default_property_type(self):
        """TextValue 不传 property_type 时，默认应为 'TextProperty'。"""
        t = TextValue(namespace="NS", key="K", source_string="S")
        assert t.property_type == "TextProperty"
        assert t.namespace == "NS"

    def test_delegate_value_default_property_type(self):
        """DelegateValue 不传 property_type 时，默认应为 'DelegateProperty'。"""
        d = DelegateValue(object_ref=123, function_name="SomeFunc")
        assert d.property_type == "DelegateProperty"
        assert d.object_ref == 123
        assert d.function_name == "SomeFunc"

    def test_struct_value_backward_compatible_with_explicit_property_type(self):
        """StructValue 仍然接受显式传入 property_type（向后兼容）。"""
        s = StructValue(
            property_type="StructProperty",
            struct_type="Rotator",
            fields={"Roll": 0.0, "Pitch": 0.0, "Yaw": 90.0},
        )
        assert s.property_type == "StructProperty"
        assert s.struct_type == "Rotator"

    def test_map_value_backward_compatible(self):
        """MapValue 仍然接受显式传入 property_type。"""
        m = MapValue(
            property_type="MapProperty",
            key_type="IntProperty",
            value_type="Name",
            entries=[],
        )
        assert m.property_type == "MapProperty"

    def test_set_value_backward_compatible(self):
        """SetValue 仍然接受显式传入 property_type。"""
        s = SetValue(
            property_type="SetProperty",
            element_type="IntProperty",
            elements=[],
        )
        assert s.property_type == "SetProperty"

    def test_enum_value_backward_compatible(self):
        """EnumValue 仍然接受显式传入 property_type。"""
        e = EnumValue(
            property_type="EnumProperty",
            enum_type="TestEnum",
            value_name="TestEnum::A",
        )
        assert e.property_type == "EnumProperty"

    def test_text_value_backward_compatible(self):
        """TextValue 仍然接受显式传入 property_type。"""
        t = TextValue(
            property_type="TextProperty",
            namespace="NS",
            key="K",
            source_string="S",
        )
        assert t.property_type == "TextProperty"

    def test_delegate_value_backward_compatible(self):
        """DelegateValue 仍然接受显式传入 property_type。"""
        d = DelegateValue(
            property_type="DelegateProperty",
            object_ref=456,
            function_name="OtherFunc",
        )
        assert d.property_type == "DelegateProperty"

    def test_struct_value_default_fields_preserved(self):
        """StructValue 的 fields 默认为空字典。"""
        s = StructValue(struct_type="Vector")
        assert s.fields == {}

    def test_map_value_default_entries_preserved(self):
        """MapValue 的 entries 默认为空列表。"""
        m = MapValue(key_type="Name", value_type="StrProperty")
        assert m.entries == []

    def test_set_value_default_elements_preserved(self):
        """SetValue 的 elements 默认为空列表。"""
        s = SetValue(element_type="IntProperty")
        assert s.elements == []

    def test_text_value_default_strings_preserved(self):
        """TextValue 的 namespace/key/source_string 默认空字符串。"""
        t = TextValue()
        assert t.property_type == "TextProperty"
        assert t.namespace == ""
        assert t.key == ""
        assert t.source_string == ""

    def test_all_value_types_are_advanced_property_value_instances(self):
        """所有 Value 类型均为 AdvancedPropertyValue 的实例。"""
        assert isinstance(StructValue(struct_type="V"), AdvancedPropertyValue)
        assert isinstance(MapValue(key_type="K", value_type="V"), AdvancedPropertyValue)
        assert isinstance(SetValue(element_type="E"), AdvancedPropertyValue)
        assert isinstance(EnumValue(enum_type="E", value_name="E::V"), AdvancedPropertyValue)
        assert isinstance(TextValue(), AdvancedPropertyValue)
        assert isinstance(DelegateValue(object_ref=0, function_name="F"), AdvancedPropertyValue)
