"""诊断输出测试 — 验证 PackageIR.diagnostics 字段及渲染器输出。"""
from __future__ import annotations

import json

import pytest

from uasset_read.models.ir import (
    PackageIR,
    PackageHeaderIR,
    ExportIR,
    LinkerSummaryIR,
)
from uasset_read.models.diagnostics import OffsetRangeDiagnostic
from uasset_read.ir_builder import build_package_ir
from uasset_read.models.result import ParseResult
from uasset_read.renderers.json_renderer import JSONRenderer
from uasset_read.renderers.markdown_renderer import MarkdownRenderer
from uasset_read.renderers.base import RenderOptions


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


# ---------------------------------------------------------------------------
# PackageIR.diagnostics 字段测试
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# IR 构建器传递 diagnostics 测试
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# JSON 渲染器 diagnostics 输出测试
# ---------------------------------------------------------------------------

class TestJSONRendererDiagnostics:
    """验证 JSONRenderer 输出 diagnostics 数组。"""

    def _render(self, ir: PackageIR) -> dict:
        renderer = JSONRenderer()
        options = RenderOptions()
        raw = renderer.render(ir, options)
        return json.loads(raw)

    def test_no_diagnostics_key_when_empty(self):
        """无诊断时 JSON 不包含 diagnostics 键。"""
        ir = _make_package_ir()
        data = self._render(ir)
        assert "diagnostics" not in data

    def test_diagnostics_array_present(self):
        """有诊断时 JSON 包含 diagnostics 数组。"""
        diag = _make_diagnostic()
        ir = _make_package_ir(diagnostics=[diag])
        data = self._render(ir)
        assert "diagnostics" in data
        assert isinstance(data["diagnostics"], list)
        assert len(data["diagnostics"]) == 1

    def test_diagnostic_fields_serialized(self):
        """诊断条目应包含 kind、module、field、error 等关键字段。"""
        diag = _make_diagnostic(module="kismet", field="CodeOffset", error="overflow")
        ir = _make_package_ir(diagnostics=[diag])
        data = self._render(ir)
        entry = data["diagnostics"][0]
        assert entry["kind"] == "offset_range_diagnostic"
        assert entry["module"] == "kismet"
        assert entry["field"] == "CodeOffset"
        assert entry["error"] == "overflow"

    def test_multiple_diagnostics(self):
        """多条诊断应全部输出。"""
        d1 = _make_diagnostic(module="graph")
        d2 = _make_diagnostic(module="pin", object_name="PinA")
        ir = _make_package_ir(diagnostics=[d1, d2])
        data = self._render(ir)
        assert len(data["diagnostics"]) == 2
        assert data["diagnostics"][0]["module"] == "graph"
        assert data["diagnostics"][1]["module"] == "pin"


# ---------------------------------------------------------------------------
# Markdown 渲染器 diagnostics 输出测试
# ---------------------------------------------------------------------------

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
