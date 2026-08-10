"""Tests for export-parsing deduplication (issue #549).

Verifies that _parse_export_properties in stages.py correctly handles:
- MemoryLimitExceeded propagation
- MemoryError graceful degradation
- Export indices filtering (lazy mode)
- store_raw_bytes functionality
- Null memory_monitor (lazy path)
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from uasset_read.pipeline.stages import _parse_export_properties
from uasset_read.memory_safety import MemoryLimitExceeded, MemoryMonitor
from uasset_read.exceptions import ParseError


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_export(idx: int, serial_size: int = 100, serial_offset: int = 0):
    """Create a mock export object."""
    export = MagicMock()
    export.serial_size = serial_size
    export.serial_offset = serial_offset
    export.object_name = f"Export_{idx}"
    export.parse_status = None
    return export


def _make_result(exports):
    """Create a mock ParseResult with export_map."""
    result = MagicMock()
    result.export_map = exports
    result.summary = MagicMock()
    result.name_map = ["TestName"]
    result.import_map = []
    result.errors = []
    return result


# ---------------------------------------------------------------------------
# Test: MemoryLimitExceeded propagation
# ---------------------------------------------------------------------------

class TestMemoryLimitExceeded:
    """Verify MemoryLimitExceeded is re-raised from _parse_export_properties."""

    def test_memory_limit_exceeded_propagates(self):
        """When memory_monitor.checkpoint raises MemoryLimitExceeded, it propagates."""
        monitor = MagicMock(spec=MemoryMonitor)
        monitor.checkpoint.side_effect = MemoryLimitExceeded(
            asset_path="test.uasset",
            stage="export[0]",
            current_rss_mb=1000.0,
            limit_mb=500.0,
        )

        export = _make_export(0)
        result = _make_result([export])

        with pytest.raises(MemoryLimitExceeded):
            _parse_export_properties(
                archive=MagicMock(),
                result=result,
                linker=None,
                tolerant=True,
                mappings_provider=None,
                game="",
                memory_monitor=monitor,
            )

    def test_memory_limit_exceeded_with_linker(self):
        """MemoryLimitExceeded propagates even with linker present."""
        monitor = MagicMock(spec=MemoryMonitor)
        monitor.checkpoint.side_effect = MemoryLimitExceeded(
            asset_path="test.uasset",
            stage="export[0]",
            current_rss_mb=1000.0,
            limit_mb=500.0,
        )

        export = _make_export(0)
        export.serial_size = 100
        result = _make_result([export])

        with pytest.raises(MemoryLimitExceeded):
            _parse_export_properties(
                archive=MagicMock(),
                result=result,
                linker=MagicMock(),
                tolerant=True,
                mappings_provider=None,
                game="",
                memory_monitor=monitor,
            )


# ---------------------------------------------------------------------------
# Test: MemoryError graceful degradation
# ---------------------------------------------------------------------------

class TestMemoryErrorGracefulDegradation:
    """Verify MemoryError sets partial status and continues in tolerant mode."""

    def test_memory_error_sets_partial_status(self):
        """MemoryError during preload sets parse_status to partial."""
        monitor = MagicMock(spec=MemoryMonitor)

        export = _make_export(0)
        export.serial_size = 100
        result = _make_result([export])

        linker = MagicMock()
        linker.preload.side_effect = MemoryError("out of memory")

        _parse_export_properties(
            archive=MagicMock(),
            result=result,
            linker=linker,
            tolerant=True,
            mappings_provider=None,
            game="",
            memory_monitor=monitor,
        )

        assert export.parse_status == "partial"
        assert export.fallback_reason == "memory_error_partial"
        assert export.properties == []

    def test_memory_error_raises_when_not_tolerant(self):
        """MemoryError re-raises when tolerant=False."""
        monitor = MagicMock(spec=MemoryMonitor)

        export = _make_export(0)
        export.serial_size = 100
        result = _make_result([export])

        linker = MagicMock()
        linker.preload.side_effect = MemoryError("out of memory")

        with pytest.raises(MemoryError):
            _parse_export_properties(
                archive=MagicMock(),
                result=result,
                linker=linker,
                tolerant=False,
                mappings_provider=None,
                game="",
                memory_monitor=monitor,
            )


# ---------------------------------------------------------------------------
# Test: Export indices filtering
# ---------------------------------------------------------------------------

class TestExportIndicesFiltering:
    """Verify export_indices parameter correctly filters which exports are parsed."""

    def test_only_specified_indices_parsed(self):
        """Only exports in export_indices are parsed; others get is_loaded=False."""
        monitor = MagicMock(spec=MemoryMonitor)

        exports = [_make_export(i) for i in range(3)]
        result = _make_result(exports)

        linker = MagicMock()
        linker._export_objects = [MagicMock() for _ in range(3)]
        for obj in linker._export_objects:
            obj.serialized_properties = []  # Empty list avoids transform extraction

        _parse_export_properties(
            archive=MagicMock(),
            result=result,
            linker=linker,
            tolerant=True,
            mappings_provider=None,
            game="",
            memory_monitor=monitor,
            export_indices={0},
        )

        # Export 0 should be parsed (properties assigned from linker)
        assert exports[0].properties == []
        assert getattr(exports[0], "is_loaded") is True

        # Exports 1 and 2 should not be parsed
        assert getattr(exports[1], "is_loaded") is False
        assert getattr(exports[2], "is_loaded") is False

    def test_none_indices_parses_all(self):
        """When export_indices is None, all exports are parsed (no filtering)."""
        monitor = MagicMock(spec=MemoryMonitor)

        exports = [_make_export(i) for i in range(3)]
        result = _make_result(exports)

        linker = MagicMock()
        linker._export_objects = [MagicMock() for _ in range(3)]
        for obj in linker._export_objects:
            obj.serialized_properties = []

        _parse_export_properties(
            archive=MagicMock(),
            result=result,
            linker=linker,
            tolerant=True,
            mappings_provider=None,
            game="",
            memory_monitor=monitor,
            export_indices=None,
        )

        for export in exports:
            # Properties assigned via linker.preload path
            assert export.properties == []

    def test_empty_indices_parses_nothing(self):
        """When export_indices is an empty set, no exports are parsed."""
        monitor = MagicMock(spec=MemoryMonitor)

        exports = [_make_export(i) for i in range(3)]
        result = _make_result(exports)

        _parse_export_properties(
            archive=MagicMock(),
            result=result,
            linker=MagicMock(),
            tolerant=True,
            mappings_provider=None,
            game="",
            memory_monitor=monitor,
            export_indices=set(),
        )

        for export in exports:
            assert getattr(export, "is_loaded") is False


# ---------------------------------------------------------------------------
# Test: store_raw_bytes
# ---------------------------------------------------------------------------

class TestStoreRawBytes:
    """Verify store_raw_bytes correctly caches serial data."""

    def test_raw_bytes_stored_for_parsed_exports(self):
        """store_raw_bytes=True stores lazy_load_archive on parsed exports."""
        monitor = MagicMock(spec=MemoryMonitor)

        export = _make_export(0, serial_size=10, serial_offset=0)
        result = _make_result([export])

        archive = MagicMock()
        archive.read_bytes.return_value = b"\x00" * 10

        linker = MagicMock()
        linker._export_objects = [MagicMock()]
        linker._export_objects[0].serialized_properties = []

        _parse_export_properties(
            archive=archive,
            result=result,
            linker=linker,
            tolerant=True,
            mappings_provider=None,
            game="",
            memory_monitor=monitor,
            export_indices={0},
            store_raw_bytes=True,
        )

        archive.seek.assert_called_with(0)
        archive.read_bytes.assert_called_with(10)
        assert getattr(export, "lazy_load_archive") == b"\x00" * 10

    def test_raw_bytes_stored_for_skipped_exports(self):
        """store_raw_bytes=True also stores raw bytes for skipped exports."""
        monitor = MagicMock(spec=MemoryMonitor)

        exports = [_make_export(i, serial_size=10, serial_offset=i * 10) for i in range(2)]
        result = _make_result(exports)

        archive = MagicMock()
        archive.read_bytes.return_value = b"\x00" * 10

        _parse_export_properties(
            archive=archive,
            result=result,
            linker=MagicMock(),
            tolerant=True,
            mappings_provider=None,
            game="",
            memory_monitor=monitor,
            export_indices={0},  # Only parse export 0
            store_raw_bytes=True,
        )

        # Both exports should have raw bytes cached
        assert getattr(exports[0], "lazy_load_archive") is not None
        assert getattr(exports[1], "lazy_load_archive") is not None

    def test_raw_bytes_not_stored_when_disabled(self):
        """store_raw_bytes=False does not call archive.seek for raw bytes."""
        monitor = MagicMock(spec=MemoryMonitor)

        export = _make_export(0, serial_size=10, serial_offset=0)
        result = _make_result([export])

        archive = MagicMock()

        _parse_export_properties(
            archive=archive,
            result=result,
            linker=MagicMock(),
            tolerant=True,
            mappings_provider=None,
            game="",
            memory_monitor=monitor,
            export_indices={0},
            store_raw_bytes=False,
        )

        # archive.seek should NOT have been called for raw bytes
        # (linker is MagicMock so no actual seek from linker.preload either)
        archive.seek.assert_not_called()

    def test_raw_bytes_error_sets_none(self):
        """Raw byte read error sets lazy_load_archive to None in tolerant mode."""
        monitor = MagicMock(spec=MemoryMonitor)

        export = _make_export(0, serial_size=10, serial_offset=0)
        result = _make_result([export])

        archive = MagicMock()
        archive.read_bytes.side_effect = OSError("read failed")

        _parse_export_properties(
            archive=archive,
            result=result,
            linker=MagicMock(),
            tolerant=True,
            mappings_provider=None,
            game="",
            memory_monitor=monitor,
            export_indices={0},
            store_raw_bytes=True,
        )

        assert getattr(export, "lazy_load_archive") is None

    def test_raw_bytes_error_raises_when_not_tolerant(self):
        """Raw byte read error raises ParseError when tolerant=False."""
        monitor = MagicMock(spec=MemoryMonitor)

        export = _make_export(0, serial_size=10, serial_offset=0)
        result = _make_result([export])

        archive = MagicMock()
        archive.read_bytes.side_effect = OSError("read failed")

        with pytest.raises(ParseError, match="Failed to read raw bytes"):
            _parse_export_properties(
                archive=archive,
                result=result,
                linker=MagicMock(),
                tolerant=False,
                mappings_provider=None,
                game="",
                memory_monitor=monitor,
                export_indices={0},
                store_raw_bytes=True,
            )


# ---------------------------------------------------------------------------
# Test: memory_monitor=None (lazy path)
# ---------------------------------------------------------------------------

class TestNullMemoryMonitor:
    """Verify _parse_export_properties works with memory_monitor=None (lazy path)."""

    def test_null_monitor_no_crash(self):
        """Passing memory_monitor=None does not crash."""
        exports = [_make_export(0, serial_size=0)]
        result = _make_result(exports)

        _parse_export_properties(
            archive=MagicMock(),
            result=result,
            linker=MagicMock(),
            tolerant=True,
            mappings_provider=None,
            game="",
            memory_monitor=None,
            export_indices=set(),
        )

        # Should complete without error; is_loaded=False since index not in empty set
        assert getattr(exports[0], "is_loaded") is False

    def test_null_monitor_with_parse_indices(self):
        """Passing memory_monitor=None with export_indices works."""
        exports = [_make_export(0, serial_size=100)]
        result = _make_result(exports)

        linker = MagicMock()
        linker._export_objects = [MagicMock()]
        linker._export_objects[0].serialized_properties = []

        _parse_export_properties(
            archive=MagicMock(),
            result=result,
            linker=linker,
            tolerant=True,
            mappings_provider=None,
            game="",
            memory_monitor=None,
            export_indices={0},
        )

        assert getattr(exports[0], "is_loaded") is True
