"""
C++ 标识符清理器单元测试。

测试 sanitize_identifier 的各种边界情况。
"""
import pytest

from uasset_read.cpp_gen.sanitizer import sanitize_identifier


class TestSanitizeIdentifier:
    """sanitize_identifier 函数测试。"""

    # === 验收用例（需求文档明确要求） ===

    def test_spaces_to_underscores(self):
        """空格 → 下划线"""
        assert sanitize_identifier("Target Touch UI") == "Target_Touch_UI"

    def test_special_chars_removed(self):
        """特殊字符被移除"""
        assert sanitize_identifier("MyVar@#$") == "MyVar"

    def test_digit_prefix(self):
        """数字开头 → 前缀 _"""
        assert sanitize_identifier("123Var") == "_123Var"

    def test_empty_string(self):
        """空字符串 → _unnamed"""
        assert sanitize_identifier("") == "_unnamed"

    # === 空格处理 ===

    def test_single_space(self):
        assert sanitize_identifier("My Var") == "My_Var"

    def test_multiple_spaces(self):
        assert sanitize_identifier("A B C D") == "A_B_C_D"

    def test_leading_space(self):
        assert sanitize_identifier(" LeadingSpace") == "_LeadingSpace"

    def test_trailing_space(self):
        assert sanitize_identifier("TrailingSpace ") == "TrailingSpace_"

    def test_only_spaces(self):
        """全是空格 → 全是下划线"""
        assert sanitize_identifier("   ") == "___"

    # === 特殊字符处理 ===

    def test_slash_removed(self):
        """斜杠被移除"""
        assert sanitize_identifier("Left / Right") == "Left__Right"

    def test_at_sign_removed(self):
        assert sanitize_identifier("var@name") == "varname"

    def test_hash_removed(self):
        assert sanitize_identifier("my#var") == "myvar"

    def test_dollar_sign_removed(self):
        assert sanitize_identifier("$price") == "price"

    def test_dot_removed(self):
        assert sanitize_identifier("obj.property") == "objproperty"

    def test_hyphen_removed(self):
        assert sanitize_identifier("my-var") == "myvar"

    def test_parentheses_removed(self):
        assert sanitize_identifier("func(arg)") == "funcarg"

    def test_brackets_removed(self):
        assert sanitize_identifier("arr[0]") == "arr0"

    def test_multiple_special_chars(self):
        assert sanitize_identifier("var!@#$%^&*()") == "var"

    # === 数字开头 ===

    def test_pure_digits(self):
        assert sanitize_identifier("123") == "_123"

    def test_single_digit(self):
        assert sanitize_identifier("0") == "_0"

    def test_digit_then_letter(self):
        assert sanitize_identifier("2DValue") == "_2DValue"

    # === 已经合法的标识符 ===

    def test_valid_identifier(self):
        assert sanitize_identifier("ValidName") == "ValidName"

    def test_valid_with_underscore(self):
        assert sanitize_identifier("_valid") == "_valid"

    def test_valid_with_digits(self):
        assert sanitize_identifier("var123") == "var123"

    def test_valid_mixed(self):
        assert sanitize_identifier("_MyVar_123") == "_MyVar_123"

    # === 边界情况 ===

    def test_none_like_empty(self):
        """空字符串等价于 None"""
        assert sanitize_identifier("") == "_unnamed"

    def test_only_special_chars(self):
        """全是特殊字符 → _unnamed"""
        assert sanitize_identifier("@#$%") == "_unnamed"

    def test_only_special_chars_with_space(self):
        """特殊字符+空格 → 下划线"""
        assert sanitize_identifier("! @") == "_"

    def test_unicode_removed(self):
        """Unicode 字符被移除"""
        assert sanitize_identifier("变量名") == "_unnamed"

    def test_mixed_unicode_and_ascii(self):
        assert sanitize_identifier("My变量Name") == "MyName"

    # === 常见 UE 蓝图名称 ===

    def test_primary_thumbstick(self):
        """UE 常见的摇杆输入名"""
        assert sanitize_identifier("Primary Thumbstick") == "Primary_Thumbstick"

    def test_move_forward(self):
        assert sanitize_identifier("Move Forward") == "Move_Forward"

    def test_target_touch_ui(self):
        """原始 bug 报告的用例"""
        assert sanitize_identifier("Target Touch UI") == "Target_Touch_UI"

    def test_camera_component_name(self):
        """组件名（通常不含空格，但确保安全）"""
        assert sanitize_identifier("FirstPersonCameraComponent") == "FirstPersonCameraComponent"

    # === 通过 extract_cpp_skeleton 中的 _sanitize_identifier 委托 ===

    def test_delegation_from_extract_cpp_skeleton(self):
        """验证 extract_cpp_skeleton._sanitize_identifier 使用新实现"""
        from uasset_read.cpp_gen.extract_cpp_skeleton import _sanitize_identifier

        assert _sanitize_identifier("Target Touch UI") == "Target_Touch_UI"
        assert _sanitize_identifier("MyVar@#$") == "MyVar"
        assert _sanitize_identifier("123Var") == "_123Var"
        assert _sanitize_identifier("") == "_unnamed"

    # === 通过顶层 __init__ 导出 ===

    def test_exported_from_cpp_gen(self):
        """验证从 cpp_gen 包可导入"""
        from uasset_read.cpp_gen import sanitize_identifier as fn
        assert fn("Test Var") == "Test_Var"

    def test_exported_from_top_level(self):
        """验证从顶层包可导入"""
        from uasset_read import sanitize_identifier as fn
        assert fn("Test Var") == "Test_Var"
