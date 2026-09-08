"""DataResource table parser for UE5 assets.

Reads FObjectDataResource table from DataResourceOffset.
Reference: Engine/Source/Runtime/CoreUObject/Private/UObject/ObjectResource.cpp
"""
from __future__ import annotations

import struct
from dataclasses import dataclass
from typing import BinaryIO

# Precompiled struct formats for row parsing
_ROW_V2 = struct.Struct("<IBqqqqiI")  # Flags(u32) + CookedIndex(u8) + SerialOffset(i64) + Dup(i64) + Size(i64) + Raw(i64) + Outer(i32) + Legacy(u32)
_ROW_V1 = struct.Struct("<IqqqqiI")  # same minus CookedIndex
_HEADER = struct.Struct("<Ii")  # version(u32) + count(i32)


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
    version, count = _HEADER.unpack(archive.read(_HEADER.size))

    if count < 0 or count > 10000:  # sanity check
        raise ValueError(f"Invalid DataResource count: {count}")

    row = _ROW_V2 if version >= 2 else _ROW_V1
    raw = archive.read(count * row.size)
    if len(raw) < count * row.size:
        raise ValueError(f"Short read for DataResource table: got {len(raw)} bytes, expected {count * row.size}")

    resources = []
    for fields in row.iter_unpack(raw):
        if version >= 2:
            flags, cooked_index, serial_offset, dup, size, raw_size, outer, legacy = fields
        else:
            flags, serial_offset, dup, size, raw_size, outer, legacy = fields
            cooked_index = 0
        resources.append(FObjectDataResource(
            flags=flags, cooked_index=cooked_index, serial_offset=serial_offset,
            duplicate_serial_offset=dup, serial_size=size, raw_size=raw_size,
            outer_index=outer, legacy_bulk_data_flags=legacy,
        ))

    return resources
