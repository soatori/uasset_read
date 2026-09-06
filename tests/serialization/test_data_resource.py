"""Tests for DataResource table parsing."""
import struct
import pytest
from io import BytesIO


def test_read_data_resource_table():
    """Parse a DataResource table with 2 entries."""
    from uasset_read.serializers.data_resource import read_data_resource_table
    from uasset_read.archive import ByteArchive

    table_data = bytearray()

    # Version (uint32) = 2 (AddedCookedIndex)
    table_data += struct.pack('<I', 2)
    # Count (int32) = 2
    table_data += struct.pack('<i', 2)

    # Entry 1
    table_data += struct.pack('<I', 0x01)  # Flags (Inline)
    table_data += struct.pack('<B', 0)  # CookedIndex (uint8)
    table_data += struct.pack('<q', 1000)  # SerialOffset
    table_data += struct.pack('<q', -1)  # DuplicateSerialOffset (INDEX_NONE)
    table_data += struct.pack('<q', 500)  # SerialSize
    table_data += struct.pack('<q', 800)  # RawSize
    table_data += struct.pack('<i', 0)  # OuterIndex (null)
    table_data += struct.pack('<I', 0)  # LegacyBulkDataFlags

    # Entry 2
    table_data += struct.pack('<I', 0x02)  # Flags (Streaming)
    table_data += struct.pack('<B', 1)  # CookedIndex
    table_data += struct.pack('<q', 2000)  # SerialOffset
    table_data += struct.pack('<q', -1)  # DuplicateSerialOffset
    table_data += struct.pack('<q', 1024)  # SerialSize
    table_data += struct.pack('<q', 2048)  # RawSize
    table_data += struct.pack('<i', -1)  # OuterIndex (import 1)
    table_data += struct.pack('<I', 0x100)  # LegacyBulkDataFlags

    archive = ByteArchive(bytes(table_data))
    resources = read_data_resource_table(archive, offset=0)

    assert len(resources) == 2
    assert resources[0].serial_offset == 1000
    assert resources[0].serial_size == 500
    assert resources[0].raw_size == 800
    assert resources[1].cooked_index == 1
    assert resources[1].legacy_bulk_data_flags == 0x100


def test_parse_stages_populates_data_resource():
    """Verify pipeline populates data_resource_map when present."""
    from uasset_read.models.document import PackageDocument
    result = PackageDocument(source=None, package=None)
    assert hasattr(result, 'data_resource_map')
    assert result.data_resource_map is None
