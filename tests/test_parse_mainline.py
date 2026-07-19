"""主链路解析测试 — 合并自 test_core_all.py、test_core_api.py、test_core_config.py。

覆盖：主链路解析、API 调用、配置处理。
"""
from __future__ import annotations

import struct
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from uasset_read.archive import ByteArchive
from uasset_read.core import parse_single
from uasset_read.core.utils import safe_str
from uasset_read.exceptions import ParseError
from uasset_read.parse_uasset import parse_package, parse_uasset_with_linker


# ============================================================================
# 1. 安全字符串基础
# ============================================================================

def test_safe_str_none():
    """None 应返回空字符串。"""
    assert safe_str(None) == ""


# ============================================================================
# 2. UTF-8 长度越界容错
# ============================================================================

def test_utf8_length_exceeds_remaining_bytes_tolerant():
    """UTF-8 长度超过剩余字节时，tolerant 模式应返回空字符串。"""
    data = struct.pack('<i', 1000) + b'\x00' * 10
    archive = ByteArchive(data, tolerant=True)
    result = archive.read_utf8_string(tolerant=True)
    assert result == ""


# ============================================================================
# 3. 模块导入冒烟
# ============================================================================

@pytest.mark.parametrize("module_path", [
    "uasset_read",
    "uasset_read.core",
    "uasset_read.archive",
])
def test_module_importable(module_path):
    """核心模块应可成功导入。"""
    import importlib
    mod = importlib.import_module(module_path)
    assert mod is not None


# ============================================================================
# 4. parse_single 解析失败抛异常
# ============================================================================

def test_parse_single_raises_on_parse_failure():
    """parse_single 在解析失败时抛出 ParseError。"""
    from uasset_read.link.result import LinkerParseResult

    with patch("uasset_read.core.parse_uasset_with_linker") as mock_parse:
        mock_parse.return_value = LinkerParseResult(
            is_success=False,
            errors=["test error"],
        )
        with pytest.raises(ParseError, match="Parse failed"):
            parse_single("nonexistent.uasset", format="json")
