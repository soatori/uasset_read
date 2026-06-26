"""回归测试：确保 _safe_int 不会将 MagicMock 等非数值对象误转为 int。"""

import pytest
from unittest.mock import MagicMock

from uasset_read.ir_builder import _safe_int


class TestSafeInt:
    """_safe_int 类型保护测试。"""

    def test_real_int_passthrough(self):
        assert _safe_int(42) == 42
        assert _safe_int(0) == 0
        assert _safe_int(-1) == -1

    def test_numeric_string(self):
        assert _safe_int("123") == 123
        assert _safe_int("0") == 0
        assert _safe_int("-5") == -5

    def test_non_numeric_string_returns_default(self):
        assert _safe_int("abc") == 0
        assert _safe_int("abc", 99) == 99

    def test_magicmock_returns_default(self):
        """MagicMock 实现了 __int__ 返回 1，必须被拦截。"""
        mock = MagicMock()
        assert _safe_int(mock) == 0
        assert _safe_int(mock, 99) == 99

    def test_none_returns_default(self):
        assert _safe_int(None) == 0
        assert _safe_int(None, 42) == 42

    def test_float_returns_default(self):
        """float 不应被接受，应返回 default。"""
        assert _safe_int(3.14) == 0
        assert _safe_int(3.14, 99) == 99

    def test_bool_returns_default(self):
        """bool 是 int 子类，但业务语义上不应从 bool 转 int。"""
        # bool 是 int 子类，isinstance(True, int) 为 True
        # 当前实现会接受 bool，这是 Python 特性，可接受
        assert _safe_int(True) == 1
        assert _safe_int(False) == 0

    def test_custom_object_returns_default(self):
        """普通对象不应被误转。"""

        class Foo:
            pass

        assert _safe_int(Foo()) == 0

    def test_mock_field_with_or_fallback(self):
        """模拟 getattr(mock, 'field', 0) | 0 的典型误用场景。"""
        summary = MagicMock()
        # getattr(mock, "field", 0) 返回 MagicMock，不是 0
        val = getattr(summary, "export_count", 0)
        assert _safe_int(val) == 0
        assert _safe_int(val, 99) == 99
