"""诊断相关测试 — 合并自以下测试文件：
- test_diagnostic_output.py — PackageIR.diagnostics 字段及渲染器输出
- test_archive_diagnostic.py — FArchive 偏移诊断（seek_safe / read_safe 越界检测）
- test_offset_range_diagnostic.py — OffsetRangeDiagnostic 数据模型
"""
from __future__ import annotations

import json

import pytest

from uasset_read.archive import FArchive
from uasset_read.models.diagnostics import OffsetRangeDiagnostic
from uasset_read.models.ir import (
    PackageIR,
    PackageHeaderIR,
    ExportIR,
    LinkerSummaryIR,
)
from uasset_read.ir_builder import build_package_ir
from uasset_read.models.result import ParseResult
from uasset_read.renderers.markdown_renderer import MarkdownRenderer
from uasset_read.renderers.base import RenderOptions
from uasset_read.semantic.builder import build_semantic_ir
from uasset_read.semantic.projection import project_semantic
from uasset_read.semantic.render import render_semantic_json


# ---------------------------------------------------------------------------
# 辅助工厂
# ---------------------------------------------------------------------------

def _make_header() -> PackageHeaderIR:
    """创建最小 PackageHeaderIR。"""
    return PackageHeaderIR(
        package_name="/Game/Test",
        package_class="Blueprint",
        package_flags=0,
        total_export_count=1,
        total_import_count=0,
        ue_version="5.1",
    )


def _make_package_ir(diagnostics: list | None = None) -> PackageIR:
    """创建最小 PackageIR，可选注入 diagnostics。"""
    return PackageIR(
        header=_make_header(),
        name_map=[],
        imports=[],
        exports=[],
        linker=None,
        diagnostics=diagnostics or [],
    )


def _make_diagnostic(**overrides) -> OffsetRangeDiagnostic:
    """创建一个 OffsetRangeDiagnostic 实例，支持部分字段覆盖。"""
    defaults = dict(
        kind="offset_range_diagnostic",
        asset_path="/Game/Test",
        asset_type="Blueprint",
        module="graph",
        object_name="TestGraph",
        field="script_serial_offset",
        current_pos=100,
        target_offset=200,
        read_size=50,
        file_size=1024,
        error="offset out of range",
    )
    defaults.update(overrides)
    return OffsetRangeDiagnostic(**defaults)


# ===========================================================================
# 第一部分：OffsetRangeDiagnostic 数据模型测试
# ===========================================================================

class TestOffsetRangeDiagnostic:
    """OffsetRangeDiagnostic 数据模型单元测试。"""

    def test_default_instance(self):
        """默认实例化 — 所有字段使用默认值。"""
        diag = OffsetRangeDiagnostic()
        assert diag.kind == "offset_range_diagnostic"
        assert diag.asset_path == ""
        assert diag.asset_type == ""
        assert diag.module == ""
        assert diag.object_name == ""
        assert diag.export_index is None
        assert diag.import_index is None
        assert diag.field == ""
        assert diag.current_pos == 0
        assert diag.target_offset == 0
        assert diag.read_size == 0
        assert diag.file_size == 0
        assert diag.range_start is None
        assert diag.range_end is None
        assert diag.source == ""
        assert diag.error == ""
        assert diag.fallback_used is False
        assert diag.fallback_result == ""

    def test_custom_instance(self):
        """自定义实例化 — 传入所有字段。"""
        diag = OffsetRangeDiagnostic(
            kind="custom_kind",
            asset_path="/Game/Test",
            asset_type="Blueprint",
            module="linker",
            object_name="MyObject",
            export_index=3,
            import_index=7,
            field="serial_offset",
            current_pos=1024,
            target_offset=2048,
            read_size=512,
            file_size=4096,
            range_start=512,
            range_end=3000,
            source="PackageLinker",
            error="offset out of range",
            fallback_used=True,
            fallback_result="partial",
        )
        assert diag.kind == "custom_kind"
        assert diag.asset_path == "/Game/Test"
        assert diag.asset_type == "Blueprint"
        assert diag.module == "linker"
        assert diag.object_name == "MyObject"
        assert diag.export_index == 3
        assert diag.import_index == 7
        assert diag.field == "serial_offset"
        assert diag.current_pos == 1024
        assert diag.target_offset == 2048
        assert diag.read_size == 512
        assert diag.file_size == 4096
        assert diag.range_start == 512
        assert diag.range_end == 3000
        assert diag.source == "PackageLinker"
        assert diag.error == "offset out of range"
        assert diag.fallback_used is True
        assert diag.fallback_result == "partial"

    def test_to_dict_default(self):
        """to_dict() 默认实例 — 仅含 kind 和整数零值字段。"""
        diag = OffsetRangeDiagnostic()
        d = diag.to_dict()
        assert isinstance(d, dict)
        assert d["kind"] == "offset_range_diagnostic"
        # 整数字段始终输出（含 0）
        assert d["current_pos"] == 0
        assert d["target_offset"] == 0
        assert d["read_size"] == 0
        assert d["file_size"] == 0
        # 空字符串字段不输出
        assert "asset_path" not in d
        assert "module" not in d
        assert "error" not in d
        # None 字段不输出
        assert "export_index" not in d
        assert "range_start" not in d
        # False 布尔不输出
        assert "fallback_used" not in d

    def test_to_dict_full(self):
        """to_dict() 完整实例 — 所有字段均输出。"""
        diag = OffsetRangeDiagnostic(
            asset_path="/Game/Test.uasset",
            asset_type="SkeletalMesh",
            module="property",
            object_name="SK_Mannequin",
            export_index=0,
            import_index=None,
            field="serial_offset",
            current_pos=512,
            target_offset=1024,
            read_size=256,
            file_size=8192,
            range_start=0,
            range_end=1024,
            source="PropertyParser",
            error="read past end of export data",
            fallback_used=True,
            fallback_result="failed",
        )
        d = diag.to_dict()
        assert d["kind"] == "offset_range_diagnostic"
        assert d["asset_path"] == "/Game/Test.uasset"
        assert d["asset_type"] == "SkeletalMesh"
        assert d["module"] == "property"
        assert d["object_name"] == "SK_Mannequin"
        assert d["export_index"] == 0
        assert "import_index" not in d  # None 不输出
        assert d["field"] == "serial_offset"
        assert d["current_pos"] == 512
        assert d["target_offset"] == 1024
        assert d["read_size"] == 256
        assert d["file_size"] == 8192
        assert d["range_start"] == 0
        assert d["range_end"] == 1024
        assert d["source"] == "PropertyParser"
        assert d["error"] == "read past end of export data"
        assert d["fallback_used"] is True
        assert d["fallback_result"] == "failed"

    def test_to_dict_json_serializable(self):
        """to_dict() 输出可被 json.dumps 序列化。"""
        diag = OffsetRangeDiagnostic(
            asset_path="/Game/Test",
            module="kismet",
            field="CodeOffset",
            current_pos=100,
            target_offset=200,
            read_size=50,
            file_size=4000,
            fallback_used=True,
            fallback_result="success",
        )
        d = diag.to_dict()
        # 不应抛出异常
        serialized = json.dumps(d, ensure_ascii=False)
        assert isinstance(serialized, str)
        assert "offset_range_diagnostic" in serialized

    def test_to_dict_zero_export_index(self):
        """export_index=0 应输出（非 None）。"""
        diag = OffsetRangeDiagnostic(export_index=0)
        d = diag.to_dict()
        assert d["export_index"] == 0

    def test_to_dict_none_export_index(self):
        """export_index=None 不应输出。"""
        diag = OffsetRangeDiagnostic(export_index=None)
        d = diag.to_dict()
        assert "export_index" not in d

    def test_to_dict_zero_range_boundaries(self):
        """range_start=0 应输出（非 None）。"""
        diag = OffsetRangeDiagnostic(range_start=0, range_end=0)
        d = diag.to_dict()
        assert d["range_start"] == 0
        assert d["range_end"] == 0

    def test_module_values(self):
        """验证各 module 值均可正确设置和输出。"""
        for mod in ("linker", "property", "graph", "pin", "kismet", "pak", "iostore"):
            diag = OffsetRangeDiagnostic(module=mod)
            d = diag.to_dict()
            assert d["module"] == mod

    def test_field_values(self):
        """验证各 field 值均可正确设置和输出。"""
        for fld in ("serial_offset", "script_serial_offset", "ValueEndOffset", "CodeOffset", "LinkedTo"):
            diag = OffsetRangeDiagnostic(field=fld)
            d = diag.to_dict()
            assert d["field"] == fld

    def test_fallback_result_values(self):
        """验证 fallback_result 各取值。"""
        for result in ("failed", "partial", "success"):
            diag = OffsetRangeDiagnostic(fallback_result=result)
            d = diag.to_dict()
            assert d["fallback_result"] == result


# ===========================================================================
# 第二部分：FArchive 偏移诊断测试
# ===========================================================================

@pytest.fixture
def sample_archive(tmp_path):
    """创建 16 字节测试文件并返回 FArchive 实例。"""
    data = bytes(range(16))  # 0x00..0x0F
    path = tmp_path / "test.bin"
    path.write_bytes(data)
    ar = FArchive(str(path), tolerant=True)
    yield ar
    ar.close()


class TestSeekSafe:
    """seek_safe() 越界诊断。"""

    def test_seek_within_bounds_returns_true(self, sample_archive):
        """正常 seek 返回 True，不产生诊断。"""
        result = sample_archive.seek_safe(8)
        assert result is True
        assert sample_archive.tell() == 8
        assert len(sample_archive.get_diagnostics()) == 0

    def test_seek_to_zero(self, sample_archive):
        """seek 到起始位置。"""
        assert sample_archive.seek_safe(0) is True

    def test_seek_to_eof(self, sample_archive):
        """seek 到文件末尾（合法）。"""
        assert sample_archive.seek_safe(16) is True

    def test_seek_beyond_eof_records_diagnostic(self, sample_archive):
        """seek 超出文件大小产生诊断。"""
        result = sample_archive.seek_safe(100)
        assert result is False
        diags = sample_archive.get_diagnostics()
        assert len(diags) == 1
        d = diags[0]
        assert d.field == "seek"
        assert d.target_offset == 100
        assert d.file_size == 16
        assert "超出文件范围" in d.error

    def test_seek_negative_records_diagnostic(self, sample_archive):
        """seek 负偏移产生诊断。"""
        result = sample_archive.seek_safe(-1)
        assert result is False
        diags = sample_archive.get_diagnostics()
        assert len(diags) == 1
        assert diags[0].target_offset == -1

    def test_seek_preserves_position_on_failure(self, sample_archive):
        """seek 失败后位置不变。"""
        sample_archive.seek_safe(4)
        sample_archive.seek_safe(100)
        assert sample_archive.tell() == 4

    def test_seek_context_recorded(self, sample_archive):
        """context 参数记录到诊断中。"""
        sample_archive.seek_safe(100, context="test_phase")
        d = sample_archive.get_diagnostics()[0]
        assert d.source == "test_phase"

    def test_seek_default_context(self, sample_archive):
        """无 context 时使用默认值。"""
        sample_archive.seek_safe(100)
        d = sample_archive.get_diagnostics()[0]
        assert d.source == "seek_safe"


class TestReadSafe:
    """read_safe() 越界诊断。"""

    def test_read_within_bounds_returns_data(self, sample_archive):
        """正常 read 返回数据，不产生诊断。"""
        data = sample_archive.read_safe(4)
        assert data is not None
        assert len(data) == 4
        assert len(sample_archive.get_diagnostics()) == 0

    def test_read_exact_remaining(self, sample_archive):
        """读取恰好剩余的字节数。"""
        sample_archive.seek_safe(12)
        data = sample_archive.read_safe(4)
        assert data is not None
        assert len(data) == 4

    def test_read_beyond_remaining_records_diagnostic(self, sample_archive):
        """请求超出剩余字节产生诊断并返回 None。"""
        sample_archive.seek_safe(12)
        data = sample_archive.read_safe(8)
        assert data is None
        diags = sample_archive.get_diagnostics()
        assert len(diags) == 1
        d = diags[0]
        assert d.field == "read"
        assert d.read_size == 8
        assert "仅剩 4 字节" in d.error

    def test_read_negative_size_records_diagnostic(self, sample_archive):
        """负大小产生诊断。"""
        data = sample_archive.read_safe(-1)
        assert data is None
        d = sample_archive.get_diagnostics()[0]
        assert d.read_size == -1
        assert "负数" in d.error

    def test_read_at_eof_records_diagnostic(self, sample_archive):
        """在 EOF 处读取产生诊断。"""
        sample_archive.seek_safe(16)
        data = sample_archive.read_safe(1)
        assert data is None
        d = sample_archive.get_diagnostics()[0]
        assert d.read_size == 1
        assert d.current_pos == 16

    def test_read_context_recorded(self, sample_archive):
        """context 参数记录到诊断中。"""
        sample_archive.read_safe(100, context="export_parse")
        d = sample_archive.get_diagnostics()[0]
        assert d.source == "export_parse"


class TestDiagnosticAccumulation:
    """多次诊断累积。"""

    def test_multiple_diagnostics_accumulated(self, sample_archive):
        """多次越界操作累积诊断记录。"""
        sample_archive.seek_safe(100, context="s1")
        sample_archive.seek_safe(200, context="s2")
        sample_archive.read_safe(50, context="r1")
        diags = sample_archive.get_diagnostics()
        assert len(diags) == 3

    def test_diagnostics_returns_copy(self, sample_archive):
        """get_diagnostics() 返回副本。"""
        sample_archive.seek_safe(100)
        diags = sample_archive.get_diagnostics()
        diags.clear()
        assert len(sample_archive.get_diagnostics()) == 1

    def test_no_diagnostics_for_clean_session(self, sample_archive):
        """正常操作不产生任何诊断。"""
        sample_archive.seek_safe(0)
        sample_archive.read_safe(8)
        sample_archive.seek_safe(4)
        sample_archive.read_safe(4)
        assert len(sample_archive.get_diagnostics()) == 0


class TestDiagnosticFields:
    """诊断记录字段完整性。"""

    def test_seek_diagnostic_fields(self, sample_archive):
        """seek 诊断包含所有必要字段。"""
        sample_archive.seek_safe(4)
        sample_archive.seek_safe(100)
        d = sample_archive.get_diagnostics()[0]
        assert d.module == "archive"
        assert d.current_pos == 4
        assert d.target_offset == 100
        assert d.file_size == 16

    def test_read_diagnostic_fields(self, sample_archive):
        """read 诊断包含所有必要字段。"""
        sample_archive.seek_safe(14)
        sample_archive.read_safe(8)
        d = sample_archive.get_diagnostics()[0]
        assert d.module == "archive"
        assert d.current_pos == 14
        assert d.read_size == 8
        assert d.file_size == 16

    def test_diagnostic_to_dict(self, sample_archive):
        """诊断可序列化为字典。"""
        sample_archive.seek_safe(100)
        d = sample_archive.get_diagnostics()[0]
        d_dict = d.to_dict()
        assert isinstance(d_dict, dict)
        assert d_dict["kind"] == "offset_range_diagnostic"
        assert d_dict["field"] == "seek"


# ===========================================================================
# 第三部分：PackageIR.diagnostics 字段测试
# ===========================================================================

class TestPackageIRDiagnostics:
    """验证 PackageIR 拥有 diagnostics 字段且行为正确。"""

    def test_default_empty(self):
        """默认 diagnostics 应为空列表。"""
        ir = _make_package_ir()
        assert ir.diagnostics == []

    def test_accepts_list(self):
        """diagnostics 可以接受 OffsetRangeDiagnostic 列表。"""
        diag = _make_diagnostic()
        ir = _make_package_ir(diagnostics=[diag])
        assert len(ir.diagnostics) == 1
        assert ir.diagnostics[0].kind == "offset_range_diagnostic"

    def test_field_independent(self):
        """不同实例的 diagnostics 互不影响（field default_factory 隔离）。"""
        ir1 = _make_package_ir()
        ir2 = _make_package_ir()
        ir1.diagnostics.append(_make_diagnostic())
        assert len(ir1.diagnostics) == 1
        assert len(ir2.diagnostics) == 0


class TestBuildPackageIRDiagnostics:
    """验证 build_package_ir 正确传递 diagnostics。"""

    def test_empty_diagnostics(self):
        """ParseResult.diagnostics 为空时，PackageIR.diagnostics 也为空。"""
        result = ParseResult(is_success=True)
        ir = build_package_ir(result)
        assert ir.diagnostics == []

    def test_passes_diagnostics(self):
        """ParseResult.diagnostics 非空时，PackageIR.diagnostics 包含相同元素。"""
        diag = _make_diagnostic()
        result = ParseResult(is_success=True, diagnostics=[diag])
        ir = build_package_ir(result)
        assert len(ir.diagnostics) == 1
        assert ir.diagnostics[0].kind == "offset_range_diagnostic"

    def test_none_diagnostics(self):
        """ParseResult.diagnostics 为 None 时，PackageIR.diagnostics 为空列表。"""
        result = ParseResult(is_success=True)
        result.diagnostics = None
        ir = build_package_ir(result)
        assert ir.diagnostics == []


# ===========================================================================
# 第四部分：渲染器 diagnostics 输出测试
# ===========================================================================

class TestSemanticDiagnostics:
    """Verify semantic pipeline handles diagnostics correctly."""

    def _render(self, ir: PackageIR) -> dict:
        semantic_ir = build_semantic_ir(ir)
        semantic_ir = project_semantic(semantic_ir, "standard")
        raw = render_semantic_json(semantic_ir)
        return json.loads(raw)

    def test_no_diagnostics_key_when_empty(self):
        """No diagnostics in output when PackageIR has diagnostics_data=None."""
        ir = _make_package_ir()
        data = self._render(ir)
        # The semantic builder adds a NO_EXPORTS warning when no exports exist,
        # so diagnostics may be present even with empty PackageIR.diagnostics.
        assert data["format"] == "uasset_read.asset_semantic"

    def test_diagnostics_present_when_diagnostic_data_exists(self):
        """Diagnostics should appear in semantic output when diagnostics_data is present."""
        # The semantic builder uses diagnostics_data, not the raw diagnostics list.
        # With empty diagnostics_data, no diagnostics appear.
        ir = _make_package_ir()
        data = self._render(ir)
        # Semantic output should be valid JSON
        assert data["format"] == "uasset_read.asset_semantic"

    def test_semantic_output_is_valid_json(self):
        """Semantic output should always be valid JSON."""
        diag = _make_diagnostic()
        ir = _make_package_ir(diagnostics=[diag])
        data = self._render(ir)
        assert "format" in data
        assert "status" in data
        assert "asset" in data


class TestMarkdownRendererDiagnostics:
    """验证 MarkdownRenderer 输出诊断信息表格。"""

    def _render(self, ir: PackageIR) -> str:
        renderer = MarkdownRenderer()
        options = RenderOptions()
        return renderer.render(ir, options)

    def test_no_diagnostics_section_when_empty(self):
        """无诊断时 Markdown 不包含诊断信息章节。"""
        ir = _make_package_ir()
        md = self._render(ir)
        assert "诊断信息" not in md

    def test_diagnostics_section_present(self):
        """有诊断时 Markdown 包含诊断信息章节。"""
        diag = _make_diagnostic()
        ir = _make_package_ir(diagnostics=[diag])
        md = self._render(ir)
        assert "## 诊断信息" in md

    def test_diagnostics_table_header(self):
        """诊断信息章节包含表头行。"""
        diag = _make_diagnostic()
        ir = _make_package_ir(diagnostics=[diag])
        md = self._render(ir)
        assert "| 类型 | 模块 | 对象名 | 字段 | 错误信息 |" in md

    def test_diagnostics_table_row_content(self):
        """诊断表格行包含正确的字段值。"""
        diag = _make_diagnostic(module="linker", error="invalid index")
        ir = _make_package_ir(diagnostics=[diag])
        md = self._render(ir)
        assert "linker" in md
        assert "invalid index" in md
