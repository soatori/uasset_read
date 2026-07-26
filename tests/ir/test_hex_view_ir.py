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
from uasset_read.models.ir import HexViewEntryIR, DebugIR, PackageIR, PackageHeaderIR, DiagnosticsDataIR
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
        mock_result.hex_view_dropped_count = 0
        mock_result.diagnostics_dropped_count = 0
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


# ===========================================================================
# Truncation visibility tests (#447)
# ===========================================================================


class TestDebugIRTruncationVisibility:
    """DebugIR and DiagnosticsDataIR expose truncation metadata."""

    def test_debug_ir_hex_view_truncated_count_default(self):
        """DebugIR defaults hex_view_truncated_count to 0."""
        ir = DebugIR()
        assert ir.hex_view_truncated_count == 0

    def test_debug_ir_hex_view_truncated_count_set(self):
        """DebugIR hex_view_truncated_count is settable."""
        ir = DebugIR(hex_view_truncated_count=42)
        assert ir.hex_view_truncated_count == 42

    def test_debug_ir_not_none_when_only_truncated(self):
        """_build_debug_ir returns DebugIR when entries are empty but truncation > 0."""
        from uasset_read.ir_builder import _build_debug_ir
        result = _build_debug_ir([], hex_view_truncated_count=5)
        assert result is not None
        assert result.hex_view == []
        assert result.hex_view_truncated_count == 5

    def test_debug_ir_none_when_no_entries_and_no_truncation(self):
        """_build_debug_ir returns None when both entries and truncation are empty."""
        from uasset_read.ir_builder import _build_debug_ir
        result = _build_debug_ir([])
        assert result is None

    def test_diagnostics_data_truncated_count_default(self):
        """DiagnosticsDataIR defaults diagnostics_truncated_count to 0."""
        dd = DiagnosticsDataIR()
        assert dd.diagnostics_truncated_count == 0

    def test_diagnostics_data_truncated_count_set(self):
        """DiagnosticsDataIR diagnostics_truncated_count is settable."""
        dd = DiagnosticsDataIR(diagnostics_truncated_count=10)
        assert dd.diagnostics_truncated_count == 10


class TestBoundedEventBufferTruncation:
    """BoundedEventBuffer tracks dropped entries correctly."""

    def test_dropped_count_zero_when_under_limit(self):
        """No entries dropped when under max_entries."""
        from uasset_read.bounded_events import BoundedEventBuffer
        buf = BoundedEventBuffer(max_entries=10)
        buf.append("a")
        buf.append("b")
        assert buf.dropped_count == 0

    def test_dropped_count_increments_when_over_limit(self):
        """dropped_count increments when buffer is full."""
        from uasset_read.bounded_events import BoundedEventBuffer
        buf = BoundedEventBuffer(max_entries=3)
        for i in range(10):
            buf.append(f"entry_{i}")
        assert buf.dropped_count == 7  # 10 - 3 = 7

    def test_dropped_count_bytes_limit(self):
        """dropped_count increments when byte limit is exceeded."""
        from uasset_read.bounded_events import BoundedEventBuffer
        buf = BoundedEventBuffer(max_entries=1000, max_bytes=20)
        buf.append("short")       # 5 bytes
        buf.append("short")       # 5 bytes (total 10)
        buf.append("short")       # 5 bytes (total 15)
        buf.append("short")       # 5 bytes (total 20)
        buf.append("overflow")    # exceeds 20 bytes -> dropped
        assert buf.dropped_count == 1

    def test_dropped_count_resets_on_clear(self):
        """dropped_count resets to 0 after clear()."""
        from uasset_read.bounded_events import BoundedEventBuffer
        buf = BoundedEventBuffer(max_entries=2)
        for i in range(10):
            buf.append(f"e_{i}")
        assert buf.dropped_count == 8
        buf.clear()
        assert buf.dropped_count == 0


class TestArchiveTruncationExposure:
    """FArchive exposes dropped counts from BoundedEventBuffer."""

    def test_diagnostics_dropped_count_zero_initially(self):
        """ByteArchive.diagnostics_dropped_count starts at 0."""
        from uasset_read.archive import ByteArchive
        ar = ByteArchive(b'\x00' * 100)
        assert ar.diagnostics_dropped_count == 0

    def test_hex_view_dropped_count_zero_initially(self):
        """ByteArchive.hex_view_dropped_count starts at 0."""
        from uasset_read.archive import ByteArchive
        ar = ByteArchive(b'\x00' * 100)
        ar.enable_hex_view(True)
        assert ar.hex_view_dropped_count == 0


class TestPackageIRTruncationPropagation:
    """Verify truncation metadata propagates through PackageIR."""

    def _make_header(self):
        return PackageHeaderIR(
            package_name="Test",
            package_class="Normal",
            package_flags=0,
            total_export_count=0,
            total_import_count=0,
            ue_version="5.4",
        )

    def _make_ir(self, **kwargs):
        defaults = dict(
            header=self._make_header(),
            name_map=(),
            imports=[],
            exports=[],
            linker=None,
        )
        defaults.update(kwargs)
        return PackageIR(**defaults)

    def test_package_ir_debug_has_truncation(self):
        """PackageIR.debug carries hex_view_truncated_count."""
        ir = self._make_ir(
            debug=DebugIR(hex_view_truncated_count=15),
        )
        assert ir.debug.hex_view_truncated_count == 15

    def test_package_ir_diagnostics_data_has_truncation(self):
        """PackageIR.diagnostics_data carries diagnostics_truncated_count."""
        ir = self._make_ir(
            diagnostics_data=DiagnosticsDataIR(diagnostics_truncated_count=3),
        )
        assert ir.diagnostics_data.diagnostics_truncated_count == 3


class TestJSONRendererTruncationVisibility:
    """JSON renderer surfaces truncation metadata."""

    def _make_header(self):
        return PackageHeaderIR(
            package_name="Test",
            package_class="Normal",
            package_flags=0,
            total_export_count=0,
            total_import_count=0,
            ue_version="5.4",
        )

    def _make_ir(self, **kwargs):
        defaults = dict(
            header=self._make_header(),
            name_map=(),
            imports=[],
            exports=[],
            linker=None,
        )
        defaults.update(kwargs)
        return PackageIR(**defaults)

    def test_json_includes_diagnostics_truncated_count(self):
        """JSON output includes diagnostics_truncated_count when > 0."""
        from uasset_read.renderers.json_renderer import JSONRenderer
        from uasset_read.renderers.base import RenderOptions
        renderer = JSONRenderer()
        options = RenderOptions()
        ir = self._make_ir(
            diagnostics_data=DiagnosticsDataIR(diagnostics_truncated_count=42),
        )
        result = renderer.render(ir, options)
        assert "diagnostics_truncated_count" in result
        assert "42" in result

    def test_json_includes_hex_view_truncated_count(self):
        """JSON output includes hex_view_truncated_count in debug when > 0."""
        from uasset_read.renderers.json_renderer import JSONRenderer
        from uasset_read.renderers.base import RenderOptions
        renderer = JSONRenderer()
        options = RenderOptions(hex_view=True)
        ir = self._make_ir(
            debug=DebugIR(hex_view_truncated_count=99),
        )
        result = renderer.render(ir, options)
        assert "hex_view_truncated_count" in result
        assert "99" in result

    def test_json_omits_truncated_count_when_zero(self):
        """JSON output omits truncation counts when they are 0."""
        from uasset_read.renderers.json_renderer import JSONRenderer
        from uasset_read.renderers.base import RenderOptions
        renderer = JSONRenderer()
        options = RenderOptions()
        ir = self._make_ir(
            diagnostics_data=DiagnosticsDataIR(diagnostics_truncated_count=0),
        )
        result = renderer.render(ir, options)
        assert "diagnostics_truncated_count" not in result


class TestMarkdownRendererTruncationVisibility:
    """Markdown renderer surfaces truncation notices."""

    def _make_header(self):
        return PackageHeaderIR(
            package_name="Test",
            package_class="Normal",
            package_flags=0,
            total_export_count=0,
            total_import_count=0,
            ue_version="5.4",
        )

    def _make_ir(self, **kwargs):
        defaults = dict(
            header=self._make_header(),
            name_map=(),
            imports=[],
            exports=[],
            linker=None,
        )
        defaults.update(kwargs)
        return PackageIR(**defaults)

    def test_markdown_includes_diagnostics_truncation_notice(self):
        """Markdown output includes truncation notice when diagnostics dropped."""
        from uasset_read.renderers.markdown_renderer import MarkdownRenderer
        from uasset_read.renderers.base import RenderOptions
        renderer = MarkdownRenderer()
        options = RenderOptions()
        ir = self._make_ir(
            diagnostics_data=DiagnosticsDataIR(diagnostics_truncated_count=5),
        )
        result = renderer.render(ir, options)
        assert "dropped" in result.lower()
        assert "5" in result


class TestCleanupArchiveDiagnosticsPropagation:
    """Verify _cleanup_archive_diagnostics propagates dropped counts to ParseResult."""

    def test_archive_diagnostics_dropped_count_propagates(self):
        """Archive diagnostics_dropped_count is added to result."""
        from unittest.mock import MagicMock
        from uasset_read.parse_uasset import _cleanup_archive_diagnostics
        from uasset_read.models.result import ParseResult

        result = ParseResult()
        archive = MagicMock()
        archive.get_diagnostics.return_value = []
        archive.is_hex_view_enabled.return_value = False
        archive.diagnostics_dropped_count = 42
        archive.hex_view_dropped_count = 0

        _cleanup_archive_diagnostics(result, archive)

        assert result.diagnostics_dropped_count == 42

    def test_archive_hex_view_dropped_count_propagates(self):
        """Archive hex_view_dropped_count is added to result."""
        from unittest.mock import MagicMock
        from uasset_read.parse_uasset import _cleanup_archive_diagnostics
        from uasset_read.models.result import ParseResult

        result = ParseResult()
        archive = MagicMock()
        archive.get_diagnostics.return_value = []
        archive.is_hex_view_enabled.return_value = False
        archive.diagnostics_dropped_count = 0
        archive.hex_view_dropped_count = 17

        _cleanup_archive_diagnostics(result, archive)

        assert result.hex_view_dropped_count == 17

    def test_both_counts_propagate(self):
        """Both diagnostics and hex_view dropped counts propagate together."""
        from unittest.mock import MagicMock
        from uasset_read.parse_uasset import _cleanup_archive_diagnostics
        from uasset_read.models.result import ParseResult

        result = ParseResult()
        archive = MagicMock()
        archive.get_diagnostics.return_value = []
        archive.is_hex_view_enabled.return_value = False
        archive.diagnostics_dropped_count = 10
        archive.hex_view_dropped_count = 25

        _cleanup_archive_diagnostics(result, archive)

        assert result.diagnostics_dropped_count == 10
        assert result.hex_view_dropped_count == 25

    def test_counts_accumulate_with_existing(self):
        """Dropped counts accumulate with any pre-existing result counts."""
        from unittest.mock import MagicMock
        from uasset_read.parse_uasset import _cleanup_archive_diagnostics
        from uasset_read.models.result import ParseResult

        result = ParseResult()
        result.diagnostics_dropped_count = 5  # pre-existing from linker
        archive = MagicMock()
        archive.get_diagnostics.return_value = []
        archive.is_hex_view_enabled.return_value = False
        archive.diagnostics_dropped_count = 3
        archive.hex_view_dropped_count = 8

        _cleanup_archive_diagnostics(result, archive)

        assert result.diagnostics_dropped_count == 8  # 5 + 3
        assert result.hex_view_dropped_count == 8

    def test_linker_diagnostics_dropped_count_propagates(self):
        """Linker _diagnostics.dropped_count is aggregated into result."""
        from unittest.mock import MagicMock
        from uasset_read.parse_uasset import _cleanup_archive_diagnostics
        from uasset_read.models.result import ParseResult

        result = ParseResult()
        linker = MagicMock()
        linker.diagnostics = [MagicMock()]  # non-empty to trigger extend()
        linker._diagnostics = MagicMock()
        linker._diagnostics.dropped_count = 12
        result.linker = linker

        archive = MagicMock()
        archive.get_diagnostics.return_value = []
        archive.is_hex_view_enabled.return_value = False
        archive.diagnostics_dropped_count = 0
        archive.hex_view_dropped_count = 0

        _cleanup_archive_diagnostics(result, archive)

        assert result.diagnostics_dropped_count == 12

    def test_result_dropped_counts_reflect_in_ir(self):
        """ParseResult dropped counts flow into IR diagnostics_data and debug."""
        from uasset_read.ir_builder import build_package_ir
        from uasset_read.models.result import ParseResult

        result = ParseResult()
        result.diagnostics_dropped_count = 30
        result.hex_view_dropped_count = 50
        result.name_map = ["Test"]

        ir = build_package_ir(result)

        assert ir.diagnostics_data is not None
        assert ir.diagnostics_data.diagnostics_truncated_count == 30
        assert ir.debug is not None
        assert ir.debug.hex_view_truncated_count == 50
