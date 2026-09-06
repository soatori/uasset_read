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
