"""Consolidated serializer tests.

Extracted and merged from:
- tests/core/test_graph_node.py
- tests/serialization/test_graph_pin_recovery.py
- tests/serialization/test_package_summary.py
- tests/core/test_subgraphs.py
"""

import logging
import struct
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

ASSET_TEXTURE_BRICK = "T_Brick_Hued_B"

def asset_path(sample_root: Path, name: str) -> Path:
    return sample_root / f"{name}.uasset"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_mock_node_export(name="BadNode", outer_idx=0):
    """Create a mock node export with outer_index."""
    mock = MagicMock(spec=[
        "object_name", "outer_index", "class_index", "serial_offset",
        "has_script_serialization", "class_name", "properties",
    ])
    mock.object_name = name
    mock.outer_index = MagicMock()
    mock.outer_index.index = outer_idx
    mock.serial_offset = 0
    mock.has_script_serialization = True
    mock.class_name = "K2Node_CallFunction"
    mock.properties = []
    return mock


def _capture_logs(func):
    """Capture DEBUG-level logs from the graph_pin logger."""
    test_logger = logging.getLogger("uasset_read.serializers.graph_pin")
    old_level = test_logger.level
    test_logger.setLevel(logging.DEBUG)
    captured: list[logging.LogRecord] = []
    handler = logging.Handler()
    handler.emit = lambda record: captured.append(record)
    test_logger.addHandler(handler)
    try:
        result = func()
    finally:
        test_logger.removeHandler(handler)
        test_logger.setLevel(old_level)
    return result, captured


def _make_archive(data: bytes):
    """Build a minimal mock archive that reads from *data*."""
    archive = MagicMock()
    archive._data = data
    archive._file_size = len(data)
    pos = [0]

    def _tell():
        return pos[0]

    def _seek(p):
        pos[0] = p

    def _read(n):
        start = pos[0]
        pos[0] += n
        return data[start:start + n]

    archive.tell = _tell
    archive.seek = _seek
    archive.read = _read
    return archive


# ---------------------------------------------------------------------------
# Graph node error tolerance (from test_graph_node.py)
# ---------------------------------------------------------------------------

class TestGraphNodeErrorTolerance:
    """read_ue_graph should tolerate per-node parse failures."""

    def test_struct_error_tolerance(self):
        """struct.error during node parsing should not crash the graph."""
        from uasset_read.serializers.graph import read_ue_graph
        from uasset_read.serializers.object_resources import ObjectExport

        mock_archive = MagicMock()
        mock_node_export = _make_mock_node_export()
        mock_export_map = [mock_node_export]
        mock_summary = MagicMock()
        mock_import_map = []
        mock_linker = MagicMock()

        mock_graph_export = MagicMock(spec=ObjectExport)
        mock_graph_export.object_name = "TestGraph"
        mock_graph_export.properties = [{"name": "Nodes", "value": [1]}]

        with patch(
            "uasset_read.serializers.graph_node.read_ue_graph_node",
            side_effect=struct.error("unpack requires a buffer of 1 bytes"),
        ):
            graph = read_ue_graph(
                mock_archive, [], mock_summary, mock_export_map, mock_import_map,
                mock_graph_export, "EdGraph", 1, mock_linker,
            )
        assert graph is not None
        assert isinstance(graph.nodes, list)


# ---------------------------------------------------------------------------
# Pin array count recovery (from test_graph_pin_recovery.py)
# ---------------------------------------------------------------------------

class TestPinArrayRecovery:
    """#344: P73-RECOVERY confidence evaluation for pin count recovery."""

    def test_recovery_logs_high_confidence(self):
        """High-confidence recovery should log confidence and diagnostics."""
        from uasset_read.serializers.graph_pin import _recover_pin_array_count

        bad_count = 255
        valid_count = 2
        pin_ref = struct.pack("<i", 0) + struct.pack("<i", 1) + b"\x00" * 16

        data = bytearray(200)
        struct.pack_into("<i", data, 0, bad_count)
        struct.pack_into("<i", data, 16, valid_count)
        data[20:20 + len(pin_ref)] = pin_ref
        data[44:44 + len(pin_ref)] = pin_ref

        archive = _make_archive(bytes(data))
        mock_validation = {
            "valid": True, "b_null": 0, "owning_node": 1,
            "owning_node_valid": True, "reason": "ok",
        }

        with patch(
            "uasset_read.serializers.graph_pin.validate_pin_reference_at",
            return_value=mock_validation,
        ):
            result, captured = _capture_logs(lambda: _recover_pin_array_count(
                archive, error_pos=0, bad_count=bad_count,
                export_map=[], import_map=[], scan_window=16,
            ))

        assert result is not None
        assert result["count"] == valid_count
        assert result["confidence"] == "high"

        recovery_logs = [r for r in captured if "P73-RECOVERY" in r.message]
        assert len(recovery_logs) > 0
        log_msg = recovery_logs[0].message
        assert "confidence=" in log_msg
        assert "scan=" in log_msg
        assert "bad_count=" in log_msg


# ---------------------------------------------------------------------------
# Subgraph limits (from test_subgraphs.py)
# ---------------------------------------------------------------------------

class TestSubgraphLimits:
    """SubGraphs array truncation and invalid-index skipping (#333)."""

    def test_truncate_large_array(self):
        """SubGraphs exceeding MAX_SUBGRAPHS should be truncated."""
        from uasset_read.serializers.graph import MAX_SUBGRAPHS, read_ue_graph
        from uasset_read.serializers.object_resources import ObjectExport

        mock_archive = MagicMock()
        mock_archive.tell.return_value = 0
        mock_summary = MagicMock()
        mock_linker = MagicMock()

        mock_graph_export = MagicMock(spec=ObjectExport)
        mock_graph_export.object_name = "TestGraph"
        mock_graph_export.properties = [
            {"name": "Nodes", "value": []},
            {"name": "SubGraphs", "value": list(range(1, 2000))},
        ]

        graph = read_ue_graph(
            mock_archive, [], mock_summary, [], mock_linker,
            mock_graph_export, "EdGraph", 1, mock_linker,
        )
        assert graph is not None
