"""tests/renderers/test_report_quality.py — Markdown 渲染质量测试。"""

import pytest
from uasset_read.renderers.markdown_renderer import MarkdownRenderer
from uasset_read.renderers.base import RenderOptions
from uasset_read.models.ir import (
    PackageIR,
    PackageHeaderIR,
    ExportIR,
    LinkerSummaryIR,
)
from uasset_read.models.diagnostics import OffsetRangeDiagnostic, DiagnosticSeverity


def _make_package_ir(**overrides) -> PackageIR:
    """创建最小 PackageIR 用于测试。"""
    header = PackageHeaderIR(
        package_name="TestAsset",
        package_class="BlueprintGeneratedClass",
        package_flags=0,
        total_export_count=0,
        total_import_count=0,
        ue_version="5.4",
    )
    defaults = dict(
        header=header,
        name_map=(),
        imports=[],
        exports=[],
        linker=None,
        status="success",
    )
    defaults.update(overrides)
    return PackageIR(**defaults)


class TestMarkdownDiagnosticsSeverity:
    """诊断信息按严重度分组并显示图标的测试。"""

    def test_diagnostics_with_severity_icons(self):
        """严重度图标和分组正确渲染。"""
        ir = _make_package_ir(
            status="partial",
            diagnostics=[
                OffsetRangeDiagnostic(
                    kind="offset_range_diagnostic",
                    severity=DiagnosticSeverity.ERROR,
                    module="linker",
                    object_name="TestObject",
                    field="serial_offset",
                    error="Offset out of range",
                ),
                OffsetRangeDiagnostic(
                    kind="offset_range_diagnostic",
                    severity=DiagnosticSeverity.WARNING,
                    module="property",
                    object_name="TestObject2",
                    field="ValueEndOffset",
                    error="Value mismatch",
                ),
            ],
        )

        renderer = MarkdownRenderer()
        output = renderer.render(ir, RenderOptions())

        # 严重度图标
        assert "❌" in output
        assert "⚠️" in output

        # 严重度分组标题
        assert "ERROR (1)" in output
        assert "WARNING (1)" in output

        # 诊断内容
        assert "Offset out of range" in output
        assert "Value mismatch" in output

    def test_diagnostics_order_critical_first(self):
        """严重度按 critical > error > warning > info 排序。"""
        ir = _make_package_ir(
            diagnostics=[
                OffsetRangeDiagnostic(
                    severity=DiagnosticSeverity.INFO,
                    module="m1",
                    error="info msg",
                ),
                OffsetRangeDiagnostic(
                    severity=DiagnosticSeverity.CRITICAL,
                    module="m2",
                    error="critical msg",
                ),
                OffsetRangeDiagnostic(
                    severity=DiagnosticSeverity.WARNING,
                    module="m3",
                    error="warning msg",
                ),
            ],
        )

        renderer = MarkdownRenderer()
        output = renderer.render(ir, RenderOptions())

        # critical 在 warning 之前
        crit_pos = output.index("CRITICAL")
        warn_pos = output.index("WARNING")
        info_pos = output.index("INFO")
        assert crit_pos < warn_pos < info_pos

    def test_no_diagnostics_no_section(self):
        """无诊断时不输出章节。"""
        ir = _make_package_ir()
        renderer = MarkdownRenderer()
        output = renderer.render(ir, RenderOptions())
        assert "## 诊断信息" not in output
