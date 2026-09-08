"""PackageTrailer parser for UE5 assets.

Reads FPackageTrailer structure from PayloadTocOffset.
Reference: Engine/Source/Runtime/CoreUObject/Private/UObject/PackageTrailer.cpp
"""

from __future__ import annotations

import struct
from dataclasses import dataclass
from uasset_read.archive import ArchiveLike

from uasset_read.constants import PACKAGE_TRAILER_HEADER_TAG


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


# Precompiled struct formats
_HEADER_FMT = struct.Struct("<QIIQi")  # tag(u64) + version(u32) + header_length(u32) + payloads_data_length(u64) + num_payloads(i32)
_ENTRY_HEAD = struct.Struct("<20sQQQ")  # identifier(20) + offset(i64) + compressed(u64) + raw(u64)
_ENTRY_TAIL_V2 = struct.Struct("<HHB")  # flags(u16) + filter_flags(u16) + access_mode(u8)
_ENTRY_TAIL_V1 = struct.Struct("<B")  # access_mode(u8)


def read_lookup_table_entry(archive: ArchiveLike, version: int) -> FLookupTableEntry:
    """Read one FLookupTableEntry from the archive.

    Entry size depends on EPackageTrailerVersion:
    - v0 (INITIAL): 44 bytes (no Flags, FilterFlags, AccessMode)
    - v1 (ACCESS_PER_PAYLOAD): 45 bytes (adds AccessMode)
    - v2 (PAYLOAD_FLAGS): 49 bytes (adds Flags + FilterFlags)
    """
    head = _ENTRY_HEAD.unpack(archive.read(_ENTRY_HEAD.size))
    identifier, offset_in_file, compressed_size, raw_size = head

    flags = 0
    filter_flags = 0
    access_mode = 0

    if version >= 2:  # PAYLOAD_FLAGS
        flags, filter_flags, access_mode = _ENTRY_TAIL_V2.unpack(archive.read(_ENTRY_TAIL_V2.size))
    elif version >= 1:  # ACCESS_PER_PAYLOAD
        (access_mode,) = _ENTRY_TAIL_V1.unpack(archive.read(_ENTRY_TAIL_V1.size))

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


def read_package_trailer(archive: ArchiveLike) -> FPackageTrailer:
    """Read FPackageTrailer from the archive.

    Args:
        archive: Seekable binary stream positioned at the trailer start.

    Returns:
        Parsed FPackageTrailer with header and lookup table.
    """
    # Read tag first for early validation
    tag = struct.unpack("<Q", archive.read(8))[0]
    if tag != PACKAGE_TRAILER_HEADER_TAG:
        raise ValueError(f"Invalid PackageTrailer tag: 0x{tag:016X}, expected 0x{PACKAGE_TRAILER_HEADER_TAG:016X}")

    version, header_length, payloads_data_length, num_payloads = struct.unpack("<IIQi", archive.read(20))
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
