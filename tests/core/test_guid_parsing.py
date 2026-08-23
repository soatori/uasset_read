"""Tests for GUID parsing robustness (issue #585)."""

from __future__ import annotations

import io
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest


# ---------------------------------------------------------------------------
# _handle_node_guid
# ---------------------------------------------------------------------------

def _make_tag(size: int, value_end_offset: int = 16) -> SimpleNamespace:
    return SimpleNamespace(size=size, value_end_offset=value_end_offset)


class _ArchiveStub:
    """Minimal archive stub for _handle_node_guid tests."""

    def __init__(self, data: bytes):
        self._stream = io.BytesIO(data)

    def read_bytes(self, n: int) -> bytes:
        return self._stream.read(n)

    def tell(self) -> int:
        return self._stream.tell()

    def seek(self, pos: int) -> None:
        self._stream.seek(pos)


def _import_handle_node_guid():
    from uasset_read.serializers.graph_node import _handle_node_guid
    return _handle_node_guid


class TestHandleNodeGuid:
    """Tests for _handle_node_guid robustness."""

    def test_normal_16_bytes(self):
        handle = _import_handle_node_guid()
        data = bytes(range(16))
        archive = _ArchiveStub(data)
        tag = _make_tag(size=16)
        result = handle(archive, tag, None, None, None, None, None)
        assert result == {"node_guid": data.hex()}

    def test_normal_16_bytes_uppercase(self):
        handle = _import_handle_node_guid()
        data = b"\xAB\xCD\xEF\x01" * 4
        archive = _ArchiveStub(data)
        tag = _make_tag(size=16)
        result = handle(archive, tag, None, None, None, None, None)
        assert result == {"node_guid": data.hex()}

    def test_short_data_padded_to_32(self):
        handle = _import_handle_node_guid()
        data = b"\x01\x02\x03"
        archive = _ArchiveStub(data)
        tag = _make_tag(size=16)
        result = handle(archive, tag, None, None, None, None, None)
        # Should be padded to 32 hex chars
        assert result["node_guid"] == data.hex().ljust(32, "0")
        assert len(result["node_guid"]) == 32

    def test_zero_size_tag_returns_empty(self):
        handle = _import_handle_node_guid()
        archive = _ArchiveStub(b"")
        tag = _make_tag(size=0)
        result = handle(archive, tag, None, None, None, None, None)
        assert result == {}

    def test_archive_seek_to_value_end_offset(self):
        handle = _import_handle_node_guid()
        # 20 bytes so seek to value_end_offset=20 skips past
        data = b"\x00" * 20
        archive = _ArchiveStub(data)
        tag = _make_tag(size=16, value_end_offset=20)
        result = handle(archive, tag, None, None, None, None, None)
        assert archive.tell() == 20

    def test_read_failure_returns_zero_guid(self):
        """Archive that raises on read_bytes → fallback to zero GUID."""
        handle = _import_handle_node_guid()

        class _FailArchive:
            def read_bytes(self, n):
                raise IOError("simulated read failure")

            def tell(self):
                return 0

            def seek(self, pos):
                pass

        archive = _FailArchive()
        tag = _make_tag(size=16)
        result = handle(archive, tag, None, None, None, None, None)
        assert result == {"node_guid": "0" * 32}


# ---------------------------------------------------------------------------
# _extract_graph_properties — GraphGuid branch
# ---------------------------------------------------------------------------

class TestExtractGraphGuid:
    """Tests for GraphGuid extraction in _extract_graph_properties."""

    @staticmethod
    def _make_graph_export(props):
        export = SimpleNamespace(properties=props)
        return export

    def _extract(self, props):
        from uasset_read.serializers.graph import _extract_graph_properties
        return _extract_graph_properties(self._make_graph_export(props))

    def test_normal_guid(self):
        props = [
            {"name": "GraphGuid", "value": {"fields": {"A": 0x01020304, "B": 0x05060708, "C": 0x090A0B0C, "D": 0x0D0E0F10}}}
        ]
        _, _, guid = self._extract(props)
        assert isinstance(guid, str)
        assert len(guid) == 28  # UE format: 14 bytes = 28 hex chars

    def test_none_field_values(self):
        props = [
            {"name": "GraphGuid", "value": {"fields": {"A": None, "B": None, "C": None, "D": None}}}
        ]
        _, _, guid = self._extract(props)
        # Should fallback to zero GUID, not crash
        assert guid == "0" * 28

    def test_missing_fields_key(self):
        props = [
            {"name": "GraphGuid", "value": {"fields": {}}}
        ]
        _, _, guid = self._extract(props)
        # Empty fields dict is falsy → graph_guid stays empty
        assert guid == ""

    def test_no_fields_key(self):
        props = [
            {"name": "GraphGuid", "value": {}}
        ]
        _, _, guid = self._extract(props)
        assert guid == ""

    def test_non_dict_value(self):
        props = [
            {"name": "GraphGuid", "value": "not_a_dict"}
        ]
        _, _, guid = self._extract(props)
        assert guid == ""

    def test_string_field_values(self):
        props = [
            {"name": "GraphGuid", "value": {"fields": {"A": "bad", "B": "bad", "C": "bad", "D": "bad"}}}
        ]
        _, _, guid = self._extract(props)
        # Should fallback, not crash
        assert guid == ""

    def test_large_integer_field_values(self):
        """Values larger than 32-bit should be masked correctly."""
        props = [
            {"name": "GraphGuid", "value": {"fields": {"A": 0xFFFFFFFF + 1, "B": 0, "C": 0, "D": 0}}}
        ]
        _, _, guid = self._extract(props)
        assert len(guid) == 28

    def test_negative_field_values(self):
        """Negative values should be masked to unsigned."""
        props = [
            {"name": "GraphGuid", "value": {"fields": {"A": -1, "B": 0, "C": 0, "D": 0}}}
        ]
        _, _, guid = self._extract(props)
        # -1 & 0xFFFFFFFF == 0xFFFFFFFF, should produce valid hex
        assert len(guid) == 28

    def test_float_field_values(self):
        props = [
            {"name": "GraphGuid", "value": {"fields": {"A": 1.5, "B": 0, "C": 0, "D": 0}}}
        ]
        _, _, guid = self._extract(props)
        # float & 0xFFFFFFFF would fail, int() converts first
        assert guid == "" or len(guid) == 28
