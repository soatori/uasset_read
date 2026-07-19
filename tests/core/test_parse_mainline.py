"""主链路解析测试 — 合并自 test_core_all.py、test_core_api.py、test_core_config.py。

覆盖：主链路解析、API 调用、配置处理。
"""
from __future__ import annotations

import inspect
import struct
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from uasset_read.archive import ByteArchive
from uasset_read.config import ParseConfig
from uasset_read.core import (
    BatchResult,
    parse_batch,
    parse_single,
)
from uasset_read.core.error_handling import tolerant_parse
from uasset_read.core.utils import safe_str
from uasset_read.exceptions import ParseError
from uasset_read.models.result import ParseResult
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
    "uasset_read.parse_uasset",
    "uasset_read.cli",
    "uasset_read.renderers",
])
def test_module_importable(module_path):
    """核心模块应可成功导入。"""
    import importlib
    mod = importlib.import_module(module_path)
    assert mod is not None


# ============================================================================
# 4. 包级 API 结构
# ============================================================================

def test_public_api_structure():
    """uasset_read 包级 API 结构验证。"""
    import uasset_read
    assert callable(getattr(uasset_read, "parse_single", None))
    assert callable(getattr(uasset_read, "parse_batch", None))
    assert callable(getattr(uasset_read, "list_formats", None))
    assert "json" in uasset_read.list_formats()


# ============================================================================
# 5. DependsMap 异常数量防护
# ============================================================================

def test_depends_map_abnormal_count():
    """DependsMap 异常数量（>10000）应跳过该条目，返回空列表。"""
    from uasset_read.serializers.package_summary import read_depends_map, PackageFileSummary

    padding = b'\x00'
    data = padding + struct.pack('<i', 100000)
    archive = ByteArchive(data, tolerant=True)
    summary = PackageFileSummary.__new__(PackageFileSummary)
    summary.depends_offset = 1
    summary.export_count = 1

    result = read_depends_map(archive, summary)
    assert result == [[]]


# ============================================================================
# 6. parse_single 解析失败抛异常
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


# ============================================================================
# 7. parse_batch 返回 BatchResult
# ============================================================================

def test_parse_batch_returns_batch_result(tmp_path):
    """parse_batch 返回 BatchResult。"""
    test_file = tmp_path / "test.uasset"
    test_file.write_bytes(b"\x00" * 100)

    with patch("uasset_read.core._parse_and_render") as mock_parse:
        mock_result = MagicMock()
        mock_result.is_success = True
        mock_result.export_map = []
        mock_result.errors = []
        mock_result.hex_view_entries = None
        mock_parse.return_value = ('{"status": "success"}', mock_result)

        result = parse_batch(
            str(tmp_path),
            format="json",
            isolate_assets=False,
        )

        assert isinstance(result, BatchResult)
        assert result.total == 1


# ============================================================================
# 8. parse_batch 参数完整性
# ============================================================================

class TestParameterIntegrity:
    """验证 parse_batch 与 parse_single 参数一致。"""

    def test_parse_batch_has_output_level(self):
        """parse_batch 应支持 output_level 参数。"""
        sig = inspect.signature(parse_batch)
        assert "output_level" in sig.parameters

    def test_parse_batch_has_hex_view(self):
        """parse_batch 应支持 hex_view 参数。"""
        sig = inspect.signature(parse_batch)
        assert "hex_view" in sig.parameters
