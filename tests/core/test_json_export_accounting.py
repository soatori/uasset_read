"""Regression coverage for JSON export accounting after tolerant IR skips."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from uasset_read.constants import UE5_REMOVE_OBJECT_EXPORT_PACKAGE_GUID
from uasset_read.ir_builder import build_package_ir
from uasset_read.models.diagnostics import OffsetRangeDiagnostic, StructuredDiagnostic
from uasset_read.models.ir import ExportIR
from uasset_read.models.result import ParseResult
from uasset_read.renderers.base import RenderOptions
from uasset_read.renderers.json_renderer import JSONRenderer
from uasset_read.serializers.object_resources import read_export_map
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
        assert statistics["exports_parsed"] == 3
        assert statistics["exports_built"] == 2
        assert statistics["diagnostic_count"] == 2
        assert statistics["exports_rendered"] == 2
        assert statistics["exports_omitted"] == 1
        assert statistics["omitted_by_reason"] == {"ir_build_failed": 1}
        assert sum(statistics["omitted_by_reason"].values()) == statistics["exports_omitted"]


def test_json_statistics_keep_loss_accounting_when_header_understates_exports(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A smaller declared count must not hide parsed-table or IR-build losses."""
    result = ParseResult(
        summary=PackageFileSummary(tag=0, legacy_file_version=0, export_count=1),
        export_map=[SimpleNamespace(), SimpleNamespace(), SimpleNamespace()],
    )

    def build_or_fail(index: int, export: object, parse_result: ParseResult) -> ExportIR:
        if index == 1:
            raise ValueError("forced IR build failure")
        return _built_export(index)

    monkeypatch.setattr("uasset_read.ir_builder._build_export_ir", build_or_fail)
    package_ir = build_package_ir(result)

    for options in (RenderOptions(), RenderOptions(output_level="debug")):
        statistics = JSONRenderer()._build_data(package_ir, options)["statistics"]
        assert statistics["total_exports"] == 3
        assert statistics["total_exports_in_table"] == 3
        assert statistics["exports_parsed"] == 3
        assert statistics["exports_built"] == 2
        assert statistics["exports_rendered"] == 2
        assert statistics["exports_omitted"] == 1
        assert statistics["omitted_by_reason"] == {"ir_build_failed": 1}
        assert sum(statistics["omitted_by_reason"].values()) == statistics["exports_omitted"]


class _TolerantExportTableArchive:
    """Minimal archive that makes the second declared export-table row fail."""

    def __init__(self) -> None:
        self.position = 0

    def seek(self, position: int) -> None:
        self.position = position

    def tell(self) -> int:
        return self.position

    def read_i32(self, key: str = "") -> int:
        self.position += 4
        if key.startswith("Export[1]"):
            raise ValueError("forced export-table row failure")
        if key.endswith("SerialSize"):
            return 64
        return 0

    def read_u32(self, key: str = "") -> int:
        self.position += 4
        return 0

    def read_bool(self, key: str = "") -> bool:
        self.position += 4
        return False

    def read_name(self, name_map: list[str], key: str = "") -> str:
        self.position += 8
        return "SurvivingExport"


def test_json_statistics_account_for_tolerant_export_table_read_failures() -> None:
    """Legacy total_exports remains parsed rows; declared table rows remain auditable."""
    summary = PackageFileSummary(
        tag=0,
        legacy_file_version=0,
        file_version_ue4=0,
        file_version_ue5=UE5_REMOVE_OBJECT_EXPORT_PACKAGE_GUID,
        export_count=2,
        export_offset=100,
    )
    parsed_exports = read_export_map(_TolerantExportTableArchive(), summary, [])

    assert len(parsed_exports) == 1
    assert parsed_exports[0].serial_size > 0

    package_ir = build_package_ir(ParseResult(summary=summary, export_map=parsed_exports))
    for options in (RenderOptions(), RenderOptions(output_level="debug")):
        data = JSONRenderer()._build_data(package_ir, options)
        statistics = data["statistics"]
        assert data["summary"]["total_export_count"] == 2
        assert statistics["total_exports"] == 1
        assert statistics["total_exports_in_table"] == 2
        assert statistics["exports_parsed"] == 1
        assert statistics["exports_built"] == 1
        assert statistics["exports_rendered"] == 1
        assert statistics["exports_omitted"] == 1
        assert statistics["omitted_by_reason"] == {"export_table_parse_failed": 1}
        assert sum(statistics["omitted_by_reason"].values()) == statistics["exports_omitted"]
