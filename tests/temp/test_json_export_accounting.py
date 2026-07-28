"""Regression coverage for JSON export accounting after tolerant IR skips."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from uasset_read.ir_builder import build_package_ir
from uasset_read.models.diagnostics import OffsetRangeDiagnostic, StructuredDiagnostic
from uasset_read.models.ir import ExportIR
from uasset_read.models.result import ParseResult
from uasset_read.renderers.base import RenderOptions
from uasset_read.renderers.json_renderer import JSONRenderer
from uasset_read.serializers.package_summary import PackageFileSummary


def _built_export(index: int) -> ExportIR:
    return ExportIR(
        index=index,
        object_name=f"Export{index}",
        object_class="RuntimeClass",
        serial_size=1,
        outer_index_resolved=None,
        super_index_resolved=None,
        parent_class=None,
        properties=[],
        graphs=[],
        bulk_data=None,
    )


def test_json_statistics_account_for_skipped_ir_exports_and_all_diagnostics(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    result = ParseResult(
        summary=PackageFileSummary(tag=0, legacy_file_version=0, export_count=3),
        export_map=[SimpleNamespace(), SimpleNamespace(), SimpleNamespace()],
        diagnostics=[OffsetRangeDiagnostic()],
        structured_diagnostics=[StructuredDiagnostic(code="structured_test", stage="test")],
    )

    def build_or_fail(index: int, export: object, parse_result: ParseResult) -> ExportIR:
        if index == 1:
            raise ValueError("forced IR build failure")
        return _built_export(index)

    monkeypatch.setattr("uasset_read.ir_builder._build_export_ir", build_or_fail)
    package_ir = build_package_ir(result)

    standard = JSONRenderer()._build_data(package_ir, RenderOptions())
    debug = JSONRenderer()._build_data(package_ir, RenderOptions(output_level="debug"))

    for data in (standard, debug):
        statistics = data["statistics"]
        assert statistics["total_exports_in_table"] == 3
        assert statistics["exports_built"] == 2
        assert statistics["diagnostic_count"] == 2
        assert statistics["exports_rendered"] == 2
        assert statistics["exports_omitted"] == 1
        assert statistics["omitted_by_reason"] == {"ir_build_failed": 1}
        assert sum(statistics["omitted_by_reason"].values()) == statistics["exports_omitted"]
