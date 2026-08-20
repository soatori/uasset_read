"""
Pak file data structures.

Mirrors UE engine IPlatformFilePak.h structures: FPakInfo, FPakEntry, FPakDirectoryEntry, etc.
"""
import struct
from dataclasses import dataclass, field
from typing import BinaryIO

from uasset_read.exceptions import ParseError
from uasset_read.constants import MAX_FSTRING_LENGTH
from uasset_read.pak.constants import (
    PAK_FILE_MAGIC,
    PAK_FILE_MAGICS,
    PakFileVersion,
    PAK_INFO_SIZES,
    Flag_Encrypted,
)
from uasset_read.pak.game_versions import detect_game_from_magic, EGame


# ============================================================================
# FString Reader (shared utility)
# ============================================================================

def read_fstring(stream: BinaryIO, version: int = 0) -> str:
    """Read a UE FString (length-prefixed, null-terminated).

    Args:
        stream: Binary stream
        version: Pak file version (>= 12 may use FUtf8String)

    Returns:
        Decoded string

    UE FString format:
    - int32 length: positive=ANSI, negative=UTF-16, 0=empty string
    - length bytes of data + 1 null terminator byte (ANSI)
    - abs(length)*2 bytes data + 2 null terminator bytes (UTF-16)
    - version >= 12: uint32 length (unsigned), UTF-8 encoded
    """
    if version >= PakFileVersion.Utf8PakDirectory:
        # FUtf8String: uint32 length + UTF-8 bytes + 1 null terminator
        length_bytes = stream.read(4)
        if len(length_bytes) < 4:
            raise ParseError("Unexpected end of stream reading FUtf8String length")
        length = struct.unpack('<I', length_bytes)[0]
        if length == 0:
            # Read null terminator
            stream.read(1)
            return ""
        if length > MAX_FSTRING_LENGTH:
            raise ParseError(
                f"FUtf8String length {length} exceeds maximum {MAX_FSTRING_LENGTH}"
            )
        data = stream.read(length)
        stream.read(1)  # null terminator
        return data.decode('utf-8', errors='replace').rstrip('\x00')

    # Standard FString: int32 length
    length_bytes = stream.read(4)
    if len(length_bytes) < 4:
        raise ParseError("Unexpected end of stream reading FString length")
    length = struct.unpack('<i', length_bytes)[0]

    if length == 0:
        return ""

    if length < 0:
        # UTF-16
        utf16_len = -length * 2
        if utf16_len > MAX_FSTRING_LENGTH:
            raise ParseError(
                f"UTF-16 string length {utf16_len} exceeds maximum {MAX_FSTRING_LENGTH}"
            )
        data = stream.read(utf16_len)
        if len(data) < utf16_len:
            raise ParseError(
                f"UTF-16 string truncated: read {len(data)} < expected {utf16_len} bytes"
            )
        stream.read(2)  # null terminator (2 bytes for UTF-16)
        return data.decode('utf-16-le', errors='replace').rstrip('\x00')
    else:
        # ANSI / UTF-8
        if length > MAX_FSTRING_LENGTH:
            raise ParseError(
                f"ANSI string length {length} exceeds maximum {MAX_FSTRING_LENGTH}"
            )
        data = stream.read(length)
        if len(data) < length:
            raise ParseError(
                f"ANSI string truncated: read {len(data)} < expected {length} bytes"
            )
        stream.read(1)  # null terminator
        return data.decode('ascii', errors='replace').rstrip('\x00')


# ============================================================================
# FPakCompressedBlock
# ============================================================================

@dataclass
class FPakCompressedBlock:
    """Compressed block info.

    compressed_start/compressed_end are converted to absolute file offsets after parsing.
    For version < 5 (RelativeChunkOffsets), entry.offset must be added after loading.
    """
    compressed_start: int  # int64 — absolute file offset
    compressed_end: int    # int64 — exclusive end offset


# ============================================================================
# FPakEntry
# ============================================================================

@dataclass
class FPakEntry:
    """Pak file entry.

    Describes offset, size, compression, encryption, and hash info for a single file in a pak.
    Corresponds to the FPakEntry struct in UE IPlatformFilePak.h.
    """
    offset: int = 0                      # int64 — entry data start offset
    uncompressed_size: int = 0           # int64 — decompressed size
    size: int = 0                        # int64 — compressed size (== uncompressed_size when not compressed)
    compression_method_index: int = 0    # uint32 — index in FPakInfo.compression_methods
    is_encrypted: bool = False           # whether encrypted
    is_compressed: bool = False          # whether compressed (derived from compression_method_index > 0)
    compression_block_count: int = 0     # uint16/uint32 depending on version
    compression_block_size: int = 0      # uint32 — uncompressed size per compression block
    compression_blocks: list = field(default_factory=list)  # list[FPakCompressedBlock]
    hash: bytes = b""                    # 20 bytes — SHA1 of uncompressed data
    flags: int = 0                       # raw flags
    is_deleted: bool = False             # whether deleted (derived from flags)
    serialized_size: int = 0             # entry size for v10+ bitfield encoding

    @classmethod
    def deserialize_legacy(cls, stream: BinaryIO, version: int) -> "FPakEntry":
        """Deserialize a full FPakEntry from stream (legacy format, version < 10).

        Serialization order (UE FPakEntry::Serialize, IPlatformFilePak.h:521-570):
        - Offset (int64)
        - Size (int64) — compressed size
        - UncompressedSize (int64)
        - CompressionMethodIndex (uint32)
        - [Timestamp (int64) — version <= 1 only]
        - Hash [20 bytes] — always present
        - [version >= 3 (CompressionEncryption)]:
          - CompressionBlocks [TArray: int32 count + N * (int64, int64)] — only when compression_method_index != 0
          - Flags (uint8)
          - CompressionBlockSize (uint32)
        """
        entry = cls()

        entry.offset = struct.unpack('<q', stream.read(8))[0]
        entry.size = struct.unpack('<q', stream.read(8))[0]
        entry.uncompressed_size = struct.unpack('<q', stream.read(8))[0]
        entry.compression_method_index = struct.unpack('<I', stream.read(4))[0]

        # Timestamp removed in version 2 (UE: Version <= PakFile_Version_Initial)
        if version < PakFileVersion.NoTimestamps:
            stream.read(8)

        # Hash — UE writes Hash before CompressionBlocks
        entry.hash = stream.read(20)

        # [version >= CompressionEncryption (3)]: CompressionBlocks, Flags, CompressionBlockSize
        if version >= PakFileVersion.CompressionEncryption:
            if entry.compression_method_index != 0:
                # CompressionBlocks: int32 count + N * (int64 compressed_start, int64 compressed_end)
                if version < PakFileVersion.FNameBasedCompressionMethod:
                    entry.compression_block_count = struct.unpack('<H', stream.read(2))[0]
                else:
                    entry.compression_block_count = struct.unpack('<I', stream.read(4))[0]

                for _ in range(entry.compression_block_count):
                    block_start = struct.unpack('<q', stream.read(8))[0]
                    block_end = struct.unpack('<q', stream.read(8))[0]
                    entry.compression_blocks.append(
                        FPakCompressedBlock(compressed_start=block_start, compressed_end=block_end)
                    )

            # Flags — uint8 (1 byte)
            entry.flags = struct.unpack('<B', stream.read(1))[0]

            # CompressionBlockSize — uint32
            entry.compression_block_size = struct.unpack('<I', stream.read(4))[0]

        entry.is_compressed = entry.compression_method_index > 0
        return entry

    @classmethod
    def decode_bitfield(cls, data: bytes, offset: int, pak_info: "FPakInfo") -> tuple["FPakEntry", int]:
        """Decode a v10+ bitfield-encoded FPakEntry.

        UE read order:
        bitfield -> CompressionBlockSize(if 0x3F) -> Offset -> UncompressedSize -> Size

        Bitfield layout (UE PakFile.cpp DecodePakEntry):
        - Bit 31: Offset fits in 32-bit
        - Bit 30: UncompressedSize fits in 32-bit
        - Bit 29: Size fits in 32-bit
        - Bits 23-28: Compression method index (6 bits)
        - Bit 22: Encrypted flag
        - Bits 6-21: Compression block count (16 bits)
        - Bits 0-5: Compression block size index (6 bits, 0x3F=read from stream)

        Args:
            data: Byte stream containing the bitfield
            offset: Starting offset of the bitfield in data
            pak_info: FPakInfo instance providing the compression method table

        Returns:
            (FPakEntry, bytes_consumed)
        """
        entry = cls()
        start_offset = offset

        # Read bitfield (4 bytes, little-endian)
        bitfield = struct.unpack_from('<I', data, offset)[0]
        offset += 4

        # Decode fields from bitfield
        offset_fits_32 = bool(bitfield & (1 << 31))
        uncompressed_size_fits_32 = bool(bitfield & (1 << 30))
        size_fits_32 = bool(bitfield & (1 << 29))
        entry.compression_method_index = (bitfield >> 23) & 0x3F
        entry.is_encrypted = bool(bitfield & (1 << 22))
        entry.compression_block_count = (bitfield >> 6) & 0xFFFF
        block_size_index = bitfield & 0x3F

        # UE order: CompressionBlockSize before Offset
        if block_size_index == 0x3F:
            entry.compression_block_size = struct.unpack_from('<I', data, offset)[0]
            offset += 4
        else:
            entry.compression_block_size = block_size_index << 11

        # Offset
        if offset_fits_32:
            entry.offset = struct.unpack_from('<I', data, offset)[0]
            offset += 4
        else:
            entry.offset = struct.unpack_from('<q', data, offset)[0]
            offset += 8

        # UncompressedSize
        if uncompressed_size_fits_32:
            entry.uncompressed_size = struct.unpack_from('<I', data, offset)[0]
            offset += 4
        else:
            entry.uncompressed_size = struct.unpack_from('<q', data, offset)[0]
            offset += 8

        # Size (compressed)
        entry.size = entry.uncompressed_size
        if entry.compression_method_index > 0:
            if size_fits_32:
                entry.size = struct.unpack_from('<I', data, offset)[0]
                offset += 4
            else:
                entry.size = struct.unpack_from('<q', data, offset)[0]
                offset += 8

        entry.is_compressed = entry.compression_method_index > 0
        entry.flags = Flag_Encrypted if entry.is_encrypted else 0
        entry.serialized_size = offset - start_offset

        return entry, entry.serialized_size


# ============================================================================
# FPakInfo
# ============================================================================

@dataclass
class FPakInfo:
    """Pak file trailer info structure.

    FPakInfo is located at the end of the file, detected by reverse-scanning
    different version sizes from the trailer. New fields are prepended before
    Magic to maintain backward compatibility.

    Corresponds to FPakInfo::Serialize in UE IPlatformFilePak.h.
    """
    magic: int = PAK_FILE_MAGIC
    version: int = 0
    index_offset: int = 0          # int64 — Primary Index offset in the file
    index_size: int = 0            # int64 — Index blob size
    index_hash: bytes = b""        # 20 bytes — SHA1 of index blob
    encryption_key_guid: bytes = b""  # 16 bytes, version >= 7
    encrypted_index: bool = False     # version >= 7
    compression_methods: list = field(default_factory=list)  # up to 5 names, version >= 8
    index_is_frozen: bool = False   # version 9 only
    detected_game: int = EGame.UNKNOWN  # detected game identifier

    @classmethod
    def _serialized_size(cls, version: int) -> int:
        """Return the serialized size of FPakInfo for the given version."""
        if version <= 6:
            return PAK_INFO_SIZES["v1-6"]
        elif version == 7:
            return PAK_INFO_SIZES["v7"]
        elif version == 8:
            return PAK_INFO_SIZES["v8"]
        elif version == 9:
            return PAK_INFO_SIZES["v9"]
        else:
            return PAK_INFO_SIZES["v10+"]

    @classmethod
    def deserialize(cls, stream: BinaryIO, file_size: int) -> "FPakInfo":
        """Detect and deserialize FPakInfo from the file trailer.

        Algorithm: iterate from latest version (12) to earliest version (1),
        compute pos = file_size - serialized_size, seek to pos,
        read 4 bytes to check if magic matches.

        Args:
            stream: File stream
            file_size: Total file size

        Returns:
            Parsed FPakInfo instance

        Raises:
            ParseError: If no version matches
        """
        # Version groups by serialized size, ordered latest first within each size
        version_groups = [
            (12, 11, 10),  # 221 bytes
            (9,),           # 222 bytes
            (8,),           # 221 bytes (same size as v10+, but different structure)
            (7,),           # 61 bytes
            (6, 5, 4, 3, 2, 1),  # 45 bytes
        ]

        for group in version_groups:
            info_size = cls._serialized_size(group[0])
            pos = file_size - info_size
            if pos < 0:
                continue

            # bEncryptedIndex is always serialized (1 byte), unconditionally per UE source.
            # For v7+, EncryptionKeyGuid(16) is prepended before bEncryptedIndex.
            # Magic position: v7+ at offset 17, v1-6 at offset 1
            magic_offset_in_trailer = (
                17 if group[0] >= PakFileVersion.EncryptionKeyGuid else 1
            )

            stream.seek(pos + magic_offset_in_trailer)
            raw = stream.read(4)
            if len(raw) < 4:
                continue

            magic = struct.unpack('<I', raw)[0]
            # Check standard magic and game-specific magic values
            if magic not in PAK_FILE_MAGICS:
                continue

            # Detect game identifier
            detected_game = detect_game_from_magic(magic)

            # Magic matched — read version field to determine exact version
            version_field = struct.unpack('<i', stream.read(4))[0]

            # Find matching version in this group
            matched_version = None
            for v in group:
                if v >= PakFileVersion.PathHashIndex:
                    if version_field >= PakFileVersion.PathHashIndex:
                        matched_version = v
                        break
                elif version_field == v:
                    matched_version = v
                    break

            if matched_version is None:
                continue

            version = matched_version

            # Deserialize from the beginning of the trailer
            stream.seek(pos)
            info = cls()
            info.version = version
            info.detected_game = detected_game

            # EncryptionKeyGuid (version >= 7 only, prepended before bEncryptedIndex)
            if version >= PakFileVersion.EncryptionKeyGuid:
                info.encryption_key_guid = stream.read(16)

            # bEncryptedIndex: always serialized, unconditionally (UE IPlatformFilePak.h)
            info.encrypted_index = struct.unpack('<B', stream.read(1))[0] != 0

            # Core fields (always present)
            info.magic = struct.unpack('<I', stream.read(4))[0]
            info.version = struct.unpack('<i', stream.read(4))[0]
            info.index_offset = struct.unpack('<q', stream.read(8))[0]
            info.index_size = struct.unpack('<q', stream.read(8))[0]
            info.index_hash = stream.read(20)

            # FrozenIndex (version 9 only)
            if version == 9:
                info.index_is_frozen = struct.unpack('<B', stream.read(1))[0] != 0

            # Compression methods (version >= 8)
            if version >= PakFileVersion.FNameBasedCompressionMethod:
                info.compression_methods = []
                for _ in range(5):
                    name_bytes = stream.read(32)
                    name_str = name_bytes.split(b'\x00')[0].decode('ascii', errors='replace')
                    if name_str:
                        info.compression_methods.append(name_str)

            return info

        raise ParseError("Unknown .pak format — no valid FPakInfo trailer found")


# ============================================================================
# FPakDirectoryEntry
# ============================================================================

@dataclass
class FPakDirectoryEntry:
    """Directory tree node.

    Represents a file entry under a directory path.
    """
    path: str                    # directory path
    filename: str                # filename
    entry: FPakEntry             # actual entry data
