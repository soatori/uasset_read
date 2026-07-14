"""验证 MathFunctionCleaner 对 BlueprintSetLibrary 的语义翻译。

覆盖：
- Set_Difference 输出集合差集（-），而非相等性比较（==）
- 其他 Set 库函数的基本翻译正确性
"""
from __future__ import annotations

from uasset_read.kismet.translator import MathFunctionCleaner


class TestSetDifference:
    """Set_Difference 语义回归测试（Issue #387 残留）。"""

    def test_set_difference_uses_minus_operator(self):
        """Set_Difference 应输出 A - B，而非 A == B。"""
        result = MathFunctionCleaner._clean_set(
            "Set_Difference", ["setA", "setB", "result"]
        )
        assert "-" in result
        assert "==" not in result
        assert result == "result = setA - setB"

    def test_set_difference_no_equality(self):
        """确保 Set_Difference 输出中不包含相等比较符号。"""
        result = MathFunctionCleaner._clean_set(
            "Set_Difference", ["MySet", "OtherSet", "Diff"]
        )
        assert "Diff = MySet - OtherSet" == result


class TestSetCleanTable:
    """其他 Set 库函数的翻译验证。"""

    def test_set_add_items(self):
        result = MathFunctionCleaner._clean_set("Set_AddItems", ["s", "item"])
        assert result == "s.Add(item)"

    def test_set_clear(self):
        result = MathFunctionCleaner._clean_set("Set_Clear", ["s"])
        assert result == "s.Clear()"

    def test_set_is_empty(self):
        result = MathFunctionCleaner._clean_set("Set_IsEmpty", ["s"])
        assert result == "s.Length == 0"

    def test_set_length(self):
        result = MathFunctionCleaner._clean_set("Set_Length", ["s"])
        assert result == "s.Length"

    def test_set_unknown_fallback(self):
        result = MathFunctionCleaner._clean_set("Set_Unknown", ["a", "b"])
        assert result == "BlueprintSetLibrary::Set_Unknown(a, b)"
