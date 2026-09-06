"""DataResource table parser for UE5 assets.

Reads FObjectDataResource table from DataResourceOffset.
Reference: Engine/Source/Runtime/CoreUObject/Private/UObject/ObjectResource.cpp
"""
from __future__ import annotations

import struct
from dataclasses import dataclass
from typing import BinaryIO


@dataclass
class FObjectDataResource:
    """A single data resource entry."""
    flags: int  # uint32, EObjectDataResourceFlags
    cooked_index: int  # uint8 (v2+)
    serial_offset: int  # int64
    duplicate_serial_offset: int  # int64
    serial_size: int  # int64
    raw_size: int  # int64
    outer_index: int  # int32, FPackageIndex encoded
    legacy_bulk_data_flags: int  # uint32


def read_data_resource_table(archive: BinaryIO, offset: int) -> list[FObjectDataResource]:
    """Read FObjectDataResource table from the archive.

    Args:
        archive: Seekable binary stream.
        offset: Byte offset where the table starts.

    Returns:
        List of parsed FObjectDataResource entries.
    """
    archive.seek(offset)

    # Read version and count
    version = struct.unpack('<I', archive.read(4))[0]
    count = struct.unpack('<i', archive.read(4))[0]

    if count < 0 or count > 10000:  # sanity check
        raise ValueError(f"Invalid DataResource count: {count}")

    resources = []
    for _ in range(count):
        flags = struct.unpack('<I', archive.read(4))[0]

        # CookedIndex only present in version >= 2 (AddedCookedIndex)
        cooked_index = 0
        if version >= 2:
            cooked_index = struct.unpack('<B', archive.read(1))[0]

        serial_offset = struct.unpack('<q', archive.read(8))[0]
        duplicate_serial_offset = struct.unpack('<q', archive.read(8))[0]
        serial_size = struct.unpack('<q', archive.read(8))[0]
        raw_size = struct.unpack('<q', archive.read(8))[0]
        outer_index = struct.unpack('<i', archive.read(4))[0]
        legacy_bulk_data_flags = struct.unpack('<I', archive.read(4))[0]

        resources.append(FObjectDataResource(
            flags=flags,
            cooked_index=cooked_index,
            serial_offset=serial_offset,
            duplicate_serial_offset=duplicate_serial_offset,
            serial_size=serial_size,
            raw_size=raw_size,
            outer_index=outer_index,
            legacy_bulk_data_flags=legacy_bulk_data_flags,
        ))

    return resources
