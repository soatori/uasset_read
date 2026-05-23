"""Phase 72g M-03: BPGC 函数提取路径回归测试。"""
import pytest

from uasset_read.blueprint.variable_extractor import (
    _extract_functions_from_bpgc_properties,
    _resolve_property_to_function_name,
)
from uasset_read.models.blueprint import BlueprintFunction
from uasset_read.models.properties import PropertyValue


class TestBPGCFunctionExtraction:
    """测试 BPGC 属性中的函数提取。"""

    def test_bpgc_ubergraph_function_extraction(self):
        """Mock BPGC properties with UbergraphFunction, verify extraction."""
        properties = [
            PropertyValue(
                name="UbergraphFunction",
                type="ObjectProperty",
                value={"object_name": "UbergraphFunction_Move"},
            ),
        ]
        functions = _extract_functions_from_bpgc_properties(properties)

        assert len(functions) == 1
        assert functions[0].name == "UbergraphFunction_Move"
        assert isinstance(functions[0], BlueprintFunction)

    def test_bpgc_function_list_extraction(self):
        """Mock BPGC properties with FunctionList, verify extraction."""
        properties = [
            PropertyValue(
                name="FunctionList",
                type="ArrayProperty",
                value=[
                    {"object_name": "DoMove"},
                    {"object_name": "DoAim"},
                    {"object_name": "JumpStart"},
                ],
            ),
        ]
        functions = _extract_functions_from_bpgc_properties(properties)

        assert len(functions) == 3
        names = {f.name for f in functions}
        assert "DoMove" in names
        assert "DoAim" in names
        assert "JumpStart" in names

    def test_bpgc_null_value_ignored(self):
        """Null/None values are not extracted."""
        properties = [
            PropertyValue(name="UbergraphFunction", type="ObjectProperty", value=None),
            PropertyValue(name="FunctionList", type="ArrayProperty", value=[None]),
        ]
        functions = _extract_functions_from_bpgc_properties(properties)
        assert len(functions) == 0

    def test_bpgc_string_value_path_extraction(self):
        """String values with UE paths extract last component."""
        properties = [
            PropertyValue(
                name="UbergraphFunction",
                type="ObjectProperty",
                value="/Game/FirstPerson/Blueprints/BP_Functions.UbergraphFunction_Move",
            ),
        ]
        functions = _extract_functions_from_bpgc_properties(properties)

        assert len(functions) == 1
        assert functions[0].name == "UbergraphFunction_Move"


class TestResolvePropertyToFunctionName:
    """测试属性值到函数名的解析。"""

    def test_string_value(self):
        assert _resolve_property_to_function_name("TestFunction") == "TestFunction"

    def test_path_string_value(self):
        result = _resolve_property_to_function_name("/Game/Path/To/MyFunction")
        assert result == "MyFunction"

    def test_dict_with_object_name(self):
        result = _resolve_property_to_function_name({"object_name": "FuncA"})
        assert result == "FuncA"

    def test_none_value(self):
        assert _resolve_property_to_function_name(None) is None

    def test_none_string_ignored(self):
        assert _resolve_property_to_function_name("None") is None

    def test_object_with_object_name_attr(self):
        obj = type('Mock', (), {'object_name': 'FuncB'})()
        assert _resolve_property_to_function_name(obj) == "FuncB"
