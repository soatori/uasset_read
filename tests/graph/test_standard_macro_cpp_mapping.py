"""标准宏 → C++ 映射表测试。"""
import pytest
from uasset_read.graph.macro_expander import (
    STANDARD_MACROS,
    STANDARD_MACRO_CPP_MAPPING,
)


def test_all_standard_macros_have_mapping():
    """每个 STANDARD_MACROS 条目都应在 STANDARD_MACRO_CPP_MAPPING 中有对应映射。"""
    missing = set(STANDARD_MACROS.keys()) - set(STANDARD_MACRO_CPP_MAPPING.keys())
    assert not missing, f"以下标准宏缺少 C++ 映射: {missing}"


def test_mapping_completeness():
    """每个映射必须包含 cpp_statement 和 cpp_template 键。"""
    for name, mapping in STANDARD_MACRO_CPP_MAPPING.items():
        assert "cpp_statement" in mapping, f"{name} 缺少 cpp_statement"
        assert "cpp_template" in mapping, f"{name} 缺少 cpp_template"


def test_for_loop_mapping():
    """ForLoop 映射应为 for 循环。"""
    m = STANDARD_MACRO_CPP_MAPPING["ForLoop"]
    assert m["cpp_statement"] == "for"
    assert "LoopCounter" in m["cpp_template"]
    assert "FirstIndex" in m["cpp_template"]
    assert "LastIndex" in m["cpp_template"]


def test_while_loop_mapping():
    """WhileLoop 映射应为 while 循环。"""
    m = STANDARD_MACRO_CPP_MAPPING["WhileLoop"]
    assert m["cpp_statement"] == "while"
    assert "Condition" in m["cpp_template"]


def test_foreach_loop_mapping():
    """ForEachLoop 映射应为 range-based for。"""
    m = STANDARD_MACRO_CPP_MAPPING["ForEachLoop"]
    assert m["cpp_statement"] == "for_each"
    assert "ArrayElement" in m["cpp_template"]
    assert "Array" in m["cpp_template"]


def test_branch_mapping():
    """Branch 映射应为 if 语句。"""
    m = STANDARD_MACRO_CPP_MAPPING["Branch"]
    assert m["cpp_statement"] == "if"
    assert "Condition" in m["cpp_template"]


def test_is_valid_mapping():
    """IsValid 映射应为 if 语句。"""
    m = STANDARD_MACRO_CPP_MAPPING["IsValid"]
    assert m["cpp_statement"] == "if"
    assert "IsValid" in m["cpp_template"]


def test_delay_mapping():
    """Delay 映射应为延迟注释。"""
    m = STANDARD_MACRO_CPP_MAPPING["Delay"]
    assert m["cpp_statement"] == "delay"
    assert "Latent" in m["cpp_template"]


def test_switch_mapping():
    """SwitchOnInt 映射应为 switch 语句。"""
    m = STANDARD_MACRO_CPP_MAPPING["SwitchOnInt"]
    assert m["cpp_statement"] == "switch"
    assert "Value" in m["cpp_template"]
