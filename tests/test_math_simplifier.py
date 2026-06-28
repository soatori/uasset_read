"""蓝图数学函数简化器单元测试。"""
import pytest
from uasset_read.cpp_gen.math_simplifier import MathSimplifier


def test_add_int_simplification():
    """测试 Int 加法简化"""
    simplifier = MathSimplifier()
    result = simplifier.simplify("Add_IntInt")
    assert result == "+"


def test_multiply_float_simplification():
    """测试 Float 乘法简化"""
    simplifier = MathSimplifier()
    result = simplifier.simplify("Multiply_FloatFloat")
    assert result == "*"


def test_boolean_and_simplification():
    """测试布尔与简化"""
    simplifier = MathSimplifier()
    result = simplifier.simplify("BooleanAND")
    assert result == "&&"


def test_is_math_library_function():
    """测试判断是否为数学库函数"""
    simplifier = MathSimplifier()
    assert simplifier.is_math_library_function("Add_IntInt") is True
    assert simplifier.is_math_library_function("UnknownFunction") is False


def test_get_operator_info():
    """测试获取运算符信息"""
    simplifier = MathSimplifier()
    info = simplifier.get_operator_info("Add_IntInt")
    assert info["type"] == "arithmetic"
    assert info["operator"] == "+"


def test_simplify_unknown_function():
    """测试简化未知函数返回 None"""
    simplifier = MathSimplifier()
    result = simplifier.simplify("UnknownFunction")
    assert result is None


def test_simplify_without_type_suffix():
    """测试不带类型后缀的简化"""
    simplifier = MathSimplifier()
    # 测试直接匹配（不带类型后缀的函数）
    result = simplifier.simplify("Sin")
    assert result == "FMath::Sin"


def test_get_operator_info_unknown():
    """测试获取未知函数的运算符信息返回 None"""
    simplifier = MathSimplifier()
    info = simplifier.get_operator_info("UnknownFunction")
    assert info is None


def test_comparison_operator():
    """测试比较运算符"""
    simplifier = MathSimplifier()
    result = simplifier.simplify("Greater_FloatFloat")
    assert result == ">"
    info = simplifier.get_operator_info("Greater_FloatFloat")
    assert info["type"] == "comparison"


def test_logical_operator():
    """测试逻辑运算符"""
    simplifier = MathSimplifier()
    result = simplifier.simplify("BooleanOR")
    assert result == "||"
    info = simplifier.get_operator_info("BooleanOR")
    assert info["type"] == "logical"


def test_math_function():
    """测试数学函数保持函数形式"""
    simplifier = MathSimplifier()
    result = simplifier.simplify("Sqrt")
    assert result == "FMath::Sqrt"
    info = simplifier.get_operator_info("Sqrt")
    assert info["type"] == "function"