"""Consolidated model tests — merges selected tests from:
- tests/ir/test_status_model.py (_result_status, ParseResult status mapping)
- tests/test_export_dependency.py (ExportDependencyIR)
- tests/test_gatherable_text.py (GatherableTextDataIR)
- tests/test_smoke_imports.py (status enums, fallback ExportParseStatus)
"""

from __future__ import annotations

import pytest


# ---------------------------------------------------------------------------
# Status model — _result_status() with mock objects (from test_status_model.py)
# ---------------------------------------------------------------------------


class MockExportMapEntry:
    """Mock ExportMapEntry for _result_status testing."""

    def __init__(self, parse_status: str = "success"):
        self.parse_status = parse_status


class MockSummary:
    def __init__(self):
        self.export_count = 0


class MockParseResult:
    """Mock ParseResult for _result_status testing."""

    def __init__(
        self,
        is_success: bool = True,
        errors: list | None = None,
        metadata: dict | None = None,
        export_map: list | None = None,
        has_summary_or_maps: bool = True,
    ):
        self.is_success = is_success
        self.errors = errors or []
        self.metadata = metadata or {}
        self.export_map = export_map or []
        self.summary = MockSummary() if has_summary_or_maps else None
        self.name_map = ["test"] if has_summary_or_maps else None
        self.import_map = {"test": "value"} if has_summary_or_maps else None

    @property
    def graphs(self):
        return None


class TestResultStatus:
    """Test _result_status() unified status computation."""

    def test_all_exports_success_yields_success(self):
        from uasset_read.ir_builder import _result_status

        exports = [MockExportMapEntry("success") for _ in range(3)]
        result = MockParseResult(is_success=True, export_map=exports)
        assert _result_status(result) == "success"


# ---------------------------------------------------------------------------
# ExportParseStatus enum (from test_smoke_imports.py)
# ---------------------------------------------------------------------------


class TestExportParseStatus:
    """Test ExportParseStatus enum values and properties."""

    def test_success_value(self):
        from uasset_read.models.fallback import ExportParseStatus

        assert ExportParseStatus.SUCCESS.value == "success"


# ---------------------------------------------------------------------------
# ExportDependencyIR (from test_export_dependency.py)
# ---------------------------------------------------------------------------


class TestExportDependencyIR:
    """Test ExportDependencyIR construction and field access."""

    def test_basic_construction(self):
        from uasset_read.models.ir import ExportDependencyIR

        ir = ExportDependencyIR(
            export_index=0,
            serialization_before_serialization=[1, 2],
            create_before_serialization=[3],
            serialization_before_create=[],
            create_before_create=[4],
        )
        assert ir.export_index == 0
        assert ir.serialization_before_serialization == [1, 2]
        assert ir.create_before_serialization == [3]
        assert ir.serialization_before_create == []
        assert ir.create_before_create == [4]


# ---------------------------------------------------------------------------
# GatherableTextDataIR (from test_gatherable_text.py)
# ---------------------------------------------------------------------------


class TestGatherableTextDataIR:
    """Test GatherableTextDataIR construction and field access."""

    def test_basic_construction(self):
        from uasset_read.models.ir import GatherableTextDataIR

        ir = GatherableTextDataIR(
            namespace_name="Game",
            source_string="Hello World",
            source_site_contexts=[],
        )
        assert ir.namespace_name == "Game"
        assert ir.source_string == "Hello World"
        assert ir.source_site_contexts == []
