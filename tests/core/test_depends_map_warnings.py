"""Tests for DependsMap warning propagation (issue #546).

Verifies that read_depends_map emits degradation warnings when a warnings
accumulator is provided, and that _result_status surfaces DependsMap warnings
as 'partial' status.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from unittest.mock import MagicMock

import pytest

from uasset_read.serializers.package_summary import read_depends_map, PackageFileSummary
from uasset_read.models.status import _result_status
from uasset_read.constants import MAX_SAFE_COUNT


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_summary(**overrides):
    """Build a minimal PackageFileSummary with defaults suitable for DependsMap tests."""
    defaults = dict(
        tag=0,
        legacy_file_version=0,
        depends_offset=64,
        export_count=1,
        import_count=0,
    )
    defaults.update(overrides)
    return PackageFileSummary(**defaults)


def _make_archive(values):
    """Create a mock FArchive whose read_i32 pops from a deque of values."""
    archive = MagicMock()
    queue = deque(values)
    def _read_i32(key=""):
        return queue.popleft()
    archive.read_i32.side_effect = _read_i32
    return archive


# ---------------------------------------------------------------------------
# Unit tests: read_depends_map warning emission
# ---------------------------------------------------------------------------

class TestReadDependsMapWarnings:
    """read_depends_map should populate the warnings list when provided."""

    def test_skipped_entries_warning(self):
        """A dependency count exceeding MAX_SAFE_COUNT triggers a skipped-entries warning."""
        summary = _make_summary(export_count=2, import_count=0)
        # For 2 exports: first has dep_count = MAX_SAFE_COUNT+1 (skipped), second has dep_count = 0
        values = [MAX_SAFE_COUNT + 1, 0]
        archive = _make_archive(values)
        warnings = []

        result = read_depends_map(archive, summary, warnings=warnings)

        assert len(result) == 2
        assert result[0] == []  # skipped entry produces empty list
        assert result[1] == []
        assert len(warnings) == 1
        assert "DependsMap: 1/2 entries skipped" in warnings[0]

    def test_invalid_index_warning(self):
        """An out-of-range PackageIndex triggers an invalid-indices warning."""
        summary = _make_summary(export_count=1, import_count=0)
        # dep_count=1, pkg_index=5 (import_count=0, so 5 > 0 -> invalid)
        values = [1, 5]
        archive = _make_archive(values)
        warnings = []

        result = read_depends_map(archive, summary, warnings=warnings)

        assert len(result) == 1
        assert result[0] == [5]
        assert len(warnings) == 1
        assert "DependsMap: 1 PackageIndex value(s) reference" in warnings[0]

    def test_no_warning_when_clean(self):
        """Valid DependsMap data produces no warnings."""
        summary = _make_summary(export_count=1, import_count=2)
        # dep_count=1, pkg_index=1 (valid import ref, 1 <= import_count=2)
        values = [1, 1]
        archive = _make_archive(values)
        warnings = []

        result = read_depends_map(archive, summary, warnings=warnings)

        assert len(result) == 1
        assert result[0] == [1]
        assert warnings == []

    def test_none_warnings_no_crash(self):
        """read_depends_map does not crash when warnings is None."""
        summary = _make_summary(export_count=1, import_count=0)
        values = [MAX_SAFE_COUNT + 1]
        archive = _make_archive(values)

        # Should not raise
        result = read_depends_map(archive, summary, warnings=None)

        assert len(result) == 1
        assert result[0] == []


# ---------------------------------------------------------------------------
# Integration test: _result_status with DependsMap warnings
# ---------------------------------------------------------------------------

class TestResultStatusDependsMapWarnings:
    """_result_status returns 'partial' when DependsMap warnings are present."""

    def test_depends_map_warning_yields_partial(self):
        """A ParseResult with a DependsMap warning and is_success=True returns 'partial'."""
        result = MagicMock()
        result.is_success = True
        result.errors = []
        result.export_map = {}
        result.warnings = [
            "DependsMap: 1/1 entries skipped due to invalid dependency count"
        ]
        result.metadata = {}
        result.diagnostics = []
        result.decompiled_functions = []
        result.translation_status = None
        result.bytecode_status = None

        status = _result_status(result)
        assert status == "partial"

    def test_no_depends_map_warning_yields_success(self):
        """A clean ParseResult with is_success=True returns 'success'."""
        result = MagicMock()
        result.is_success = True
        result.errors = []
        result.export_map = {}
        result.warnings = []
        result.metadata = {}
        result.diagnostics = []
        result.decompiled_functions = []
        result.translation_status = None
        result.bytecode_status = None

        status = _result_status(result)
        assert status == "success"
