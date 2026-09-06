"""Tests for BulkData header parsing."""

from __future__ import annotations

import struct

import pytest

from uasset_read.parsers.bulk_data import BulkDataHeader, parse_bulk_data_header


def test_bulk_data_header_basic():
    """Test parsing a basic BulkData header."""
    # FBulkDataHeader format: Flags (uint32), ElementCount (uint32),
    # SizeOnDisk (uint32), Offset (uint32)
    flags = 0x01  # BULKDATA_None
    element_count = 1024
    size_on_disk = 2048
    offset = 4096

    data = struct.pack("<IIII", flags, element_count, size_on_disk, offset)
    header = parse_bulk_data_header(data)

    assert header.flags == flags
    assert header.element_count == element_count
    assert header.size_on_disk == size_on_disk
    assert header.offset == offset
    assert header.compression_type is None  # No compression flags


def test_bulk_data_header_compressed():
    """Test parsing a compressed BulkData header."""
    flags = 0x02  # BULKDATA_CompressedZlib
    element_count = 2048
    size_on_disk = 4096
    offset = 8192

    data = struct.pack("<IIII", flags, element_count, size_on_disk, offset)
    header = parse_bulk_data_header(data)

    assert header.flags == flags
    assert header.compression_type == "zlib"


def test_bulk_data_header_oodle_compression():
    """Test parsing an Oodle-compressed BulkData header."""
    flags = 0x04  # BULKDATA_CompressedOodle
    element_count = 512
    size_on_disk = 1024
    offset = 0

    data = struct.pack("<IIII", flags, element_count, size_on_disk, offset)
    header = parse_bulk_data_header(data)

    assert header.flags == flags
    assert header.compression_type == "oodle"
    assert header.is_compressed is True


def test_bulk_data_header_too_short():
    """Test that a too-short buffer raises ValueError."""
    with pytest.raises(ValueError, match="requires 16 bytes"):
        parse_bulk_data_header(b"\x00" * 10)


def test_bulk_data_header_is_compressed_false():
    """Test is_compressed property returns False when no compression flags."""
    header = BulkDataHeader(
        flags=0x00, element_count=1, size_on_disk=1, offset=0
    )
    assert header.is_compressed is False


def test_bulk_data_header_is_memory_mapped():
    """Test is_memory_mapped property."""
    header = BulkDataHeader(
        flags=0x08, element_count=1, size_on_disk=1, offset=0
    )
    assert header.is_memory_mapped is True

    header2 = BulkDataHeader(
        flags=0x00, element_count=1, size_on_disk=1, offset=0
    )
    assert header2.is_memory_mapped is False
