"""#341 PropertyTag early corruption recovery tests.

Verifies that when a PropertyTag read fails due to corrupted data,
the parser recovers by scanning forward for the next valid PropertyTag
boundary instead of skipping only 1 byte (which caused 9,340 property skips).

Test strategy:
1. Create a byte sequence with a corrupted PropertyTag followed by a valid one
2. Verify the parser recovers and parses the second property correctly
3. Verify that PropertyFallback is still recorded for skipped properties
4. Verify the scan distance is reasonable (not just 1 byte)
"""
from __future__ import annotations

import struct
from io import BytesIO

import pytest

from uasset_read.archive import FArchive
from uasset_read.bounded_events import BoundedSet
from uasset_read.models.fallback import PropertyFallback
from uasset_read.models.properties import PropertyTag, PropertyValue
from uasset_read.parsers.property_parser import (
    _try_recover_property_tag,
    _MAX_RECOVERY_SCAN,
    parse_properties_from_export,
)
from uasset_read.serializers.object_resources import ObjectExport, PackageIndex


def _make_archive(data: bytes, tolerant: bool = True) -> FArchive:
    """Create FArchive from raw bytes for testing."""
    archive = FArchive.__new__(FArchive)
    archive._stream = BytesIO(data)
    archive._file_size = len(data)
    archive._byte_swapping = False
    archive._use_mmap = False
    archive._mmap = None
    archive._tolerant = tolerant
    archive._file = BytesIO(data)
    archive._hex_view_enabled = False
    archive._hex_view_entries = []
    archive._hex_view_context = ""
    archive._diagnostics = []
    archive._logger = __import__("logging").getLogger("test")
    archive._name_map = None
    archive._name_warnings_seen = BoundedSet()
    archive._recovery_attempts = 0
    archive._recovery_successes = 0
    archive._recovery_failures = 0
    return archive


def _make_export(serial_offset: int = 0, serial_size: int = 1024) -> ObjectExport:
    """Create test ObjectExport."""
    return ObjectExport(
        class_index=PackageIndex(-1),
        super_index=PackageIndex(-1),
        outer_index=PackageIndex(0),
        object_name="TestExport",
        object_flags=0,
        serial_size=serial_size,
        serial_offset=serial_offset,
    )


def _make_fname(index: int, number: int = 0) -> bytes:
    """Create FName bytes (4-byte index + 4-byte number)."""
    return struct.pack("<II", index, number)


def _make_int32(value: int) -> bytes:
    """Create int32 bytes."""
    return struct.pack("<i", value)


def _make_legacy_tag(name_idx: int, type_idx: int, size: int, value_data: bytes = b"") -> bytes:
    """Build a legacy PropertyTag: name(FName) + type(FName) + size(i32) + array_index(i32) + flags(u8) + value_data."""
    return _make_fname(name_idx, 0) + _make_fname(type_idx, 0) + _make_int32(size) + _make_int32(0) + b"\x00" + value_data


def _make_ue53_tag(name_idx: int, type_idx: int, size: int, value_data: bytes = b"") -> bytes:
    """Build a UE5.3+ PropertyTag with name(FName) + type_tree(FName + inner_count) + size(i32) + value_data."""
    return (
        _make_fname(name_idx, 0)
        + _make_fname(type_idx, 0)
        + _make_int32(0)  # inner_count = 0 (no children)
        + _make_int32(size)
        + value_data
    )


class TestPropertyTagRecovery341:
    """#341: PropertyTag early corruption recovery."""

    def test_scan_max_increased(self):
        """Recovery scan budget should be at least 2048 bytes."""
        assert _MAX_RECOVERY_SCAN >= 2048

    def test_try_recover_finds_valid_tag_after_corruption(self):
        """_try_recover_property_tag should find a valid PropertyTag after corrupted data."""
        name_map = ["Corrupted", "ValidProp", "IntProperty"]
        corruption = b"\xFF" * 16

        # Valid legacy PropertyTag: name(8) + type_fname(8) + size(4) + value(4)
        valid_tag = _make_legacy_tag(1, 2, 4, _make_int32(42))

        data = corruption + valid_tag
        archive = _make_archive(data, tolerant=True)
        archive._file_version_ue5 = 1011  # legacy format (< 1012)

        archive.seek(0)
        recovered = _try_recover_property_tag(
            archive, name_map, max_scan=64, property_end=None,
        )

        assert recovered is True
        assert archive.tell() == 16

    def test_try_recover_finds_tag_in_ue53_format(self):
        """_try_recover_property_tag should find valid tags in UE5.3+ format."""
        name_map = ["Corrupted", "ValidProp", "IntProperty"]
        corruption = b"\xFF" * 8

        # UE5.3+ PropertyTag: name(8) + type_tree(8) + size(4) + value(4)
        valid_tag = _make_ue53_tag(1, 2, 4, _make_int32(42))

        data = corruption + valid_tag
        archive = _make_archive(data, tolerant=True)
        archive._file_version_ue5 = 1012  # UE5.3+ format

        archive.seek(0)
        recovered = _try_recover_property_tag(
            archive, name_map, max_scan=64, property_end=None,
        )

        assert recovered is True
        assert archive.tell() == 8

    def test_try_recover_rejects_invalid_fname_index(self):
        """Recovery should skip positions with out-of-range FName indices."""
        name_map = ["ValidProp", "IntProperty"]
        invalid_fname = struct.pack("<II", 99, 0)  # index=99, out of range
        valid_tag = _make_legacy_tag(0, 1, 4, _make_int32(10))

        data = invalid_fname + valid_tag
        archive = _make_archive(data, tolerant=True)
        archive._file_version_ue5 = 1011

        archive.seek(0)
        recovered = _try_recover_property_tag(
            archive, name_map, max_scan=64, property_end=None,
        )

        assert recovered is True
        assert archive.tell() == 8

    def test_try_recover_rejects_empty_name(self):
        """Recovery should skip positions where name is empty."""
        name_map = ["", "ValidProp", "IntProperty"]
        empty_name = struct.pack("<II", 0, 0)
        valid_tag = _make_legacy_tag(1, 2, 4, _make_int32(10))

        data = empty_name + valid_tag
        archive = _make_archive(data, tolerant=True)
        archive._file_version_ue5 = 1011

        archive.seek(0)
        recovered = _try_recover_property_tag(
            archive, name_map, max_scan=64, property_end=None,
        )

        assert recovered is True
        assert archive.tell() == 8

    def test_try_recover_rejects_none_name(self):
        """Recovery should skip positions where name is 'None'."""
        name_map = ["None", "ValidProp", "IntProperty"]
        none_name = struct.pack("<II", 0, 0)
        valid_tag = _make_legacy_tag(1, 2, 4, _make_int32(10))

        data = none_name + valid_tag
        archive = _make_archive(data, tolerant=True)
        archive._file_version_ue5 = 1011

        archive.seek(0)
        recovered = _try_recover_property_tag(
            archive, name_map, max_scan=64, property_end=None,
        )

        assert recovered is True
        assert archive.tell() == 8

    def test_try_recover_rejects_unknown_type(self):
        """Recovery should skip positions where type is not a known property type."""
        name_map = ["ValidProp", "UnknownType"]
        valid_tag = _make_legacy_tag(0, 1, 4, _make_int32(10))

        data = valid_tag
        archive = _make_archive(data, tolerant=True)
        archive._file_version_ue5 = 1011

        archive.seek(0)
        recovered = _try_recover_property_tag(
            archive, name_map, max_scan=64, property_end=None,
        )

        assert recovered is False

    def test_try_recover_rejects_negative_size(self):
        """Recovery should skip positions where size is negative."""
        name_map = ["ValidProp", "IntProperty"]
        valid_tag = _make_legacy_tag(0, 1, -1)  # negative size

        data = valid_tag
        archive = _make_archive(data, tolerant=True)
        archive._file_version_ue5 = 1011

        archive.seek(0)
        recovered = _try_recover_property_tag(
            archive, name_map, max_scan=64, property_end=None,
        )

        assert recovered is False

    def test_try_recover_rejects_size_exceeding_file(self):
        """Recovery should skip positions where size exceeds file size."""
        name_map = ["ValidProp", "IntProperty"]
        valid_tag = _make_legacy_tag(0, 1, 99999)  # size exceeds file

        data = valid_tag + b"\x00" * 10
        archive = _make_archive(data, tolerant=True)
        archive._file_version_ue5 = 1011

        archive.seek(0)
        recovered = _try_recover_property_tag(
            archive, name_map, max_scan=64, property_end=None,
        )

        assert recovered is False

    def test_try_recover_returns_false_when_nothing_found(self):
        """Recovery should return False when no valid tag is found."""
        name_map = ["ValidProp", "IntProperty"]
        data = b"\xFF" * 100
        archive = _make_archive(data, tolerant=True)
        archive._file_version_ue5 = 1011

        archive.seek(0)
        recovered = _try_recover_property_tag(
            archive, name_map, max_scan=64, property_end=None,
        )

        assert recovered is False
        assert archive.tell() == 0

    def test_full_parse_recovery_after_corrupted_tag(self):
        """Recovery function correctly advances past corrupted data to valid tag."""
        name_map = ["None", "Corrupted", "ValidProp", "IntProperty"]

        # Place cursor after some garbage bytes, then a valid tag
        garbage = b"\x00\x01\x02\x03\x04\x05\x06\x07\x08\x09"
        valid_tag = _make_legacy_tag(2, 3, 4, _make_int32(42))

        data = garbage + valid_tag
        archive = _make_archive(data, tolerant=True)
        archive._file_version_ue5 = 1011
        archive.seek(0)

        recovered = _try_recover_property_tag(
            archive, name_map, max_scan=_MAX_RECOVERY_SCAN, property_end=None,
        )

        assert recovered is True
        # Cursor should have advanced past the garbage to find the valid tag at offset 10
        assert archive.tell() == len(garbage)

    def test_full_parse_size_exceeded_recovery(self):
        """Full parse: when a tag's size is garbage (too large), recovery finds the next valid tag."""
        # Corrupted tag: valid FName "Corrupted" but truncated type overlaps with
        # the next tag's name, producing a huge size value (size_exceeded).
        name_map = ["None", "Corrupted", "ValidProp", "IntProperty"]

        corrupted_tag = (
            _make_fname(1, 0)  # name: "Corrupted" at offset 0
            + b"\x00\x01"  # truncated type at offset 8-9 (only 2 bytes)
        )
        # The valid tag starts at offset 10
        valid_tag = _make_legacy_tag(2, 3, 4, _make_int32(42))
        # Terminator
        terminator = (
            _make_fname(0, 0)  # name: "None"
            + _make_fname(3, 0)  # type: "IntProperty"
            + _make_int32(0)  # size: 0
        )

        # Use version < 1011 to avoid _handle_serialization_control consuming the first byte
        data = corrupted_tag + valid_tag + terminator
        archive = _make_archive(data, tolerant=True)
        archive._file_version_ue5 = 1010

        summary = type("Summary", (), {"package_flags": 0, "file_version_ue5": 1010})()
        export = _make_export(serial_offset=0, serial_size=len(data))

        result = parse_properties_from_export(
            export, archive, summary,
            name_map=name_map, export_map=[], tolerant=True,
        )

        assert isinstance(result, list)
        # Should have: PropertyFallback (from corrupted tag) + valid IntProperty
        fallbacks = [p for p in result if isinstance(p.value, PropertyFallback)]
        valid = [p for p in result if not isinstance(p.value, PropertyFallback)]
        assert len(fallbacks) >= 1, f"Expected at least 1 PropertyFallback, got {len(fallbacks)}"
        assert len(valid) >= 1, f"Expected at least 1 valid property, got {len(valid)}"
        # Verify the fallback has expected fields
        fb = fallbacks[0].value
        assert hasattr(fb, "name")
        assert hasattr(fb, "type")
        assert hasattr(fb, "reason")
        # Verify the valid property was parsed correctly
        assert valid[0].name == "ValidProp"
        assert valid[0].type == "IntProperty"
        assert valid[0].value == 42

    def test_full_parse_recovery_preserves_fallback(self):
        """Full parse: PropertyFallback is recorded for a corrupted tag that is skipped."""
        name_map = ["None", "Corrupted", "ValidProp", "IntProperty"]

        corrupted_tag = (
            _make_fname(1, 0)  # name: "Corrupted"
            + b"\x00\x01"  # truncated type
        )
        valid_tag = _make_legacy_tag(2, 3, 4, _make_int32(100))
        terminator = (
            _make_fname(0, 0)
            + _make_fname(3, 0)
            + _make_int32(0)
        )

        # Use version < 1011 to avoid _handle_serialization_control consuming the first byte
        data = corrupted_tag + valid_tag + terminator
        archive = _make_archive(data, tolerant=True)
        archive._file_version_ue5 = 1010

        summary = type("Summary", (), {"package_flags": 0, "file_version_ue5": 1010})()
        export = _make_export(serial_offset=0, serial_size=len(data))

        result = parse_properties_from_export(
            export, archive, summary,
            name_map=name_map, export_map=[], tolerant=True,
        )

        assert isinstance(result, list)
        fallbacks = [p for p in result if isinstance(p.value, PropertyFallback)]
        assert len(fallbacks) >= 1
        fb = fallbacks[0].value
        assert fb.name == "Corrupted"

    def test_recovery_scan_distance_not_just_one_byte(self):
        """Recovery should scan more than 1 byte when possible."""
        name_map = ["ValidProp", "IntProperty"]
        corruption = b"\xFF" * 32
        valid_tag = _make_legacy_tag(0, 1, 4, _make_int32(99))

        data = corruption + valid_tag
        archive = _make_archive(data, tolerant=True)
        archive._file_version_ue5 = 1011

        archive.seek(0)
        recovered = _try_recover_property_tag(
            archive, name_map, max_scan=64, property_end=None,
        )

        assert recovered is True
        scan_distance = archive.tell() - 0
        assert scan_distance == 32, f"Expected scan distance 32, got {scan_distance}"
        assert scan_distance > 1, "Recovery should scan more than 1 byte"

    def test_recovery_within_property_end_boundary(self):
        """Recovery should work within property_end boundary."""
        name_map = ["ValidProp", "IntProperty"]
        corruption = b"\xFF" * 16
        valid_tag = _make_legacy_tag(0, 1, 4, _make_int32(55))

        data = corruption + valid_tag + b"\x00" * 100
        archive = _make_archive(data, tolerant=True)
        archive._file_version_ue5 = 1011

        archive.seek(0)
        recovered = _try_recover_property_tag(
            archive, name_map, max_scan=64, property_end=40,
        )

        assert recovered is True
        assert archive.tell() == 16
