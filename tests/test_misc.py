"""Misc 模块合并测试。

覆盖 HexView 调试系统：
1. HexViewEntry 数据类
"""
from __future__ import annotations

import pytest

from uasset_read.debug.hex_view import HexViewEntry, format_hex_view


# ---------------------------------------------------------------------------
# 1. HexViewEntry 数据类
# ---------------------------------------------------------------------------

class TestHexViewEntry:
    def test_basic_creation(self):
        """基本字段赋值。"""
        entry = HexViewEntry(
            key="test", type="int", value=42, start=0, stop=4
        )
        assert entry.key == "test"
        assert entry.value == 42

    def test_format_hex_view_basic(self):
        """format_hex_view 应返回格式化字符串。"""
        entries = [
            HexViewEntry(key="Header", type="int", value=1, start=0, stop=4),
            HexViewEntry(key="Version", type="int", value=522, start=4, stop=6),
        ]
        result = format_hex_view(entries)
        assert "Header" in result
        assert "Version" in result
