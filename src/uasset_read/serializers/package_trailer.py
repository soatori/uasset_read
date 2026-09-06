"""PackageTrailer parser for UE5 assets.

Reads FPackageTrailer structure from PayloadTocOffset.
Reference: Engine/Source/Runtime/CoreUObject/Private/UObject/PackageTrailer.cpp
"""
from __future__ import annotations

import struct
from dataclasses import dataclass
from typing import BinaryIO

from uasset_read.constants import (
    PACKAGE_TRAILER_HEADER_TAG,
    PACKAGE_TRAILER_FOOTER_TAG,
)


@dataclass
class FLookupTableEntry:
    """A single entry in the PayloadLookupTable."""

    identifier: bytes  # FIoHash, 20 bytes
    offset_in_file: int  # int64, relative to Payload Data start
    compressed_size: int  # uint64
    raw_size: int  # uint64
    flags: int = 0  # uint16, EPayloadFlags (v2+)
    filter_flags: int = 0  # uint16, EPayloadFilterReason (v2+)
    access_mode: int = 0  # uint8, EPayloadAccessMode (v1+)


def read_lookup_table_entry(archive: BinaryIO, version: int) -> FLookupTableEntry:
    """Read one FLookupTableEntry from the archive.

    Entry size depends on EPackageTrailerVersion:
    - v0 (INITIAL): 44 bytes (no Flags, FilterFlags, AccessMode)
    - v1 (ACCESS_PER_PAYLOAD): 45 bytes (adds AccessMode)
    - v2 (PAYLOAD_FLAGS): 49 bytes (adds Flags + FilterFlags)
    """
    identifier = archive.read(20)
    if len(identifier) < 20:
        raise ValueError(f"Short read for FIoHash: got {len(identifier)} bytes")

    offset_in_file = struct.unpack('<q', archive.read(8))[0]
    compressed_size = struct.unpack('<Q', archive.read(8))[0]
    raw_size = struct.unpack('<Q', archive.read(8))[0]

    flags = 0
    filter_flags = 0
    access_mode = 0

    if version >= 2:  # PAYLOAD_FLAGS
        flags = struct.unpack('<H', archive.read(2))[0]
        filter_flags = struct.unpack('<H', archive.read(2))[0]

    if version >= 1:  # ACCESS_PER_PAYLOAD
        access_mode = struct.unpack('<B', archive.read(1))[0]

    return FLookupTableEntry(
        identifier=identifier,
        offset_in_file=offset_in_file,
        compressed_size=compressed_size,
        raw_size=raw_size,
        flags=flags,
        filter_flags=filter_flags,
        access_mode=access_mode,
    )


@dataclass
class FPackageTrailerHeader:
    """PackageTrailer header structure."""

    tag: int  # uint64, should be PACKAGE_TRAILER_HEADER_TAG
    version: int  # uint32, EPackageTrailerVersion
    header_length: int  # uint32
    payloads_data_length: int  # uint64
    num_payloads: int  # int32


@dataclass
class FPackageTrailer:
    """Complete PackageTrailer structure."""

    header: FPackageTrailerHeader
    lookup_table: list[FLookupTableEntry]


def read_package_trailer(archive: BinaryIO, payload_toc_offset: int) -> FPackageTrailer:
    """Read FPackageTrailer from the archive.

    Args:
        archive: Seekable binary stream positioned at payload_toc_offset.
        payload_toc_offset: Offset where the trailer starts (for validation).

    Returns:
        Parsed FPackageTrailer with header and lookup table.
    """
    # Read header fields
    tag_bytes = archive.read(8)
    if len(tag_bytes) < 8:
        raise ValueError("Short read for PackageTrailer tag")
    tag = struct.unpack('<Q', tag_bytes)[0]
    if tag != PACKAGE_TRAILER_HEADER_TAG:
        raise ValueError(
            f"Invalid PackageTrailer tag: 0x{tag:016X}, "
            f"expected 0x{PACKAGE_TRAILER_HEADER_TAG:016X}"
        )

    version = struct.unpack('<I', archive.read(4))[0]
    header_length = struct.unpack('<I', archive.read(4))[0]
    payloads_data_length = struct.unpack('<Q', archive.read(8))[0]
    num_payloads = struct.unpack('<i', archive.read(4))[0]
    if num_payloads < 0:
        raise ValueError(f"Invalid num_payloads: {num_payloads}")

    header = FPackageTrailerHeader(
        tag=tag,
        version=version,
        header_length=header_length,
        payloads_data_length=payloads_data_length,
        num_payloads=num_payloads,
    )

    # Read lookup table entries
    lookup_table = []
    for _ in range(num_payloads):
        entry = read_lookup_table_entry(archive, version=version)
        lookup_table.append(entry)

    return FPackageTrailer(header=header, lookup_table=lookup_table)
