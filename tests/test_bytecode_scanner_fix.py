"""
测试：裸数字 1509949440 修复验证。

验证两个修复点：
1. bytecode_extractor._PLAUSIBLE_SCRIPT_START_TOKENS 不再包含 0x1D/0x5A/0x5E
2. translator 对可疑 IntConst 输出注释而非裸数字
"""
from __future__ import annotations

import pytest


# ===========================================================================
# Fix 1: _PLAUSIBLE_SCRIPT_START_TOKENS 不含危险 token
# ===========================================================================


class TestPlausibleStartTokens:
    """验证 scanner 起始 token 集合已排除误匹配 token。"""

    def test_removed_tokens_not_in_start_set(self):
        """0x1D (EX_IntConst)、0x5A (EX_WireTracepoint)、0x5E (EX_Tracepoint)
        不应出现在 _PLAUSIBLE_SCRIPT_START_TOKENS 中。"""
        from uasset_read.kismet.bytecode_extractor import _PLAUSIBLE_SCRIPT_START_TOKENS

        assert 0x1D not in _PLAUSIBLE_SCRIPT_START_TOKENS, \
            "0x1D (EX_IntConst) 应已从起始 token 集合中移除"
        assert 0x5A not in _PLAUSIBLE_SCRIPT_START_TOKENS, \
            "0x5A (EX_WireTracepoint) 应已从起始 token 集合中移除"
        assert 0x5E not in _PLAUSIBLE_SCRIPT_START_TOKENS, \
            "0x5E (EX_Tracepoint) 应已从起始 token 集合中移除"

    def test_retained_tokens_present(self):
        """保留的安全起始 token 仍应存在。"""
        from uasset_read.kismet.bytecode_extractor import _PLAUSIBLE_SCRIPT_START_TOKENS

        expected = {0x04, 0x19, 0x1B, 0x1C, 0x46}
        assert expected.issubset(_PLAUSIBLE_SCRIPT_START_TOKENS), \
            f"预期保留的 token {expected} 应全部存在"

    def test_start_token_set_exactly_five(self):
        """起始 token 集合应恰好包含 5 个元素。"""
        from uasset_read.kismet.bytecode_extractor import _PLAUSIBLE_SCRIPT_START_TOKENS

        assert len(_PLAUSIBLE_SCRIPT_START_TOKENS) == 5, \
            f"预期 5 个起始 token，实际 {len(_PLAUSIBLE_SCRIPT_START_TOKENS)} 个"


# ===========================================================================
# Fix 2: translator 对可疑 IntConst 输出安全注释
# ===========================================================================


class TestSuspiciousIntConst:
    """验证 EX_IntConst 翻译器对可疑值的安全网。"""

    def _make_int_const(self, value: int):
        """创建 EX_IntConst 表达式实例。"""
        from uasset_read.kismet.expressions import EX_IntConst
        return EX_IntConst(Value=value)

    def test_suspicious_value_emits_comment(self):
        """0x5A000000 (1509949440) 应输出为可疑注释，而非裸数字。"""
        from uasset_read.kismet.translator import line_cpp

        expr = self._make_int_const(0x5A000000)  # 1509949440
        result = line_cpp(expr)
        assert result.startswith("/* suspicious:"), \
            f"可疑值应输出注释，实际: {result}"
        assert "0x5A000000" in result, \
            f"注释应包含十六进制表示，实际: {result}"

    def test_another_suspicious_value(self):
        """0x1D000000 也应触发安全网。"""
        from uasset_read.kismet.translator import line_cpp

        expr = self._make_int_const(0x1D000000)
        result = line_cpp(expr)
        assert result.startswith("/* suspicious:"), \
            f"可疑值应输出注释，实际: {result}"

    def test_normal_int_const_still_works(self):
        """正常整数常量应保持不变。"""
        from uasset_read.kismet.translator import line_cpp

        for val in [0, 1, 42, -1, 255, 1024, 0xFFFFFF, -0x80000000]:
            expr = self._make_int_const(val)
            result = line_cpp(expr)
            assert result == str(val), \
                f"正常值 {val} 应直接输出为字符串，实际: {result}"

    def test_non_aligned_value_not_suspicious(self):
        """低位非零的大整数不应触发安全网（如 0x5A000001）。"""
        from uasset_read.kismet.translator import line_cpp

        expr = self._make_int_const(0x5A000001)
        result = line_cpp(expr)
        assert result == "1509949441", \
            f"低位非零值不应触发安全网，实际: {result}"

    def test_boundary_below_threshold_not_suspicious(self):
        """值 <= 0xFFFFFF 不应触发安全网。"""
        from uasset_read.kismet.translator import line_cpp

        expr = self._make_int_const(0xFFFFFF)
        result = line_cpp(expr)
        assert result == "16777215", \
            f"边界值 0xFFFFFF 不应触发安全网，实际: {result}"

    def test_aligned_above_threshold_suspicious(self):
        """刚好超过 0xFFFFFF 且低位全零的值应触发安全网。"""
        from uasset_read.kismet.translator import line_cpp

        expr = self._make_int_const(0x01000000)
        result = line_cpp(expr)
        assert result.startswith("/* suspicious:"), \
            f"0x01000000 应触发安全网，实际: {result}"
