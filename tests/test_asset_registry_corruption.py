"""Regression tests for corrupted AssetRegistryData degradation (Task #450).

When AssetRegistryData is malformed/truncated, the result status must be
'partial' — not 'success'. Degradation must surface through warnings.
"""
import struct
from io import BytesIO

import pytest

from uasset_read.parsers.asset_registry_parser import (
    read_asset_registry_data,
    AssetRegistryData,
)
from uasset_read.models.status import _result_status


class MockArchive:
    """Minimal FArchive mock supporting the read methods used by AssetRegistryData."""

    def __init__(self, data: bytes):
        self._stream = BytesIO(data)
        self._total_size = len(data)

    def read(self, size: int) -> bytes:
        return self._stream.read(size)

    def read_i32(self) -> int:
        raw = self._stream.read(4)
        if len(raw) < 4:
            raise struct.error("not enough data for int32")
        return struct.unpack('<i', raw)[0]

    def read_i64(self) -> int:
        raw = self._stream.read(8)
        if len(raw) < 8:
            raise struct.error("not enough data for int64")
        return struct.unpack('<q', raw)[0]

    def read_fstring(self) -> str:
        length = self.read_i32()
        if length == 0:
            return ""
        if length < 0:
            raise struct.error(f"negative fstring length: {length}")
        raw = self._stream.read(length)
        if len(raw) < length:
            raise struct.error("truncated fstring")
        # UE fstrings include a null terminator in the length
        text = raw[:-1].decode('utf-8') if raw.endswith(b'\x00') else raw.decode('utf-8')
        return text

    def tell(self) -> int:
        return self._stream.tell()

    def seek(self, pos: int):
        self._stream.seek(pos)

    def total_size(self) -> int:
        return self._total_size

    def set_byte_swapping(self, enabled: bool):
        pass


def _build_valid_object_data() -> bytes:
    """Build bytes for one AssetRegistryObjectData entry."""
    parts = []
    # object_path (FString)
    path = b"/Game/Content/MyAsset"
    parts.append(struct.pack('<i', len(path) + 1))
    parts.append(path + b'\x00')
    # object_class_name (FString)
    cls = b"Blueprint"
    parts.append(struct.pack('<i', len(cls) + 1))
    parts.append(cls + b'\x00')
    # tag_count = 0
    parts.append(struct.pack('<i', 0))
    return b''.join(parts)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestCorruptedAssetRegistryData:
    """Verify that malformed AssetRegistryData surfaces as 'partial' status."""

    def _make_archive(self, data: bytes) -> MockArchive:
        """Create a mock archive where asset_registry_data_offset=1 lands at data[0]."""
        # Pad with 1 byte so offset=1 points to the real data
        return MockArchive(b'\x00' + data)

    def test_truncated_after_object_count_marks_corrupted(self):
        """ObjectCount claims 1 object but data is truncated — must mark corrupted."""
        data = struct.pack('<q', -1) + struct.pack('<i', 1)
        archive = self._make_archive(data)

        result = read_asset_registry_data(
            archive,
            asset_registry_data_offset=1,
            file_version_ue4=510,
            is_cooked=False,
        )

        assert result is not None
        assert result.corrupted is True
        # The single object could not be read, so objects list may be empty
        assert isinstance(result.objects, list)

    def test_truncated_mid_object_marks_corrupted(self):
        """ObjectCount claims 1 object but only partial object data present."""
        data = struct.pack('<q', -1) + struct.pack('<i', 1)
        # Only 2 bytes — not enough for even a single i32 FString length
        data += b'\x01\x00'
        archive = self._make_archive(data)

        result = read_asset_registry_data(
            archive,
            asset_registry_data_offset=1,
            file_version_ue4=510,
            is_cooked=False,
        )

        assert result is not None
        assert result.corrupted is True

    def test_valid_data_not_corrupted(self):
        """A well-formed AssetRegistryData must not be marked corrupted."""
        obj_data = _build_valid_object_data()
        data = struct.pack('<q', -1) + struct.pack('<i', 1) + obj_data
        archive = self._make_archive(data)

        result = read_asset_registry_data(
            archive,
            asset_registry_data_offset=1,
            file_version_ue4=510,
            is_cooked=False,
        )

        assert result is not None
        assert result.corrupted is False
        assert len(result.objects) == 1

    def test_negative_object_count_not_corrupted(self):
        """Negative ObjectCount returns empty result without corruption flag."""
        data = struct.pack('<q', -1) + struct.pack('<i', -1)
        archive = self._make_archive(data)

        result = read_asset_registry_data(
            archive,
            asset_registry_data_offset=1,
            file_version_ue4=510,
            is_cooked=False,
        )

        assert result is not None
        assert result.corrupted is False
        assert len(result.objects) == 0

    def test_zero_offset_returns_none(self):
        """Zero offset returns None (no data to parse)."""
        buf = b'\x00' * 16
        archive = MockArchive(buf)

        result = read_asset_registry_data(
            archive,
            asset_registry_data_offset=0,
            file_version_ue4=510,
            is_cooked=False,
        )

        assert result is None


class TestStatusSurfaceDegradation:
    """Verify that _result_status returns 'partial' when AssetRegistryData is corrupted."""

    def test_corrupted_asset_registry_yields_partial_status(self):
        """A ParseResult with an AssetRegistryData corruption warning must have 'partial' status."""

        class FakeResult:
            is_success = True
            errors = []
            warnings = ["AssetRegistryData is corrupted — only partial data was recovered"]
            metadata = {}
            diagnostics = []
            summary = None

        status = _result_status(FakeResult())
        assert status == "partial"

    def test_clean_result_is_success(self):
        """A clean ParseResult (no errors, no corruption) must be 'success'."""

        class FakeResult:
            is_success = True
            errors = []
            warnings = []
            metadata = {}
            diagnostics = []
            summary = None

        status = _result_status(FakeResult())
        assert status == "success"

    def test_other_warning_does_not_affect_status(self):
        """An unrelated warning should not change status to partial."""

        class FakeResult:
            is_success = True
            errors = []
            warnings = ["Some unrelated warning"]
            metadata = {}
            diagnostics = []
            summary = None

        status = _result_status(FakeResult())
        assert status == "success"
