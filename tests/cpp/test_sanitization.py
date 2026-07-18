"""
C++ sanitizer 模块单元测试。

覆盖 sanitize_string_literal、sanitize_uproperty_marks、
sanitize_category 三个函数。
sanitize_identifier 测试已移至 tests/cpp/test_cpp_sanitizer.py。
"""

import pytest
from uasset_read.cpp_gen.sanitizer import (
    sanitize_string_literal,
    sanitize_uproperty_marks,
    sanitize_category,
)
from uasset_read.cpp_gen.math_simplifier import MathSimplifier


# ============================================================================
# sanitize_string_literal 测试
# ============================================================================


class TestSanitizeStringLiteral:
    """sanitize_string_literal 函数测试。"""

    def test_plain_string(self):
        """普通字符串不变。"""
        assert sanitize_string_literal("Hello World") == "Hello World"

    def test_escape_backslash(self):
        """反斜杠转义。"""
        assert sanitize_string_literal("C:\\path") == "C:\\\\path"

    def test_escape_double_quote(self):
        """双引号转义。"""
        assert sanitize_string_literal('Hello "World"') == 'Hello \\"World\\"'

    def test_escape_newline(self):
        """换行符转义。"""
        assert sanitize_string_literal("line1\nline2") == "line1\\nline2"

    def test_escape_carriage_return(self):
        """回车符转义。"""
        assert sanitize_string_literal("cr\rhere") == "cr\\rhere"

    def test_escape_tab(self):
        """制表符转义。"""
        assert sanitize_string_literal("tab\there") == "tab\\there"

    def test_none_returns_empty(self):
        """None 返回空字符串。"""
        assert sanitize_string_literal(None) == ""

    def test_empty_string(self):
        """空字符串不变。"""
        assert sanitize_string_literal("") == ""

    def test_combined_escapes(self):
        """混合转义场景。"""
        assert sanitize_string_literal('path\\to"file"') == 'path\\\\to\\"file\\"'

    def test_backslash_before_quote(self):
        """反斜杠在引号前——反斜杠先转义。"""
        # 输入: a\"b → a\\\"b
        assert sanitize_string_literal('a\\"b') == 'a\\\\\\"b'


# ============================================================================
# sanitize_uproperty_marks 测试
# ============================================================================


class TestSanitizeUpropertyMarks:
    """sanitize_uproperty_marks 函数测试。"""

    def test_valid_marks(self):
        """合法 specifier 保留。"""
        result = sanitize_uproperty_marks(["EditAnywhere", "BlueprintReadWrite"])
        assert result == ["EditAnywhere", "BlueprintReadWrite"]

    def test_filters_invalid_marks(self):
        """非法 specifier 被过滤。"""
        result = sanitize_uproperty_marks(["EditAnywhere", "INJECTED_CODE", "Transient"])
        assert result == ["EditAnywhere", "Transient"]

    def test_none_returns_empty(self):
        """None 返回空列表。"""
        assert sanitize_uproperty_marks(None) == []

    def test_empty_list(self):
        """空列表返回空列表。"""
        assert sanitize_uproperty_marks([]) == []

    def test_deduplication(self):
        """重复 specifier 去重。"""
        result = sanitize_uproperty_marks(["EditAnywhere", "EditAnywhere"])
        assert result == ["EditAnywhere"]

    def test_all_whitelist_specifiers(self):
        """白名单中所有 specifier 都通过。"""
        marks = [
            "EditAnywhere", "EditInstanceOnly", "EditDefaultsOnly",
            "VisibleAnywhere", "VisibleInstanceOnly", "VisibleDefaultsOnly",
            "BlueprintReadWrite", "BlueprintReadOnly", "BlueprintCallable",
            "BlueprintAssignable", "BlueprintPure", "BlueprintType",
            "Transient", "Config", "SaveGame", "Replicated",
            "DuplicateTransient", "Instanced", "NoClear", "Interp",
            "ExposeOnSpawn", "AllowPrivateAccess", "Deprecated",
            "AdvancedDisplay", "Protected",
        ]
        result = sanitize_uproperty_marks(marks)
        assert result == marks

    def test_empty_string_mark(self):
        """空字符串标记被过滤。"""
        assert sanitize_uproperty_marks(["", "EditAnywhere"]) == ["EditAnywhere"]

    def test_non_string_mark(self):
        """非字符串标记被过滤。"""
        assert sanitize_uproperty_marks([123, "EditAnywhere"]) == ["EditAnywhere"]

    def test_case_sensitive(self):
        """大小写敏感——小写变体不通过。"""
        assert sanitize_uproperty_marks(["editanywhere"]) == []
        assert sanitize_uproperty_marks(["EDITANYWHERE"]) == []


# ============================================================================
# sanitize_category 测试
# ============================================================================


class TestSanitizeCategory:
    """sanitize_category 函数测试。"""

    def test_valid_category(self):
        """合法 Category 不变。"""
        assert sanitize_category("My Category") == "My Category"

    def test_remove_double_quotes(self):
        """移除双引号。"""
        assert sanitize_category('My "Category"') == "My Category"

    def test_remove_single_quotes(self):
        """移除单引号。"""
        assert sanitize_category("My 'Category'") == "My Category"

    def test_remove_backslash(self):
        """移除反斜杠。"""
        assert sanitize_category("C:\\path/to") == "Cpathto"

    def test_remove_newline(self):
        """移除换行符。"""
        assert sanitize_category("line\nbreak") == "linebreak"

    def test_remove_carriage_return(self):
        """移除回车符。"""
        assert sanitize_category("line\rbreak") == "linebreak"

    def test_tab_to_space(self):
        """制表符转空格。"""
        assert sanitize_category("my\tcategory") == "my category"

    def test_empty_returns_empty(self):
        """空字符串返回空。"""
        assert sanitize_category("") == ""

    def test_none_returns_empty(self):
        """None 返回空字符串。"""
        assert sanitize_category(None) == ""

    def test_trim_whitespace(self):
        """去除首尾空格。"""
        assert sanitize_category("  Trimmed  ") == "Trimmed"

    def test_compress_spaces(self):
        """压缩连续空格。"""
        assert sanitize_category("My  Big  Category") == "My Big Category"

    def test_preserve_underscore(self):
        """保留下划线。"""
        assert sanitize_category("Valid_Category 123") == "Valid_Category 123"

    def test_remove_special_chars(self):
        """移除特殊字符。"""
        assert sanitize_category("My!@#$%Category") == "MyCategory"

    def test_injection_attempt(self):
        """注入攻击被清除。"""
        assert sanitize_category('"); // INJECTED') == "INJECTED"

    def test_null_bytes(self):
        """null 字节被移除。"""
        assert sanitize_category("abc\0def") == "abcdef"


# ============================================================================
# MathSimplifier 测试（合并自 test_math_simplifier.py）
# ============================================================================


class TestMathSimplifier:
    """蓝图数学函数简化器单元测试。"""

    def test_add_int_simplification(self):
        """测试 Int 加法简化"""
        simplifier = MathSimplifier()
        result = simplifier.simplify("Add_IntInt")
        assert result == "+"

    def test_multiply_float_simplification(self):
        """测试 Float 乘法简化"""
        simplifier = MathSimplifier()
        result = simplifier.simplify("Multiply_FloatFloat")
        assert result == "*"

    def test_boolean_and_simplification(self):
        """测试布尔与简化"""
        simplifier = MathSimplifier()
        result = simplifier.simplify("BooleanAND")
        assert result == "&&"

    def test_is_math_library_function(self):
        """测试判断是否为数学库函数"""
        simplifier = MathSimplifier()
        assert simplifier.is_math_library_function("Add_IntInt") is True
        assert simplifier.is_math_library_function("UnknownFunction") is False

    def test_get_operator_info(self):
        """测试获取运算符信息"""
        simplifier = MathSimplifier()
        info = simplifier.get_operator_info("Add_IntInt")
        assert info["type"] == "arithmetic"
        assert info["operator"] == "+"

    def test_simplify_unknown_function(self):
        """测试简化未知函数返回 None"""
        simplifier = MathSimplifier()
        result = simplifier.simplify("UnknownFunction")
        assert result is None

    def test_simplify_without_type_suffix(self):
        """测试不带类型后缀的简化"""
        simplifier = MathSimplifier()
        # 测试直接匹配（不带类型后缀的函数）
        result = simplifier.simplify("Sin")
        assert result == "FMath::Sin"

    def test_get_operator_info_unknown(self):
        """测试获取未知函数的运算符信息返回 None"""
        simplifier = MathSimplifier()
        info = simplifier.get_operator_info("UnknownFunction")
        assert info is None

    def test_comparison_operator(self):
        """测试比较运算符"""
        simplifier = MathSimplifier()
        result = simplifier.simplify("Greater_FloatFloat")
        assert result == ">"
        info = simplifier.get_operator_info("Greater_FloatFloat")
        assert info["type"] == "comparison"

    def test_logical_operator(self):
        """测试逻辑运算符"""
        simplifier = MathSimplifier()
        result = simplifier.simplify("BooleanOR")
        assert result == "||"
        info = simplifier.get_operator_info("BooleanOR")
        assert info["type"] == "logical"

    def test_math_function(self):
        """测试数学函数保持函数形式"""
        simplifier = MathSimplifier()
        result = simplifier.simplify("Sqrt")
        assert result == "FMath::Sqrt"
        info = simplifier.get_operator_info("Sqrt")
        assert info["type"] == "function"
