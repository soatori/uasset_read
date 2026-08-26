from __future__ import annotations

"""IoStore core data structures — mirrors IoStore structures"""
from dataclasses import dataclass, field
from enum import IntEnum, IntFlag
from typing import BinaryIO, List
import struct


# ============================================================================
# Enum definitions
# ============================================================================


class EIoStoreTocVersion(IntEnum):
    """IoStore TOC version enum"""

    Invalid = 0
    Initial = 1
    DirectoryIndex = 2
    PartitionSize = 3
    PerfectHash = 4
    PerfectHashWithOverflow = 5
    OnDemandMetaData = 6
    RemovedOnDemandMetaData = 7
    ReplaceIoChunkHashWithIoHash = 8
    LatestPlusOne = 9
    Latest = LatestPlusOne - 1


class EIoContainerFlags(IntFlag):
    """IoStore container flags"""

    None_ = 0
    Compressed = 1 << 0
    Encrypted = 1 << 1
    Signed = 1 << 2
    Indexed = 1 << 3
    OnDemand = 1 << 4


class EIoChunkType(IntEnum):
    """IoStore chunk type

    UE5 IoStore-specific types. UE4 uses a different storage mechanism.
    Types 0-6 are defined in UE5.0+, types 7+ were added in later versions.
    """

    Invalid = 0
    ExportBundleData = 1  # UE5.0+: Export bundle data
    BulkData = 2  # UE5.0+: Bulk data
    OptionalBulkData = 3  # UE5.0+: Optional bulk data
    MemoryMappedBulkData = 4  # UE5.0+: Memory-mapped bulk data
    ScriptObjects = 5  # UE5.0+: Script objects
    ContainerHeader = 6  # UE5.0+: Container header
    ExternalFile = 7  # UE5.1+: External file reference
    ShaderCodeLibrary = 8  # UE5.1+: Shader code library
    ShaderCode = 9  # UE5.1+: Shader code
    PackageStoreEntry = 10  # UE5.2+: Package store entry
    DerivedData = 11  # UE5.3+: Derived data
    EditorDerivedData = 12  # UE5.4+: Editor derived data
    PackageResource = 13  # UE5.5+: Package resource


class EIoStoreTocReadOptions(IntFlag):
    """IoStore TOC read options"""

    Default = 0
    ReadDirectoryIndex = 1 << 0
    ReadTocMeta = 1 << 1
    ReadAll = ReadDirectoryIndex | ReadTocMeta


# ============================================================================
# Core data structures
# ============================================================================


@dataclass
class FIoChunkId:
    """IoStore Chunk identifier (12 bytes).

    Struct layout (UE FIoChunkId):
    - Bytes 0-7: ChunkId (uint64, little-endian)
    - Bytes 8-9: ChunkIndex (uint16, big-endian)
    - Byte 10: ChunkGroup (uint8)
    - Byte 11: ChunkType (uint8, EIoChunkType)

    Comparison uses all 12 bytes, consistent with UE source.
    """

    bytes: bytes  # 12 bytes

    @property
    def id(self) -> int:
        """Return 64-bit ID (low 8 bytes)"""
        return struct.unpack("<Q", self.bytes[:8])[0]

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, FIoChunkId):
            return NotImplemented
        return self.bytes == other.bytes

    def __hash__(self) -> int:
        return hash(self.bytes)


@dataclass
class FIoOffsetAndLength:
    """Offset and length (10-byte big-endian encoding, 5-byte offset + 5-byte length)

    FIoOffsetAndLength — IoStore standard format
    """

    offset: int
    length: int

    @staticmethod
    def from_bytes(data: bytes) -> FIoOffsetAndLength:
        """Unpack from 10 bytes (big-endian)"""
        if len(data) < 10:
            raise ValueError("FIoOffsetAndLength requires at least 10 bytes")
        # Offset: bytes 0-4, big-endian
        offset = (data[0] << 32) | (data[1] << 24) | (data[2] << 16) | (data[3] << 8) | data[4]
        # Length: bytes 5-9, big-endian
        length = (data[5] << 32) | (data[6] << 24) | (data[7] << 16) | (data[8] << 8) | data[9]
        return FIoOffsetAndLength(offset=offset, length=length)

    @staticmethod
    def from_stream(stream: BinaryIO) -> FIoOffsetAndLength:
        """Read 10 bytes from stream"""
        data = stream.read(10)
        return FIoOffsetAndLength.from_bytes(data)


@dataclass
class FIoDirectoryIndexEntry:
    """Directory index entry"""

    name: int
    first_child_entry: int
    next_sibling_entry: int
    first_file_entry: int

    @staticmethod
    def deserialize(stream: BinaryIO) -> FIoDirectoryIndexEntry:
        """Deserialize from stream"""
        data = stream.read(16)
        if len(data) < 16:
            raise ValueError("Unexpected end of stream")

        name, first_child_entry, next_sibling_entry, first_file_entry = struct.unpack("<IIII", data)

        return FIoDirectoryIndexEntry(
            name=name,
            first_child_entry=first_child_entry,
            next_sibling_entry=next_sibling_entry,
            first_file_entry=first_file_entry,
        )


@dataclass
class FIoFileIndexEntry:
    """IoStore file index entry."""

    name: int
    next_file_entry: int
    user_data: int

    @staticmethod
    def deserialize(stream: BinaryIO) -> FIoFileIndexEntry:
        data = stream.read(12)
        if len(data) < 12:
            raise ValueError("Unexpected end of stream")
        name, next_file_entry, user_data = struct.unpack("<III", data)
        return FIoFileIndexEntry(
            name=name,
            next_file_entry=next_file_entry,
            user_data=user_data,
        )


# ============================================================================
# IoStore TOC structure (144-byte header)
# ============================================================================

# IoStore TOC magic number: "-==--==--==--==-" (16 bytes)
TOC_MAGIC = b"-==--==--==--==-"

# FIoStoreTocHeader size
TOC_HEADER_SIZE = 144


@dataclass
class FIoStoreTocHeader:
    """IoStore TOC header structure (144 bytes)

    Mirrors FIoStoreTocHeader
    """

    toc_magic: bytes  # 16 bytes
    version: int  # uint8
    reserved0: int  # uint8
    reserved1: int  # uint16
    toc_header_size: int  # uint32
    toc_entry_count: int  # uint32
    toc_compressed_block_entry_count: int  # uint32
    toc_compressed_block_entry_size: int  # uint32
    compression_method_name_count: int  # uint32
    compression_method_name_length: int  # uint32
    compression_block_size: int  # uint32
    directory_index_size: int  # uint32
    partition_count: int  # uint32
    container_id: int  # uint64 (FIoContainerId)
    encryption_key_guid: bytes  # 16 bytes (FGuid)
    container_flags: int  # uint8 (EIoContainerFlags)
    toc_chunk_perfect_hash_seeds_count: int  # uint32
    partition_size: int  # uint64
    toc_chunks_without_perfect_hash_count: int  # uint32
    reserved7: int  # uint32
    reserved8: List[int] = field(default_factory=lambda: [0] * 5)  # 5 x uint64

    @staticmethod
    def from_stream(stream: BinaryIO) -> FIoStoreTocHeader:
        """Read TOC header from stream"""
        header_data = stream.read(TOC_HEADER_SIZE)
        if len(header_data) < TOC_HEADER_SIZE:
            raise ValueError(
                f"TOC header data insufficient: need {TOC_HEADER_SIZE} bytes, got {len(header_data)} bytes"
            )

        toc_magic = header_data[0:16]
        if toc_magic != TOC_MAGIC:
            raise ValueError(f"Invalid IoStore TOC magic: {toc_magic!r}")

        # Parse header fields (little-endian) offset 16-59
        (
            version,
            reserved0,
            reserved1,
            toc_header_size,
            toc_entry_count,
            toc_compressed_block_entry_count,
            toc_compressed_block_entry_size,
            compression_method_name_count,
            compression_method_name_length,
            compression_block_size,
            directory_index_size,
            partition_count,
            reserved2,
        ) = struct.unpack_from("<BBHIIIIIIIIII", header_data, 16)

        # container_id (uint64) at offset 56
        container_id = struct.unpack_from("<Q", header_data, 56)[0]

        # encryption_key_guid (16 bytes) at offset 64
        encryption_key_guid = header_data[64:80]

        # container_flags (uint8) at offset 80
        container_flags = header_data[80]

        # reserved3(1 byte at 81) + reserved4(2 bytes at 82)
        # These are reserved fields, skip them

        # toc_chunk_perfect_hash_seeds_count (uint32) at offset 84
        toc_chunk_perfect_hash_seeds_count = struct.unpack_from("<I", header_data, 84)[0]

        # partition_size (uint64) at offset 88
        partition_size = struct.unpack_from("<Q", header_data, 88)[0]

        # toc_chunks_without_perfect_hash_count (uint32) at offset 96
        toc_chunks_without_perfect_hash_count = struct.unpack_from("<I", header_data, 96)[0]

        # reserved7 (uint32) at offset 100
        reserved7 = struct.unpack_from("<I", header_data, 100)[0]

        # reserved8 (5 x uint64 = 40 bytes) at offset 104
        reserved8_raw = header_data[104:144]
        reserved8 = list(struct.unpack_from("<5Q", reserved8_raw, 0))

        return FIoStoreTocHeader(
            toc_magic=toc_magic,
            version=version,
            reserved0=reserved0,
            reserved1=reserved1,
            toc_header_size=toc_header_size,
            toc_entry_count=toc_entry_count,
            toc_compressed_block_entry_count=toc_compressed_block_entry_count,
            toc_compressed_block_entry_size=toc_compressed_block_entry_size,
            compression_method_name_count=compression_method_name_count,
            compression_method_name_length=compression_method_name_length,
            compression_block_size=compression_block_size,
            directory_index_size=directory_index_size,
            partition_count=partition_count,
            container_id=container_id,
            encryption_key_guid=encryption_key_guid,
            container_flags=container_flags,
            toc_chunk_perfect_hash_seeds_count=toc_chunk_perfect_hash_seeds_count,
            partition_size=partition_size,
            toc_chunks_without_perfect_hash_count=toc_chunks_without_perfect_hash_count,
            reserved7=reserved7,
            reserved8=reserved8,
        )

    @property
    def is_encrypted(self) -> bool:
        """Whether the container is encrypted"""
        return bool(self.container_flags & EIoContainerFlags.Encrypted)

    @property
    def is_compressed(self) -> bool:
        """Whether the container is compressed"""
        return bool(self.container_flags & EIoContainerFlags.Compressed)

    @property
    def is_signed(self) -> bool:
        """Whether the container is signed"""
        return bool(self.container_flags & EIoContainerFlags.Signed)

    @property
    def is_indexed(self) -> bool:
        """Whether the container has a directory index"""
        return bool(self.container_flags & EIoContainerFlags.Indexed)


@dataclass
class FIoStoreTocCompressedBlockEntry:
    """IoStore TOC compressed block entry (12 bytes)

    Bit distribution:
    - Offset: 5 bytes (bits 0-39)
    - CompressedSize: 3 bytes (bits 40-63)
    - UncompressedSize: 3 bytes (bits 64-87)
    - CompressionMethodIndex: 1 byte (bits 88-95)
    """

    offset: int  # 5 bytes
    compressed_size: int  # 3 bytes
    uncompressed_size: int  # 3 bytes
    compression_method_index: int  # 1 byte

    SIZE = 12  # Size in bytes

    @staticmethod
    def from_stream(stream: BinaryIO) -> FIoStoreTocCompressedBlockEntry:
        """Read from stream"""
        data = stream.read(12)
        if len(data) < 12:
            raise ValueError("Compressed block entry data insufficient")

        # 12-byte little-endian parsing
        # Bytes 0-4: Offset (5 bytes, little-endian)
        offset = data[0] | (data[1] << 8) | (data[2] << 16) | (data[3] << 24) | ((data[4] & 0xFF) << 32)

        # Bytes 5-7: CompressedSize (3 bytes)
        compressed_size = data[5] | (data[6] << 8) | (data[7] << 16)

        # Bytes 8-10: UncompressedSize (3 bytes)
        uncompressed_size = data[8] | (data[9] << 8) | (data[10] << 16)

        # Byte 11: CompressionMethodIndex (1 byte)
        compression_method_index = data[11]

        return FIoStoreTocCompressedBlockEntry(
            offset=offset,
            compressed_size=compressed_size,
            uncompressed_size=uncompressed_size,
            compression_method_index=compression_method_index,
        )
