"""蓝图通配符类型映射测试。"""
import pytest
from uasset_read.blueprint.variable_extractor import _map_pin_category_to_cpp_type


class TestWildcardTypeMapping:
    """验证通配符 Pin category 正确映射。"""

    def test_wildcard_without_leading_space(self):
        """'wildcard'（无前导空格）应映射到 'Wildcard'。"""
        result = _map_pin_category_to_cpp_type("wildcard")
        assert result == "Wildcard"

    def test_wildcard_with_leading_space(self):
        """' wildcard'（有前导空格）也应映射到 'Wildcard'。"""
        result = _map_pin_category_to_cpp_type(" wildcard")
        assert result == "Wildcard"

    def test_exec_maps_to_void(self):
        """'exec' 映射到 'void'。"""
        result = _map_pin_category_to_cpp_type("exec")
        assert result == "void"

    def test_object_types_still_work(self):
        """对象类型映射不受影响。"""
        result = _map_pin_category_to_cpp_type("object")
        assert result == "UObject*"
