"""C++ 默认值空输出修复测试。

验证：
- 空值不输出 "= ;"
- 有值正常输出 "= value"
- format_cpp_default_value 和 _format_default_value 均正确处理空值
"""
from __future__ import annotations

import unittest
from typing import List

from uasset_read.cpp_gen.cpp_default_value_formatter import format_cpp_default_value
from uasset_read.cpp_gen.formatters.cpp_header_formatter import (
    _format_default_value,
    _format_variable_property,
)
from uasset_read.cpp_gen.formatters.cpp_json_ir import CppProperty


def _make_variable_property(
    name: str,
    cpp_type: str,
    default_value=None,
    marks: List[str] | None = None,
) -> CppProperty:
    """构建变量 CppProperty 测试对象。"""
    if marks is None:
        marks = ["EditAnywhere", "BlueprintReadWrite"]
    return CppProperty(
        cpp_type=cpp_type,
        name=name,
        uproperty_marks=marks,
        category="variable",
        default_value=default_value,
    )


class TestFormatCppDefaultValueEmpty(unittest.TestCase):
    """测试 format_cpp_default_value 空值处理。"""

    def test_none_returns_empty(self) -> None:
        """None 值应返回空字符串。"""
        self.assertEqual(format_cpp_default_value(None, "float"), "")

    def test_empty_string_returns_empty(self) -> None:
        """空字符串应返回空字符串，不产生输出。"""
        self.assertEqual(format_cpp_default_value("", "FString"), "")
        self.assertEqual(format_cpp_default_value("", "float"), "")
        self.assertEqual(format_cpp_default_value("", "int32"), "")

    def test_whitespace_string_returns_empty(self) -> None:
        """纯空白字符串应返回空字符串。"""
        self.assertEqual(format_cpp_default_value("  ", "FString"), "")
        self.assertEqual(format_cpp_default_value("\t", "FString"), "")
        self.assertEqual(format_cpp_default_value("\n", "FString"), "")

    def test_valid_float_value(self) -> None:
        """有效 float 值应正常格式化。"""
        self.assertEqual(format_cpp_default_value(100.0, "float"), "100.f")
        self.assertEqual(format_cpp_default_value(3.14, "float"), "3.14f")

    def test_valid_bool_value(self) -> None:
        """有效 bool 值应正常格式化。"""
        self.assertEqual(format_cpp_default_value(True, "bool"), "true")
        self.assertEqual(format_cpp_default_value(False, "bool"), "false")

    def test_valid_int_value(self) -> None:
        """有效 int 值应正常格式化。"""
        self.assertEqual(format_cpp_default_value(42, "int32"), "42")

    def test_valid_string_value(self) -> None:
        """有效字符串值应正常格式化。"""
        self.assertEqual(
            format_cpp_default_value("hello", "FString"),
            'TEXT("hello")',
        )

    def test_valid_enum_value(self) -> None:
        """有效枚举值应正常格式化。"""
        self.assertEqual(
            format_cpp_default_value("FirstPerson", "EFirstPersonPrimitiveType"),
            "FirstPerson",
        )


class TestFormatDefaultValueEmpty(unittest.TestCase):
    """测试 cpp_header_formatter._format_default_value 空值处理。"""

    def test_none_returns_empty(self) -> None:
        self.assertEqual(_format_default_value("float", None), "")

    def test_empty_string_returns_empty(self) -> None:
        self.assertEqual(_format_default_value("FString", ""), "")

    def test_whitespace_string_returns_empty(self) -> None:
        self.assertEqual(_format_default_value("FString", "   "), "")

    def test_valid_float(self) -> None:
        self.assertEqual(_format_default_value("float", 100.0), "100.0f")

    def test_valid_bool(self) -> None:
        self.assertEqual(_format_default_value("bool", True), "true")

    def test_valid_int(self) -> None:
        self.assertEqual(_format_default_value("int32", 42), "42")


class TestVariablePropertyNoEmptyDefault(unittest.TestCase):
    """测试 _format_variable_property 不产生 '= ;' 输出。"""

    def test_none_default_no_equals(self) -> None:
        """None 默认值不应输出 '= ;'。"""
        prop = _make_variable_property("Speed", "float", default_value=None)
        lines = _format_variable_property(prop)
        decl_line = lines[-1]
        self.assertNotIn("= ;", decl_line)
        self.assertNotIn("= ", decl_line)
        self.assertTrue(decl_line.strip().endswith(";"))

    def test_empty_string_default_no_equals(self) -> None:
        """空字符串默认值不应输出 '= ;'。"""
        prop = _make_variable_property("Name", "FString", default_value="")
        lines = _format_variable_property(prop)
        decl_line = lines[-1]
        self.assertNotIn("= ;", decl_line)
        self.assertNotIn("= ", decl_line)

    def test_whitespace_default_no_equals(self) -> None:
        """纯空白默认值不应输出 '= ;'。"""
        prop = _make_variable_property("Name", "FString", default_value="   ")
        lines = _format_variable_property(prop)
        decl_line = lines[-1]
        self.assertNotIn("= ;", decl_line)

    def test_valid_default_has_equals(self) -> None:
        """有效默认值应正常输出 '= value'。"""
        prop = _make_variable_property("Speed", "float", default_value=100.0)
        lines = _format_variable_property(prop)
        decl_line = lines[-1]
        self.assertIn("= 100.0f", decl_line)
        self.assertTrue(decl_line.strip().endswith(";"))

    def test_valid_bool_default_has_equals(self) -> None:
        """有效 bool 默认值应正常输出。"""
        prop = _make_variable_property("bActive", "bool", default_value=True)
        lines = _format_variable_property(prop)
        decl_line = lines[-1]
        self.assertIn("= true", decl_line)

    def test_valid_int_default_has_equals(self) -> None:
        """有效 int 默认值应正常输出。"""
        prop = _make_variable_property("Count", "int32", default_value=42)
        lines = _format_variable_property(prop)
        decl_line = lines[-1]
        self.assertIn("= 42", decl_line)


if __name__ == "__main__":
    unittest.main()
