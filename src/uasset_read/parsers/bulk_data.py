"""BulkData header parsing for cooked .uasset files.

Parses FBulkDataHeader from UE source:
- Engine/Source/Runtime/Core/Public/Serialization/BulkData.h
- Engine/Source/Runtime/Engine/Private/TextureCube.cpp (for Texture2D bulk layout)
"""

from __future__ import annotations

import struct
from dataclasses import dataclass
from typing import Optional


# BulkData flags from BulkData.h
BULKDATA_None = 0x00
BULKDATA_CompressedZlib = 0x02
BULKDATA_CompressedOodle = 0x04
BULKDATA_MemoryMapped = 0x08
BULKDATA_SerializeAsVoid = 0x10
BULKDATA_SkipBulkDataCompress = 0x20
BULKDATA_Unused = 0x40  # Unused in newer UE versions
BULKDATA_ContainsEmbeddedPkgs = 0x80
BULKDATA_OptionalPayload = 0x100
BULKDATA_MemoryMappedFromFrozenFile = 0x200
BULKDATA_ShortForwardReference = 0x400
BULKDATA_CustomChunk = 0x800
BULKDATA_ForceUsage = 0x1000


@dataclass(frozen=True)
class BulkDataHeader:
    """Parsed BulkData header from a cooked .uasset export."""

    flags: int
    element_count: int
    size_on_disk: int
    offset: int
    compression_type: Optional[str] = None

    @property
    def is_compressed(self) -> bool:
        return bool(self.flags & (BULKDATA_CompressedZlib | BULKDATA_CompressedOodle))

    @property
    def is_memory_mapped(self) -> bool:
        return bool(self.flags & BULKDATA_MemoryMapped)


def parse_bulk_data_header(data: bytes) -> BulkDataHeader:
    """Parse a BulkData header from raw bytes.

    Args:
        data: At least 16 bytes containing the header.

    Returns:
        Parsed BulkDataHeader.

    Raises:
        ValueError: If data is too short or invalid.
    """
    if len(data) < 16:
        raise ValueError(f"BulkData header requires 16 bytes, got {len(data)}")

    flags, element_count, size_on_disk, offset = struct.unpack_from("<IIII", data)

    # Determine compression type from flags
    compression_type: str | None = None
    if flags & BULKDATA_CompressedZlib:
        compression_type = "zlib"
    elif flags & BULKDATA_CompressedOodle:
        compression_type = "oodle"

    return BulkDataHeader(
        flags=flags,
        element_count=element_count,
        size_on_disk=size_on_disk,
        offset=offset,
        compression_type=compression_type,
    )
