"""Tests for PackageTrailer constants and parsing."""

import pytest
from uasset_read.constants import (
    PACKAGE_TRAILER_HEADER_TAG,
    UE5_PAYLOAD_TOC,
    UE5_DATA_RESOURCES,
)


def test_header_tag_value():
    assert PACKAGE_TRAILER_HEADER_TAG == 0xD1C43B2E80A5F697


def test_payload_toc_version():
    assert UE5_PAYLOAD_TOC == 1002


def test_data_resources_version():
    assert UE5_DATA_RESOURCES == 1009


def test_package_document_has_trailer_field():
    from uasset_read.models.document import PackageDocument

    doc = PackageDocument(source=None, package=None)
    assert hasattr(doc, "package_trailer")
    assert doc.package_trailer is None


# --- FLookupTableEntry tests ---

import struct
from uasset_read.archive import ByteArchive


def test_read_lookup_table_entry_v0():
    """Version 0: 44 bytes (no Flags, FilterFlags, AccessMode)."""
    from uasset_read.serializers.package_trailer import read_lookup_table_entry

    # Build 44-byte entry: Identifier(20) + OffsetInFile(8) + CompressedSize(8) + RawSize(8)
    entry_bytes = b"\x00" * 20  # FIoHash
    entry_bytes += struct.pack("<q", 1024)  # OffsetInFile
    entry_bytes += struct.pack("<Q", 2048)  # CompressedSize
    entry_bytes += struct.pack("<Q", 4096)  # RawSize

    archive = ByteArchive(entry_bytes)
    entry = read_lookup_table_entry(archive, version=0)

    assert entry.identifier == b"\x00" * 20
    assert entry.offset_in_file == 1024
    assert entry.compressed_size == 2048
    assert entry.raw_size == 4096
    assert entry.access_mode == 0  # default


def test_read_lookup_table_entry_v2():
    """Version 2: 49 bytes (adds Flags, FilterFlags, AccessMode)."""
    from uasset_read.serializers.package_trailer import read_lookup_table_entry

    entry_bytes = b"\x00" * 20  # FIoHash
    entry_bytes += struct.pack("<q", 2048)  # OffsetInFile
    entry_bytes += struct.pack("<Q", 4096)  # CompressedSize
    entry_bytes += struct.pack("<Q", 8192)  # RawSize
    entry_bytes += struct.pack("<H", 0x0001)  # Flags
    entry_bytes += struct.pack("<H", 0x0002)  # FilterFlags
    entry_bytes += struct.pack("<B", 1)  # AccessMode (Referenced)

    archive = ByteArchive(entry_bytes)
    entry = read_lookup_table_entry(archive, version=2)

    assert entry.offset_in_file == 2048
    assert entry.compressed_size == 4096
    assert entry.raw_size == 8192
    assert entry.flags == 0x0001
    assert entry.filter_flags == 0x0002
    assert entry.access_mode == 1


# --- FPackageTrailer tests ---


def test_read_package_trailer_header():
    """Parse FPackageTrailer header with 2 entries."""
    from uasset_read.serializers.package_trailer import read_package_trailer

    # Build trailer: Header(28 bytes static) + 2 entries(49 bytes each v2)
    trailer_data = bytearray()

    # FHeader
    trailer_data += struct.pack("<Q", 0xD1C43B2E80A5F697)  # Tag
    trailer_data += struct.pack("<I", 2)  # Version (PAYLOAD_FLAGS)
    trailer_data += struct.pack("<I", 28 + 2 * 49)  # HeaderLength
    trailer_data += struct.pack("<Q", 4096)  # PayloadsDataLength
    trailer_data += struct.pack("<i", 2)  # NumPayloads

    # Entry 1 (49 bytes v2)
    trailer_data += b"\x01" * 20  # Identifier
    trailer_data += struct.pack("<q", 0)  # OffsetInFile
    trailer_data += struct.pack("<Q", 1024)  # CompressedSize
    trailer_data += struct.pack("<Q", 2048)  # RawSize
    trailer_data += struct.pack("<H", 0)  # Flags
    trailer_data += struct.pack("<H", 0)  # FilterFlags
    trailer_data += struct.pack("<B", 0)  # AccessMode

    # Entry 2 (49 bytes v2)
    trailer_data += b"\x02" * 20  # Identifier
    trailer_data += struct.pack("<q", 1024)  # OffsetInFile
    trailer_data += struct.pack("<Q", 512)  # CompressedSize
    trailer_data += struct.pack("<Q", 1024)  # RawSize
    trailer_data += struct.pack("<H", 0)  # Flags
    trailer_data += struct.pack("<H", 0)  # FilterFlags
    trailer_data += struct.pack("<B", 0)  # AccessMode

    archive = ByteArchive(bytes(trailer_data))
    trailer = read_package_trailer(archive)

    assert trailer.header.tag == 0xD1C43B2E80A5F697
    assert trailer.header.version == 2
    assert trailer.header.num_payloads == 2
    assert trailer.header.payloads_data_length == 4096
    assert len(trailer.lookup_table) == 2
    assert trailer.lookup_table[0].compressed_size == 1024
    assert trailer.lookup_table[1].offset_in_file == 1024


def test_read_package_trailer_invalid_tag():
    """Reject trailer with wrong header tag."""
    from uasset_read.serializers.package_trailer import read_package_trailer

    trailer_data = struct.pack("<Q", 0xDEADBEEF)  # Wrong tag
    trailer_data += b"\x00" * 20  # padding

    archive = ByteArchive(trailer_data)
    with pytest.raises(ValueError, match="Invalid PackageTrailer tag"):
        read_package_trailer(archive)


def test_serializers_exports():
    """Verify new parsers are importable from serializers package (import is the check)."""
    from uasset_read.serializers.data_resource import read_data_resource_table
    from uasset_read.serializers.package_trailer import read_package_trailer

    assert callable(read_package_trailer)
    assert callable(read_data_resource_table)
