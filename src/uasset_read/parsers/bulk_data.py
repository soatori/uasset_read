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


def extract_bulk_data_descriptors(
    serial_data: bytes,
    base_offset: int = 0,
    export_index: int = 0,
) -> list[BulkDataHeader]:
    """Extract BulkData descriptors from export serial data.

    Scans for BulkData headers at the end of export serial regions.
    This is a heuristic based on UE's save format where BulkData
    descriptors appear after tagged properties.

    Args:
        serial_data: Raw bytes of the export serial region.
        base_offset: Starting offset of this region in the package.
        export_index: Index of the export (for header IDs).

    Returns:
        List of BulkDataHeader objects found.
    """
    descriptors: list[BulkDataHeader] = []

    if len(serial_data) < 16:
        return descriptors

    # Look for BulkData headers at the very end of the serial data
    # A BulkData header is 16 bytes: flags, element_count, size_on_disk, offset
    # BulkData descriptors appear at the end of export serial regions, after
    # all tagged properties. We only check the last 16 bytes for a single header.
    try:
        header = parse_bulk_data_header(serial_data[-16:])

        # Validate the header looks reasonable
        if header.size_on_disk > 0 and header.element_count > 0:
            # Additional validation: flags should be within known range
            if header.flags <= 0x1FFF:
                descriptors.append(header)
    except (ValueError, struct.error):
        pass

    return descriptors
