"""HexView IR 集成测试。

验证:
- HexViewEntryIR 数据类
- DebugIR 数据类
- _build_debug_ir() 函数
- PackageIR.debug 字段
- JSON 渲染器 debug.hex_view 输出
"""
import json
from dataclasses import dataclass
from typing import Any

import pytest

from uasset_read.debug.hex_view import HexViewEntry
from uasset_read.models.ir import HexViewEntryIR, DebugIR, PackageIR, PackageHeaderIR
from uasset_read.ir_builder import _build_debug_ir, build_package_ir
from uasset_read.renderers.json_renderer import JSONRenderer
from uasset_read.renderers.base import RenderOptions
from uasset_read.models.result import ParseResult


# ---------------------------------------------------------------------------
# HexViewEntryIR
# ---------------------------------------------------------------------------
class TestHexViewEntryIR:
    """HexViewEntryIR 数据类测试。"""

    def test_basic_creation(self):
        """基本创建和字段访问。"""
        entry = HexViewEntryIR(
            key="Magic", type="u32", value=0x9E2A83C1,
            start=0, stop=4, size=4,
        )
        assert entry.key == "Magic"
        assert entry.type == "u32"
        assert entry.value == 0x9E2A83C1
        assert entry.start == 0
        assert entry.stop == 4
        assert entry.size == 4

    def test_optional_fields_none(self):
        """可选字段默认为 None。"""
        entry = HexViewEntryIR(
            key="x", type="u8", value=1, start=0, stop=1, size=1,
        )
        assert entry.field_path is None
        assert entry.semantic_type is None
        assert entry.value_hex is None
        assert entry.value_size is None

    def test_optional_fields_set(self):
        """可选字段可设置。"""
        entry = HexViewEntryIR(
            key="x", type="u8", value=1, start=0, stop=1, size=1,
            field_path="PackageSummary.Magic",
            semantic_type="header",
        )
        assert entry.field_path == "PackageSummary.Magic"
        assert entry.semantic_type == "header"


# ---------------------------------------------------------------------------
# DebugIR
# ---------------------------------------------------------------------------
class TestDebugIR:
    """DebugIR 数据类测试。"""

    def test_default_empty(self):
        """默认空 DebugIR。"""
        debug = DebugIR()
        assert debug.hex_view == []

    def test_with_entries(self):
        """带条目的 DebugIR。"""
        entries = [
            HexViewEntryIR(key="a", type="u8", value=1, start=0, stop=1, size=1),
            HexViewEntryIR(key="b", type="u32", value=2, start=1, stop=5, size=4),
        ]
        debug = DebugIR(hex_view=entries)
        assert len(debug.hex_view) == 2
        assert debug.hex_view[0].key == "a"
        assert debug.hex_view[1].key == "b"


# ---------------------------------------------------------------------------
# _build_debug_ir
# ---------------------------------------------------------------------------
class TestBuildDebugIR:
    """_build_debug_ir 函数测试。"""

    def test_empty_entries_returns_none(self):
        """空条目返回 None。"""
        assert _build_debug_ir([]) is None

    def test_none_entries_returns_none(self):
        """None 输入返回 None。"""
        assert _build_debug_ir(None) is None

    def test_converts_hex_view_entries(self):
        """HexViewEntry 转换为 HexViewEntryIR。"""
        source = [
            HexViewEntry(key="Magic", type="u32", value=0x9E2A83C1, start=0, stop=4),
        ]
        result = _build_debug_ir(source)
        assert result is not None
        assert isinstance(result, DebugIR)
        assert len(result.hex_view) == 1
        assert result.hex_view[0].key == "Magic"
        assert result.hex_view[0].type == "u32"
        assert result.hex_view[0].value == 0x9E2A83C1
        assert result.hex_view[0].start == 0
        assert result.hex_view[0].stop == 4
        assert result.hex_view[0].size == 4

    def test_preserves_field_path_and_semantic_type(self):
        """保留 field_path 和 semantic_type。"""
        source = [
            HexViewEntry(
                key="Version", type="i32", value=100, start=4, stop=8,
                field_path="PackageSummary.Version",
                semantic_type="header",
            ),
        ]
        result = _build_debug_ir(source)
        assert result.hex_view[0].field_path == "PackageSummary.Version"
        assert result.hex_view[0].semantic_type == "header"

    def test_handles_legacy_entries_without_new_fields(self):
        """兼容没有新字段的旧条目。"""
        source = [
            HexViewEntry(key="x", type="u8", value=1, start=0, stop=1),
        ]
        result = _build_debug_ir(source)
        assert result is not None
        assert result.hex_view[0].field_path is None
        assert result.hex_view[0].semantic_type is None

    def test_multiple_entries(self):
        """多个条目转换。"""
        source = [
            HexViewEntry(key="A", type="u8", value=1, start=0, stop=1),
            HexViewEntry(key="B", type="u16", value=2, start=1, stop=3),
            HexViewEntry(key="C", type="u32", value=3, start=3, stop=7),
        ]
        result = _build_debug_ir(source)
        assert len(result.hex_view) == 3


# ---------------------------------------------------------------------------
# PackageIR.debug
# ---------------------------------------------------------------------------
class TestPackageIRDebug:
    """PackageIR.debug 字段测试。"""

    def _make_header(self):
        return PackageHeaderIR(
            package_name="Test", package_class="Package",
            package_flags=0, total_export_count=0, total_import_count=0,
            ue_version="5.4",
        )

    def test_default_none(self):
        """默认 debug 为 None。"""
        ir = PackageIR(
            header=self._make_header(),
            name_map=[], imports=[], exports=[], linker=None,
        )
        assert ir.debug is None

    def test_with_debug(self):
        """设置 debug 字段。"""
        debug = DebugIR(hex_view=[
            HexViewEntryIR(key="x", type="u8", value=1, start=0, stop=1, size=1),
        ])
        ir = PackageIR(
            header=self._make_header(),
            name_map=[], imports=[], exports=[], linker=None,
            debug=debug,
        )
        assert ir.debug is not None
        assert len(ir.debug.hex_view) == 1


# ---------------------------------------------------------------------------
# JSON Renderer — debug.hex_view 输出
# ---------------------------------------------------------------------------
class TestJSONRendererHexView:
    """JSON 渲染器 HexView 输出测试。"""

    def _make_ir(self, hex_view_entries=None):
        """构建用于测试的最小 PackageIR。"""
        header = PackageHeaderIR(
            package_name="Test", package_class="Package",
            package_flags=0, total_export_count=0, total_import_count=0,
            ue_version="5.4",
        )
        ir = PackageIR(
            header=header,
            name_map=[], imports=[], exports=[], linker=None,
        )
        if hex_view_entries:
            ir.debug = DebugIR(hex_view=hex_view_entries)
        return ir

    def test_no_debug_when_hex_view_flag_false(self):
        """hex_view=False 时不输出 debug。"""
        ir = self._make_ir([
            HexViewEntryIR(key="x", type="u8", value=1, start=0, stop=1, size=1),
        ])
        renderer = JSONRenderer()
        options = RenderOptions(hex_view=False)
        output = json.loads(renderer.render(ir, options))
        assert "debug" not in output

    def test_debug_output_when_hex_view_flag_true(self):
        """hex_view=True 时输出 debug.hex_view。"""
        ir = self._make_ir([
            HexViewEntryIR(key="Magic", type="u32", value=0x9E2A83C1, start=0, stop=4, size=4),
        ])
        renderer = JSONRenderer()
        options = RenderOptions(hex_view=True)
        output = json.loads(renderer.render(ir, options))
        assert "debug" in output
        assert "hex_view" in output["debug"]
        assert len(output["debug"]["hex_view"]) == 1
        assert output["debug"]["hex_view"][0]["key"] == "Magic"
        assert output["debug"]["hex_view"][0]["type"] == "u32"
        assert output["debug"]["hex_view"][0]["value"] == 0x9E2A83C1
        assert output["debug"]["hex_view"][0]["start"] == 0
        assert output["debug"]["hex_view"][0]["stop"] == 4
        assert output["debug"]["hex_view"][0]["size"] == 4

    def test_debug_output_when_output_level_debug(self):
        """output_level='debug' 时输出 debug.hex_view。"""
        ir = self._make_ir([
            HexViewEntryIR(key="x", type="u8", value=1, start=0, stop=1, size=1),
        ])
        renderer = JSONRenderer()
        options = RenderOptions(output_level="debug")
        output = json.loads(renderer.render(ir, options))
        assert "debug" in output

    def test_no_debug_when_no_entries(self):
        """无条目时不输出 debug。"""
        ir = self._make_ir()  # 无 hex_view_entries
        renderer = JSONRenderer()
        options = RenderOptions(hex_view=True)
        output = json.loads(renderer.render(ir, options))
        assert "debug" not in output

    def test_field_path_in_output(self):
        """field_path 字段正确输出。"""
        ir = self._make_ir([
            HexViewEntryIR(
                key="Version", type="i32", value=100, start=4, stop=8, size=4,
                field_path="PackageSummary.Version",
                semantic_type="header",
            ),
        ])
        renderer = JSONRenderer()
        options = RenderOptions(hex_view=True)
        output = json.loads(renderer.render(ir, options))
        entry = output["debug"]["hex_view"][0]
        assert entry["field_path"] == "PackageSummary.Version"
        assert entry["semantic_type"] == "header"

    def test_bytes_value_serialized_as_hex(self):
        """bytes 值序列化为 value_hex。"""
        ir = self._make_ir([
            HexViewEntryIR(
                key="raw", type="bytes", value=b'\xAB\xCD', start=0, stop=2, size=2,
            ),
        ])
        renderer = JSONRenderer()
        options = RenderOptions(hex_view=True)
        output = json.loads(renderer.render(ir, options))
        entry = output["debug"]["hex_view"][0]
        assert entry["value_hex"] == "abcd"
        assert entry["value_size"] == 2
        assert "value" not in entry


# ---------------------------------------------------------------------------
# core.py bypass 逻辑
# ---------------------------------------------------------------------------
class TestCoreBypassLogic:
    """core.py hex_view 旁路逻辑测试。"""

    def test_hex_view_text_format_bypasses_ir(self):
        """非 json 格式 + hex_view=True 时返回文本（旁路 IR）。"""
        from unittest.mock import MagicMock, patch
        from uasset_read.core import parse_single

        mock_result = MagicMock()
        mock_result.is_success = True
        mock_result.hex_view_entries = [
            HexViewEntry(key="x", type="u8", value=1, start=0, stop=1),
        ]
        mock_result.summary = MagicMock()
        mock_result.summary.uncompressed_size = 1024

        with patch("uasset_read.core.parse_package", return_value=mock_result):
            result = parse_single("fake.uasset", hex_view=True, format="markdown")
            assert isinstance(result, str)
            assert "HexView" in result

    def test_hex_view_json_format_goes_through_ir(self):
        """json 格式 + hex_view=True 时走 IR 管线。"""
        from unittest.mock import patch
        from uasset_read.core import parse_single

        # 构建真实 ParseResult 避免 mock 属性缺失问题
        mock_result = ParseResult()
        mock_result.is_success = True
        mock_result.hex_view_entries = [
            HexViewEntry(key="Magic", type="u32", value=0x9E2A83C1, start=0, stop=4),
        ]

        # json 格式走 linker 路径，需要 mock parse_uasset_with_linker
        with patch("uasset_read.core.parse_uasset_with_linker", return_value=mock_result):
            result = parse_single("fake.uasset", hex_view=True, format="json")
            # JSON 格式走 IR 管线，返回 JSON 字符串
            assert isinstance(result, str)
            output = json.loads(result)
            assert "summary" in output
            assert "debug" in output
            assert output["debug"]["hex_view"][0]["key"] == "Magic"
